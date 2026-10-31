#!/usr/bin/env python3
# encoding: utf-8
"""Step 1b: read-only serial check, with reception enabled.

The SDK returns None from get_battery()/get_imu() until enable_reception()
has been called, which is why the first attempt came back empty.
The vendor's ROS node does exactly this: board.enable_reception() after Board().

No motor motion is commanded here.
"""
import sys
import time

sys.path.insert(0, "/home/pi/board_demo")
import ros_robot_controller_sdk as rrc

board = rrc.Board()
board.enable_reception()
print("Board() opened, reception enabled")

# Give the background reader time to assemble a packet.
for attempt in range(10):
    time.sleep(0.3)
    battery = board.get_battery()
    imu = board.get_imu()
    print(f"  t={attempt * 0.3:.1f}s battery={battery} imu={imu}")
    if battery is not None:
        break

button = board.get_button()
print("button:", button)

# Leave the board idle.
board.set_motor_duty([[1, 0], [2, 0], [3, 0], [4, 0]])
print("DONE_READONLY")
