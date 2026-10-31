#!/usr/bin/env python3
# encoding: utf-8
"""Serial link test with the ROS node stopped.

Step A: can we read data back (battery)?  -> proves the port is bidirectional.
Step B: a tiny motor pulse, wheels off the ground.
Step C: motors back to zero.

Run only while ros_robot_controller is stopped, so the port is free.
"""
import sys
import time

sys.path.insert(0, "/home/pi/board_demo")
import ros_robot_controller_sdk as rrc

print("opening board...")
try:
    board = rrc.Board()
except Exception as exc:  # noqa: BLE001
    print(f"OPEN FAILED: {exc}")
    sys.exit(2)

board.enable_reception()
print("opened, reception enabled")

# --- Step A: read back ---
print("\n--- A: read-back test ---")
got = None
for i in range(15):
    time.sleep(0.3)
    b = board.get_battery()
    imu = board.get_imu()
    if b is not None or imu is not None:
        print(f"  t={i*0.3:.1f}s battery={b} imu={imu}")
        got = b if b is not None else imu
        break
if got is None:
    print("  NO DATA READ BACK in 4.5s (port may be write-only / board not replying)")
else:
    print("  READ-BACK OK: the serial port is bidirectional")

# --- Step B: tiny motor pulse ---
print("\n--- B: motor pulse (3 x 0.4s at 25) ---")
try:
    for i in range(3):
        board.set_motor_duty([[1, 25], [2, 25], [3, 25], [4, 25]])
        print(f"  pulse {i+1}: all motors +25")
        time.sleep(0.4)
        board.set_motor_duty([[1, 0], [2, 0], [3, 0], [4, 0]])
        print(f"  pulse {i+1}: stopped")
        time.sleep(0.8)
except Exception as exc:  # noqa: BLE001
    print(f"  PULSE FAILED: {exc}")
finally:
    board.set_motor_duty([[1, 0], [2, 0], [3, 0], [4, 0]])
    print("  motors zeroed")

print("\nSERIAL_TEST_DONE")
