#!/usr/bin/env python3
# encoding: utf-8
"""Minimal pan-tilt (gimbal) test for the TurboPi.

Sends SetPWMServoState to ros_robot_controller/pwm_servo/set_state.

Axis mapping taken from the vendor's own tracking.py publish_servo():
    state_x.id = [2]; state_x.position = [servo_x]   # horizontal (pan)
    state_y.id = [1]; state_y.position = [servo_y]   # vertical   (tilt)

Ranges used by the vendor tracker:
    servo_x  800..2200   (centre 1500)
    servo_y 1200..1900   (centre 1500)

Safety: the script always returns the gimbal to centre, including on error,
and a SIGINT handler does the same.
"""
import sys
import time
import signal
import rclpy
from rclpy.node import Node
from ros_robot_controller_msgs.msg import PWMServoState, SetPWMServoState

PAN_ID = 2       # horizontal
TILT_ID = 1      # vertical
CENTRE = 1500
PAN_MIN, PAN_MAX = 800, 2200
TILT_MIN, TILT_MAX = 1200, 1900


def clamp(v, lo, hi):
    return max(lo, min(hi, int(v)))


class GimbalTest(Node):
    def __init__(self):
        super().__init__("turpi_gimbal_test")
        self.pub = self.create_publisher(
            SetPWMServoState, "ros_robot_controller/pwm_servo/set_state", 10
        )
        self._stopped = False

    def move(self, pan=None, tilt=None, duration=0.3):
        """Move one or both axes. None means 'leave as is'."""
        msg = SetPWMServoState()
        if pan is not None:
            s = PWMServoState()
            s.id = [PAN_ID]
            s.position = [clamp(pan, PAN_MIN, PAN_MAX)]
            s.offset = [0]
            msg.state.append(s)
        if tilt is not None:
            s = PWMServoState()
            s.id = [TILT_ID]
            s.position = [clamp(tilt, TILT_MIN, TILT_MAX)]
            s.offset = [0]
            msg.state.append(s)
        msg.duration = float(duration)
        self.pub.publish(msg)
        self.get_logger().info(f"sent pan={pan} tilt={tilt} duration={duration}")

    def centre(self):
        self.move(pan=CENTRE, tilt=CENTRE, duration=0.4)


def main():
    rclpy.init()
    node = GimbalTest()

    def on_sigint(_signum, _frame):
        node.get_logger().warn("interrupted: returning to centre")
        node._stopped = True

    signal.signal(signal.SIGINT, on_sigint)

    # These publishes need a moment for discovery before the first send.
    time.sleep(1.0)

    try:
        node.get_logger().info("1) centre")
        node.centre()
        time.sleep(1.5)

        node.get_logger().info("2) tilt down slightly (servo_y 1500 -> 1400)")
        node.move(tilt=1400)
        time.sleep(2.0)

        node.get_logger().info("3) tilt up slightly (servo_y 1500 -> 1600)")
        node.move(tilt=1600)
        time.sleep(2.0)

        node.get_logger().info("4) pan right slightly (servo_x 1500 -> 1600)")
        node.move(pan=1600)
        time.sleep(2.0)

        node.get_logger().info("5) back to centre")
        node.centre()
        time.sleep(1.5)

        node.get_logger().info("done")
    finally:
        try:
            node.centre()
            time.sleep(0.3)
        except Exception as exc:  # noqa: BLE001
            print(f"centre on exit failed: {exc}", file=sys.stderr)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
