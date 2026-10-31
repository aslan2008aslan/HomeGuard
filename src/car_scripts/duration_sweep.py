#!/usr/bin/env python3
# encoding: utf-8
"""Test the gimbal with the vendor's own duration value.

The vendor's tracking.py uses duration = 0.02 seconds:

    msg.duration = 0.02
    self.servo_pub.publish(msg)

Our earlier tests used duration 0.4-0.6. The SDK does
    duration = int(duration * 1000)
so 0.5 becomes 500 and 0.02 becomes 20. If the board treats this as the
time allowed for the move, a large value makes the servo crawl.

This script sweeps the duration so we can see which one makes the gimbal
actually travel. Read-back is printed for each step.

Run with ros_robot_controller stopped.
"""
import sys
import time

sys.path.insert(0, "/home/pi/board_demo")
import ros_robot_controller_sdk as rrc

TILT_ID, PAN_ID = 1, 2

board = rrc.Board()
board.enable_reception()
time.sleep(0.4)
print("board opened")


def pos():
    return board.pwm_servo_read_position(TILT_ID), board.pwm_servo_read_position(PAN_ID)


def move(tilt, duration):
    board.pwm_servo_set_position(duration, [[TILT_ID, tilt]])
    time.sleep(1.2)


print()
print("=== duration sweep on tilt, moving 1500 -> 1800 each time ===")
for duration in (0.02, 0.1, 0.3, 1.0):
    board.pwm_servo_set_position(0.05, [[TILT_ID, 1500]])
    time.sleep(1.0)
    before = pos()
    move(1800, duration)
    after = pos()
    print(f"  duration={duration:<5} before={before} after={after}")
    time.sleep(0.5)

print()
print("=== leave tilted at 1800 with vendor duration, wait 3 s, re-read ===")
board.pwm_servo_set_position(0.02, [[TILT_ID, 1800]])
time.sleep(3.0)
print("  after 3 s:", pos())

print()
print("=== pan test with vendor duration ===")
board.pwm_servo_set_position(0.02, [[PAN_ID, 1750]])
time.sleep(2.0)
print("  pan:", pos())

print()
print("=== centre both ===")
board.pwm_servo_set_position(0.02, [[TILT_ID, 1500], [PAN_ID, 1500]])
time.sleep(1.5)
print("  centred:", pos())

print()
print("DURATION_SWEEP_DONE")
