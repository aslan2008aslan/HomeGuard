#!/usr/bin/env python3
# encoding: utf-8
"""Directly drive the gimbal servos over serial, bypassing ROS entirely.

Run with ros_robot_controller STOPPED so this owns /dev/rrc.

Sequence, with a read-back after each move so we can see if the board
took the new position:
    id2 (pan)  -> 1700
    id1 (tilt) -> 1300
    id1 (tilt) -> 1800
    both back to 1500

Each step prints the read-back so the result is not a matter of opinion.
"""
import sys
import time

sys.path.insert(0, "/home/pi/board_demo")
import ros_robot_controller_sdk as rrc

PAN_ID, TILT_ID = 2, 1

board = rrc.Board()
board.enable_reception()
time.sleep(0.3)
print("board opened")


def show(tag):
    pan = board.pwm_servo_read_position(PAN_ID)
    tilt = board.pwm_servo_read_position(TILT_ID)
    print(f"  [{tag}] pan(id2)={pan}  tilt(id1)={tilt}")


def move(pairs, duration=0.5):
    board.pwm_servo_set_position(duration, pairs)
    time.sleep(duration + 0.6)


print()
print("=== starting state ===")
show("start")

print()
print("=== 1. pan(id2) -> 1700 ===")
move([[PAN_ID, 1700]])
show("after pan")

print()
print("=== 2. tilt(id1) -> 1300 (look down) ===")
move([[TILT_ID, 1300]])
show("after tilt down")

print()
print("=== 3. tilt(id1) -> 1800 (look up) ===")
move([[TILT_ID, 1800]])
show("after tilt up")

print()
print("=== 4. back to centre ===")
move([[PAN_ID, 1500], [TILT_ID, 1500]])
show("after centre")

print()
print("DIRECT_GIMBAL_DONE")
