#!/usr/bin/env python3
# encoding: utf-8
"""TurPi device program for Agnes MHS (Model Hardware Standard).

Runs INSIDE the turbopi docker container, where the ROS2 workspace lives,
and dials AgnesHub running on the operator's PC.

Interfaces used (all verified on the real robot, see docs/树莓派侦察记录.md):
  movement   /cmd_vel                      geometry_msgs/Twist
  gimbal     /ros_robot_controller/pwm_servo/set_state   SetPWMServoState
             id 2 = horizontal (pan), 800..2200
             id 1 = vertical   (tilt), 1200..1900
  camera     http://<pi>:8080/snapshot?topic=/image_raw   (web_video_server)
  battery    /ros_robot_controller/battery

Safety model:
  - on_stop zeroes the chassis AND centres the gimbal, and returns fast
  - every motion tool zeroes the chassis in a finally block
  - motion loops call checkpoint(), so pause/stop take effect promptly
  - unsafe() refuses motion when the battery is low

Usage:
    python3 turpi_device.py [ws://HUB_HOST:PORT]
"""

import asyncio
import math
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

from agnes_mhs import Device

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from ros_robot_controller_msgs.msg import PWMServoState, SetPWMServoState
from std_msgs.msg import UInt16

# ==== IMPORTS_SECTION ====

# ==== CONFIG_SECTION ====
HUB_URL = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:4180"

DEVICE_ID = "turpi-01"

# Camera snapshot endpoint (web_video_server inside the container).
CAMERA_URL = os.environ.get(
    "TURPI_CAMERA_URL", "http://127.0.0.1:8080/snapshot?topic=/image_raw&width=1024&height=768&quality=60"
)

# Gimbal servo ids and travel limits, taken from the vendor's tracking.py.
# NOTE: the gimbal is NOT usable through ROS2 on this robot. The
# servo_controller node filters by the joints table in servo_controller.yaml,
# which assigns id 1 and 2 to the arm, so gimbal commands are clamped by the
# arm's limits. The servos answer on PWM and their position read-back changes,
# but they only twitch under load (insufficient torque / possible hardware
# fault). Viewpoint changes are therefore done by turning the chassis.
PAN_ID = 2
TILT_ID = 1
PAN_MIN, PAN_MAX, PAN_CENTRE = 800, 2200, 1500
TILT_MIN, TILT_MAX, TILT_CENTRE = 1200, 1900, 1500
GIMBAL_USABLE = False

# Chassis. max_linear_speed is 1.0 m/s in the vendor's mecanum node, so a
# commanded speed of S m/s becomes S*100 percent duty.
MAX_LINEAR = 1.0
MAX_ANGULAR = 1.0
SAFE_LINEAR = 0.25          # m/s; measured to move the wheels

# Angular commands need a much larger number than linear ones: the vendor
# computes angular_z * (wheelbase + track_width) / 2 and then divides by
# max_linear_speed, so a rad/s value yields only ~1/7 of its duty.
# angular.z = 2.0 gives about 27.8 percent, which turns the robot reliably.
# angular.z = 0.5 gave only 6.9 percent and the wheels did not move.
TURN_COMMAND = 2.0          # rad/s; proven to turn the robot
TURN_RATE_TRUE = 1.0        # rad/s actually achieved per commanded unit (to tune)

# Nominal geometry, used only for open-loop dead reckoning.
WHEELBASE = 0.1368
TRACK_WIDTH = 0.1410
WHEEL_DIAMETER = 0.065

# Battery: the board reports millivolts; below this we refuse to drive.
BATTERY_LOW_MV = 6800

# Loop pacing for motion tools.
TICK = 0.05

