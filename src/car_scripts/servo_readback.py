#!/usr/bin/env python3
# encoding: utf-8
"""Read the real PWM servo positions straight from the board.

The ROS node's get_state service was unavailable, so go one level lower:
stop nothing, just ask the board over serial? No - the node owns the port.

Instead this script is meant to run with the node STOPPED, reading each
servo id directly. That answers the one question we still lack:
which servo ids physically exist and what position they hold.
"""
import sys
import time

sys.path.insert(0, "/home/pi/board_demo")
import ros_robot_controller_sdk as rrc

board = rrc.Board()
board.enable_reception()
time.sleep(0.3)
print("board opened")

print()
print("=== read position of servo ids 1..6 ===")
for sid in range(1, 7):
    try:
        pos = board.pwm_servo_read_position(sid)
        off = board.pwm_servo_read_offset(sid)
        print(f"  id {sid}: position={pos} offset={off}")
    except Exception as exc:  # noqa: BLE001
        print(f"  id {sid}: ERROR {exc}")
    time.sleep(0.25)

print()
print("=== battery for reference ===")
print("  ", board.get_battery())

print()
print("READBACK_DONE")
