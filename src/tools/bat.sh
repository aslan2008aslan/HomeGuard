#!/bin/bash
# Run ON the Raspberry Pi (HOST, not the container).
#
# Reads the battery straight from the board SDK, because the ROS2 topic
# /ros_robot_controller/battery has NO publisher, so the device's `battery` state
# is always empty and the low-battery guard never fires.
#
# MUST call enable_reception() first: the SDK defaults enable_recv=False (L100),
# and every get_battery() without it returns None.
#
# WARNING: this opens /dev/ttyAMA0 while the ros_robot_controller node holds it.
# Short read-only use is fine; do NOT do this during a demo.

PYTHONPATH=/home/pi/demo python3 - <<'PY'
import time
try:
    import ros_robot_controller_sdk as rrc
except Exception as e:
    print("import failed:", type(e).__name__, e)
    raise SystemExit(1)

try:
    b = rrc.Board()
    b.enable_reception()
    time.sleep(1.0)
    vals = []
    for i in range(8):
        mv = b.get_battery()
        if mv is not None:
            vals.append(mv)
            print("  sample %d: battery = %s mV (%.2f V)" % (i, mv, mv / 1000.0))
        time.sleep(0.3)
    if not vals:
        print("  no reading -- serial contention with the ROS node?")
        raise SystemExit(1)
    lo, hi = min(vals), max(vals)
    print("")
    print("  range: %s - %s mV   (avg %.0f mV)" % (lo, hi, sum(vals) / len(vals)))
    if hi < 6900:
        print("  VERDICT: TOO LOW for motion -- charge first")
    elif hi < 7200:
        print("  VERDICT: low -- short tests only")
    else:
        print("  VERDICT: OK to drive")
except Exception as e:
    print("board read failed:", type(e).__name__, e)
PY