# ---- Audio -----------------------------------------------------------------
# The robot has ONE USB audio device (JMTek "USB PnP Audio Device") that carries
# BOTH the microphone and the speaker. Verified on the real robot 2026-10-10:
# playing a 1 kHz tone raised the microphone's RMS level from 0.0078 to 0.8475.
#   ALSA card 2, device 0 -> plughw:2,0 for both capture and playback.
#
# Three traps, all measured:
#   1. The speaker boots MUTED at 2 percent. Without an explicit unmute a
#      perfectly good speaker looks broken.
#   2. Card 0/1 are HDMI. Bare `aplay`/`arecord` pick those and stay silent,
#      so the device must be named explicitly.
#   3. The mixer setting does NOT survive a reboot (no persisted asound.state).
AUDIO_DEVICE = os.environ.get("TURPI_AUDIO_DEVICE", "plughw:2,0")
AUDIO_CARD = os.environ.get("TURPI_AUDIO_CARD", "2")
AUDIO_RATE = 16000          # Hz; 16 kHz mono is plenty for speech and is light
AUDIO_CHANNELS = 1
SPEAKER_VOLUME = "80%"

# Recording limits, so a `listen` call cannot occupy the device forever.
LISTEN_MIN_S = 0.5
LISTEN_MAX_S = 10.0

# Playback: `say` speaks text through espeak-ng when it is installed; otherwise
# it falls back to a tone, so the caller still gets audible feedback.
SAY_MAX_CHARS = 300

# ==== CONFIG_SECTION ====

# ==== DEVICE_DECLARATION_SECTION ====


class RosBridge:
    """Thin wrapper around the ROS2 node, with its own spin thread.

    All publishers are created once and reused. Calls are thread-safe enough
    for our use: rclpy publishers may be called from any thread.
    """

    def __init__(self):
        rclpy.init(args=None)
        self.node = Node("turpi_mhs_device")

        self.cmd_pub = self.node.create_publisher(Twist, "/cmd_vel", 10)
        self.servo_pub = self.node.create_publisher(
            SetPWMServoState,
            "/ros_robot_controller/pwm_servo/set_state",
            10,
        )

        self.battery_mv = None
        self._battery_seen = False
        self.node.create_subscription(
            UInt16, "/ros_robot_controller/battery", self._on_battery, 10
        )

        self._stop_flag = threading.Event()
        self._executor = None
        self._spin_thread = threading.Thread(target=self._spin, daemon=True)
        self._spin_thread.start()

    # -- battery ----------------------------------------------------------
    def _on_battery(self, msg):
        value = float(msg.data)
        # The board reports millivolts; normalise if a small value shows up.
        self.battery_mv = value if value > 100 else value * 1000.0
        self._battery_seen = True

    def battery_percent(self):
        """Rough Li-ion pack estimate from voltage (2S ~7.4V nominal)."""
        mv = self.battery_mv
        if mv is None:
            return None
        # 8.4V full, 6.4V empty as a simple linear model.
        pct = (mv - 6400.0) / (8400.0 - 6400.0) * 100.0
        return int(max(0, min(100, round(pct))))

    # -- spinning ---------------------------------------------------------
    def _spin(self):
        while not self._stop_flag.is_set():
            try:
                rclpy.spin_once(self.node, timeout_sec=0.1)
            except Exception:  # noqa: BLE001
                time.sleep(0.1)

    def wait_for_battery(self, timeout=3.0):
        deadline = time.time() + timeout
        while time.time() < deadline and not self._battery_seen:
            time.sleep(0.05)
        return self._battery_seen

    # -- chassis ----------------------------------------------------------
    def drive(self, linear_x=0.0, linear_y=0.0, angular_z=0.0):
        t = Twist()
        t.linear.x = float(linear_x)
        t.linear.y = float(linear_y)
        t.angular.z = float(angular_z)
        self.cmd_pub.publish(t)

    def stop_chassis(self):
        for _ in range(3):
            self.drive(0.0, 0.0, 0.0)
            time.sleep(0.03)

    # -- gimbal -----------------------------------------------------------
    def set_gimbal(self, pan=None, tilt=None, duration=0.3):
        msg = SetPWMServoState()
        if pan is not None:
            s = PWMServoState()
            s.id = [PAN_ID]
            s.position = [int(max(PAN_MIN, min(PAN_MAX, pan)))]
            s.offset = [0]
            msg.state.append(s)
        if tilt is not None:
            s = PWMServoState()
            s.id = [TILT_ID]
            s.position = [int(max(TILT_MIN, min(TILT_MAX, tilt)))]
            s.offset = [0]
            msg.state.append(s)
        if not msg.state:
            return
        msg.duration = float(duration)
        self.servo_pub.publish(msg)

    def centre_gimbal(self):
        self.set_gimbal(pan=PAN_CENTRE, tilt=TILT_CENTRE, duration=0.4)

    # -- shutdown ---------------------------------------------------------
    def close(self):
        self._stop_flag.set()
        try:
            self.stop_chassis()
        except Exception:  # noqa: BLE001
            pass
        try:
            self.node.destroy_node()
            rclpy.shutdown()
        except Exception:  # noqa: BLE001
            pass


# ==== DEVICE_DECLARATION_SECTION ====

# ==== CAMERA_AND_ODOM_SECTION ====


def _run(cmd, timeout=10.0):
    """Run a command, returning (ok, stdout+stderr). Never raises."""
    try:
        p = subprocess.run(
            cmd, capture_output=True, timeout=timeout, check=False
        )
        out = (p.stdout or b"") + (p.stderr or b"")
        return p.returncode == 0, out.decode("utf-8", "replace").strip()
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def ensure_speaker():
    """Unmute and raise the speaker. Trap 1: it boots muted at 2 percent.

    Safe to call repeatedly; cheap enough to run before every utterance, which
    also covers the case where something else muted the mixer in between.
    """
    ok, _ = _run(["amixer", "-c", AUDIO_CARD, "sset", "Speaker", SPEAKER_VOLUME, "unmute"])
    return ok


def play_pcm(pcm, rate=AUDIO_RATE, channels=AUDIO_CHANNELS, timeout=20.0):
    """Play raw 16-bit little-endian PCM through the speaker.

    The hub may hand us a clip it synthesised (MHS 14.8); we write it straight
    to aplay, declaring the format explicitly so no guessing happens.
    """
    ensure_speaker()
    cmd = [
        "aplay", "-D", AUDIO_DEVICE,
        "-f", "S16_LE", "-r", str(rate), "-c", str(channels),
        "-t", "raw", "-",
    ]
    try:
        p = subprocess.run(cmd, input=pcm, capture_output=True, timeout=timeout, check=False)
        if p.returncode != 0:
            return False, (p.stderr or b"").decode("utf-8", "replace").strip()
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def speak(text, timeout=25.0):
    """Speak text. Uses espeak-ng when present, else falls back to a tone."""
    ensure_speaker()
    espeak = shutil.which("espeak-ng") or shutil.which("espeak")
    if espeak:
        ok, out = _run(
            [espeak, "--stdout", "-v", "zh", "-s", "150", text], timeout=timeout
        )
        if not ok:
            # A missing Chinese voice is common; retry in the default voice.
            ok, out = _run([espeak, "--stdout", "-s", "150", text], timeout=timeout)
        if ok and out:
            raw = out if isinstance(out, bytes) else out.encode("latin-1", "replace")
            return play_pcm(raw, rate=22050, timeout=timeout)
    # Fallback: an audible 660 Hz beep, so silence never reads as success.
    tone = b"".join(
        int(12000 * math.sin(2 * math.pi * 660 * i / AUDIO_RATE)).to_bytes(
            2, "little", signed=True
        )
        for i in range(int(AUDIO_RATE * 0.7))
    )
    ok, err = play_pcm(tone, timeout=timeout)
    if ok:
        return False, "no speech synthesiser on the robot; played a tone instead"
    return False, err


def record_pcm(seconds, timeout=None):
    """Record mono 16-bit PCM. Returns (pcm, error).

    Reads from plughw explicitly (trap 2: the default is HDMI and would return
    silence without erroring). Read as raw bytes so no WAV header stripping is
    needed; the declared rate and channel count go alongside it.
    """
    seconds = max(LISTEN_MIN_S, min(LISTEN_MAX_S, float(seconds)))
    # arecord wants a whole number of seconds; a value like "3.0" is rejected.
    whole = max(1, int(round(seconds)))
    cmd = [
        "arecord", "-D", AUDIO_DEVICE,
        "-f", "S16_LE", "-r", str(AUDIO_RATE), "-c", str(AUDIO_CHANNELS),
        "-t", "raw", "-d", str(whole), "-",
    ]
    try:
        p = subprocess.run(
            cmd, capture_output=True, stdin=subprocess.DEVNULL,
            timeout=timeout or (whole + 8.0), check=False,
        )
    except Exception as exc:  # noqa: BLE001
        return None, str(exc)
    data = p.stdout or b""
    if not data:
        err = (p.stderr or b"").decode("utf-8", "replace").strip()
        return None, err or "arecord returned no audio"
    # STR-3: an audio frame must be whole 16-bit samples.
    if len(data) % 2:
        data = data[:-1]
    return data, None


def pcm_level(pcm):
    """Peak and RMS of 16-bit PCM as fractions of full scale.

    Gives the model something to judge by: a silent room and a running tap look
    identical in a byte count, but not in these numbers.
    """
    n = len(pcm) // 2
    if n == 0:
        return 0.0, 0.0
    import array as _array

    samples = _array.array("h")
    samples.frombytes(pcm)
    peak = 0
    total = 0
    for s in samples:
        a = s if s >= 0 else -s
        if a > peak:
            peak = a
        total += s * s
    return peak / 32768.0, math.sqrt(total / n) / 32768.0


def grab_jpeg(timeout=3.0):
    """Fetch one JPEG from web_video_server. Returns bytes or None."""
    try:
        with urllib.request.urlopen(CAMERA_URL, timeout=timeout) as resp:
            data = resp.read()
        # JPEG magic check.
        if len(data) > 4 and data[0] == 0xFF and data[1] == 0xD8:
            return data
        return None
    except Exception:  # noqa: BLE001
        return None


class Odometry:
    """Open-loop dead reckoning.

    The robot has no wheel encoders and publishes no /odom, so position is
    integrated from commanded velocity. It WILL drift; the device therefore
    reports `ok: false` on its pose source and keeps the estimate coarse.
    """

    def __init__(self, x=0.0, y=0.0, yaw=0.0):
        self.x = float(x)
        self.y = float(y)
        self.yaw = float(yaw)   # radians, CCW from +x
        self._last = time.time()

    def reset(self, x=0.0, y=0.0, yaw=0.0):
        self.x, self.y, self.yaw = float(x), float(y), float(yaw)
        self._last = time.time()

    def integrate(self, linear_x, linear_y, angular_z):
        now = time.time()
        dt = now - self._last
        self._last = now
        if dt <= 0 or dt > 1.0:
            return
        # Body-frame velocities -> world frame using the current heading.
        cos_y, sin_y = math.cos(self.yaw), math.sin(self.yaw)
        self.x += (linear_x * cos_y - linear_y * sin_y) * dt
        self.y += (linear_x * sin_y + linear_y * cos_y) * dt
        self.yaw += angular_z * dt

    def as_pose(self):
        return {
            "map": "home",
            "x": round(self.x, 3),
            "y": round(self.y, 3),
            "yaw": round(math.degrees(self.yaw), 1),
            # Honest: this is dead reckoning without encoders.
            "ok": False,
        }


# ==== DEVICE_AND_TOOLS_SECTION ====

# Map of the home, in metres. Named places let the brain ask for a spot by
# name instead of coordinates. Edit to match the real flat.
HOME_MAP = {
    "id": "home",
    "name": "Home",
    "bounds": [0, 0, 6, 4],
    "places": [
        {"id": "dock", "name": "Charging dock", "at": [0.5, 0.5], "yaw": 0},
        {"id": "plant", "name": "Balcony pothos", "at": [4.8, 1.2]},
        {"id": "window", "name": "Kitchen window", "at": [5.4, 3.2]},
    ],
}

bridge = RosBridge()
odo = Odometry(x=0.5, y=0.5, yaw=0.0)

# Calibration: measured travel differs from commanded travel because there
# are no encoders. Refine once the backward-1m test is measured by hand.
SPEED_CALIBRATION = 1.0

current_tilt = TILT_CENTRE
current_pan = PAN_CENTRE
_chassis_lock = asyncio.Lock()


dev = Device(
    DEVICE_ID,
    "robot",
    name="TurPi patrol car",
    model="TurboPi",
    mobile=True,
    localization="self",
    maps=[HOME_MAP],
    resources={"chassis": "reject"},
    state={
        "battery": {
            "type": "integer",
            "unit": "%",
            "min": 0,
            "max": 100,
            "role": "battery",
            "alert": {"warn": 30, "bad": 15, "below": True},
        },
        "gimbal_tilt": {"type": "number", "unit": "x_us", "min": TILT_MIN, "max": TILT_MAX},
        "gimbal_pan": {"type": "number", "unit": "x_us", "min": PAN_MIN, "max": PAN_MAX},
    },
)

# Live camera. One JPEG per message; the model reads these directly.
front = dev.source(
    "front",
    "image",
    "colour camera on the pan-tilt gimbal",
    hz=0.25,
    mime="image/jpeg",
    encoding="rgb",
    size=[1024, 768],
    fov_deg=[60, 45],
    mount={"xyz": [0.1, 0, 0.15], "rpy": [0, 0, 0]},
    default=True,
)

# Dead-reckoned pose. `ok: false` is honest: no wheel encoders exist.
# A pose source must declare the model that computes it (MOS 4): ours is
# simple dead reckoning, so say exactly that.
pose_src = dev.source(
    "pose",
    "pose",
    "dead-reckoned position (no wheel encoders; drifts)",
    hz=2,
    model={"name": "turpi-dead-reckoning", "version": "1.0"},
    max_error_m=1.0,
)

# Microphone. Shares the single USB audio device with the speaker (see AUDIO_DEVICE).
# Frames are raw 16-bit little-endian mono PCM at AUDIO_RATE, which is what the
# hub's audio checks expect (STR-3). Deliberately NOT default: opening the mic
# continuously would hold the one audio device and block `say`.
mic = dev.source(
    "mic",
    "audio",
    "microphone on the USB audio device (raw 16-bit PCM)",
    hz=1,
    mime="audio/x-pcm",
    rate=AUDIO_RATE,
    channels=AUDIO_CHANNELS,
    mount={"xyz": [0.0, 0, 0.1], "rpy": [0, 0, 0]},
)


@dev.tool(
    "Drive forward a given distance in metres; negative reverses.",
    timeout=30,
    params={
        "distance": {
            "type": "number",
            "minimum": -3.0,
            "maximum": 3.0,
            "description": "metres, positive is forward",
        },
        "speed": {
            "type": "number",
            "minimum": 0.1,
            "maximum": 0.4,
            "description": "m/s; defaults to 0.25",
        },
    },
    required=["distance"],
    uses=["chassis"],
    motion=True,
    pausable=True,
)
async def drive(call, distance, speed=SAFE_LINEAR):
    """Drive straight for a distance, with progress and pause support."""
    speed = min(abs(speed), SAFE_LINEAR)
    direction = 1.0 if distance >= 0 else -1.0
    target = abs(distance) * SPEED_CALIBRATION
    travelled = 0.0
    try:
        while travelled < target:
            # Blocks while a pause is wanted; stop_chassis brings us to rest.
            await call.checkpoint(bridge.stop_chassis)
            bridge.drive(direction * speed, 0.0, 0.0)
            await asyncio.sleep(TICK)
            travelled += speed * TICK
            odo.integrate(direction * speed, 0.0, 0.0)
            call.progress(done=round(travelled, 2), total=round(target, 2))
    finally:
        bridge.stop_chassis()
    return f"drove {travelled:.2f} m {'forward' if direction > 0 else 'backward'}"


@dev.tool(
    "Turn in place by an angle in degrees; positive turns left.",
    timeout=40,
    params={
        "angle": {
            "type": "number",
            "minimum": -180,
            "maximum": 180,
            "description": "degrees, left positive",
        }
    },
    required=["angle"],
    uses=["chassis"],
    motion=True,
    pausable=True,
)
async def turn(call, angle):
    """Rotate on the spot.

    Commands a fixed angular rate proven to move the wheels (TURN_COMMAND),
    and runs for the time needed to cover the requested angle.
    """
    target = abs(math.radians(angle))
    direction = 1.0 if angle >= 0 else -1.0
    turned = 0.0
    seconds = target / max(TURN_RATE_TRUE, 0.01)
    try:
        t0 = asyncio.get_event_loop().time()
        while turned < target:
            await call.checkpoint(bridge.stop_chassis)
            bridge.drive(0.0, 0.0, direction * TURN_COMMAND)
            await asyncio.sleep(TICK)
            elapsed = asyncio.get_event_loop().time() - t0
            turned = elapsed * TURN_RATE_TRUE
            odo.integrate(0.0, 0.0, direction * TURN_RATE_TRUE)
            call.progress(done=round(math.degrees(min(turned, target)), 1), total=abs(angle))
        _ = seconds
    finally:
        bridge.stop_chassis()
    return f"turned {math.degrees(min(turned, target)):.1f} deg {'left' if direction > 0 else 'right'}"


@dev.tool(
    "Turn to get a different view of the target, then report ready for another picture.",
    timeout=40,
    params={
        "degrees": {
            "type": "number",
            "minimum": -90,
            "maximum": 90,
            "description": "how far to turn, left positive; 25-40 works well",
        }
    },
    required=["degrees"],
    uses=["chassis"],
    motion=True,
    pausable=True,
)
async def change_view(call, degrees):
    """Shift the viewpoint so a second photo is taken from elsewhere.

    Used when a judgement is low-confidence: the same scene from a new angle
    usually resolves it. The camera itself stays at its fixed pose because the
    gimbal is not usable on this robot.
    """
    result = await turn(call, degrees)
    return f"view changed: {result}"


@dev.tool(
    "Aim the camera. Not usable on this robot (gimbal has no torque); kept so the "
    "failure is reported honestly instead of silently doing nothing.",
    timeout=10,
    params={
        "tilt": {
            "type": "integer",
            "minimum": TILT_MIN,
            "maximum": TILT_MAX,
            "description": "1500 is nominal level",
        },
        "pan": {
            "type": "integer",
            "minimum": PAN_MIN,
            "maximum": PAN_MAX,
            "description": "optional; 1500 is nominal straight ahead",
        },
    },
    required=["tilt"],
)
async def aim_camera(call, tilt, pan=None):
    """Refuse honestly: the gimbal moves only a few degrees under load.

    Position read-back changes, so the servo accepts the command, but the
    camera does not actually travel. Reporting the failure lets the brain
    fall back to change_view instead of assuming a new angle was achieved.
    """
    from agnes_mhs import CallError

    raise CallError(
        "x_gimbal_unavailable",
        "the pan-tilt gimbal does not move the camera on this robot "
        "(servo accepts the position but has no torque under load); "
        "use change_view to turn the chassis instead",
    )
    _ = (tilt, pan)  # kept for schema compatibility


@dev.tool("Stop immediately: zero the wheels and level the camera.", timeout=8)
async def halt(call):
    """Explicit stop, alongside the hub's own stop."""
    bridge.stop_chassis()
    bridge.centre_gimbal()
    return "stopped, camera centred"


@dev.tool(
    "Say something out loud through the speaker. Use for short spoken reports "
    "such as alerting a person nearby.",
    timeout=40,
    params={
        "text": {
            "type": "string",
            "maxLength": SAY_MAX_CHARS,
            "description": "what to say, in plain text",
        }
    },
    required=["text"],
)
async def say(call, text):
    """Speak text through the USB speaker.

    Returns an error when the robot has no speech synthesiser rather than
    pretending the words were spoken: a tone is not speech, and the caller
    should know which one it got.
    """
    from agnes_mhs import CallError

    text = (text or "").strip()[:SAY_MAX_CHARS]
    if not text:
        raise CallError("x_empty_text", "nothing to say")

    loop = asyncio.get_event_loop()
    ok, msg = await loop.run_in_executor(None, speak, text)
    if ok:
        return f'said: {text}'
    raise CallError("x_audio_playback_failed", msg or "could not play audio")


@dev.tool(
    "Listen through the microphone for a few seconds and report how loud it was. "
    "Use to check for sound such as running water or an alarm.",
    timeout=30,
    params={
        "seconds": {
            "type": "number",
            "minimum": LISTEN_MIN_S,
            "maximum": LISTEN_MAX_S,
            "description": "how long to listen; defaults to 3",
        }
    },
)
async def listen(call, seconds=3.0):
    """Record a short clip and describe its level.

    Returns level numbers as well as a word, because 'quiet' is a judgement and
    the caller may want to make its own from the measurements.
    """
    from agnes_mhs import CallError

    loop = asyncio.get_event_loop()
    pcm, err = await loop.run_in_executor(None, record_pcm, seconds)
    if pcm is None:
        raise CallError("x_audio_capture_failed", err or "could not record audio")

    peak, rms = pcm_level(pcm)
    if peak < 0.02:
        word = "silent"
    elif peak < 0.12:
        word = "quiet"
    elif peak < 0.5:
        word = "audible"
    else:
        word = "loud"
    return (
        f"listened for {len(pcm) / 2 / AUDIO_RATE:.1f} s: {word} "
        f"(peak {peak:.3f}, rms {rms:.4f} of full scale)"
    )


# ==== HOOKS_SECTION ====


def _motors_off():
    """Zero the chassis. Called by the framework on stop and while paused."""
    try:
        bridge.stop_chassis()
    except Exception:  # noqa: BLE001
        pass


# on_stop must return quickly: the hub waits for it before interrupting motion.
dev.on_stop = lambda: (bridge.stop_chassis(), bridge.centre_gimbal())


def _unsafe(tool):
    """Refuse motion when the pack is low, and report why."""
    if tool in ("drive", "turn"):
        mv = bridge.battery_mv
        if mv is not None and mv < BATTERY_LOW_MV:
            return f"battery is {mv:.0f} mV; charge before driving"
    return None


dev.unsafe = _unsafe


def _after():
    """Attached to every result: current pose estimate and battery."""
    out = {"pose": odo.as_pose()}
    mv = bridge.battery_mv
    if mv is not None:
        out["battery_mv"] = round(mv, 0)
    return out


dev.after = _after


# ==== HOOKS_SECTION ====


# ==== LOOPS_AND_MAIN_SECTION ====


async def stream_camera():
    """Push a JPEG whenever the hub wants one.

    NOTE: source.send() takes metadata first and the binary payload second:
        send(data: dict, binary: bytes | None = None)
    Passing the JPEG as the first argument (an earlier bug) means the hub
    never sees a "bin" announcement and silently drops every frame.
    """
    while True:
        try:
            if front.wants():
                data = await asyncio.get_event_loop().run_in_executor(None, grab_jpeg)
                if data:
                    front.send({"w": 1024, "h": 768}, data)
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(0.2)


async def stream_pose():
    """Push the dead-reckoned pose at the declared rate."""
    while True:
        try:
            if pose_src.wants():
                pose_src.send(odo.as_pose())
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(0.4)


async def poll_battery(dev_obj):
    """Mirror the ROS battery topic into device state."""
    while True:
        try:
            pct = bridge.battery_percent()
            if pct is not None:
                dev_obj.update(battery=pct)
                mv = bridge.battery_mv or 0
                if mv and mv < BATTERY_LOW_MV:
                    dev_obj.problem = "battery low; charge before driving"
                    dev_obj.faults = ["battery_low"]
                else:
                    dev_obj.problem = None
                    dev_obj.faults = []
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(2.0)


async def main():
    bridge.wait_for_battery(timeout=3.0)
    pct = bridge.battery_percent()
    if pct is not None:
        dev.update(battery=pct)

    bridge.centre_gimbal()
    dev.update(gimbal_tilt=TILT_CENTRE, gimbal_pan=PAN_CENTRE)

    # Unmute the speaker at boot: it comes up muted at 2 percent, and the
    # setting does not survive a reboot. Doing it here means the first `say`
    # is audible instead of mysteriously silent.
    ok = await asyncio.get_event_loop().run_in_executor(None, ensure_speaker)
    print(f"audio: speaker unmute {'ok' if ok else 'FAILED'}", flush=True)

    tasks = [
        asyncio.create_task(stream_camera()),
        asyncio.create_task(stream_pose()),
        asyncio.create_task(poll_battery(dev)),
    ]
    try:
        await dev.run(HUB_URL)
    finally:
        for t in tasks:
            t.cancel()
        bridge.close()


# ==== MHS-RECONNECT: 断线自动重连 ====
def _is_connection_error(exc):
    """判断是否为可重试的连接类异常。"""
    name = type(exc).__module__ + "." + type(exc).__name__
    text = f"{name} {exc}".lower()
    for key in (
        "connectionclosed",     # websockets 断连
        "keepalive",
        "timeout",
        "connectionreset",
        "connectionerror",
        "brokenpipe",
        "eof",
        "1011",
    ):
        if key in text:
            return True
    return False


def _run_with_reconnect():
    """反复运行 main()，连接断了就退避重连。"""
    attempt = 0
    while True:
        try:
            asyncio.run(main())
            # main() 正常返回也视为断开，继续重连
            print("[reconnect] main() returned; reconnecting", flush=True)
            attempt = 0
        except KeyboardInterrupt:
            print("[reconnect] interrupted by user; exiting", flush=True)
            raise
        except Exception as exc:  # noqa: BLE001
            if not _is_connection_error(exc):
                # 非连接类错误：不吞掉，打印后仍然重试（机器人要能自愈）
                print(f"[reconnect] unexpected error: {type(exc).__name__}: {exc}",
                      flush=True)
            else:
                print(f"[reconnect] connection lost: {type(exc).__name__}: {exc}",
                      flush=True)

        # 退避：2s, 4s, 8s, 16s, 30s 封顶
        attempt += 1
        delay = min(2 ** min(attempt, 5), 30)
        print(f"[reconnect] retrying in {delay}s (attempt {attempt})", flush=True)

        # 重连前确保底盘停止（安全）
        try:
            bridge.stop_chassis()
            bridge.centre_gimbal()
        except Exception:  # noqa: BLE001
            pass

        time.sleep(delay)


if __name__ == "__main__":
    try:
        _run_with_reconnect()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            bridge.stop_chassis()
            bridge.centre_gimbal()
        except Exception:  # noqa: BLE001
            pass


# ==== LOOPS_AND_MAIN_SECTION ====
