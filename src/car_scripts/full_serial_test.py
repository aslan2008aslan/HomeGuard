#!/usr/bin/env python3
# encoding: utf-8
"""Full serial control test: chassis + gimbal, bypassing ROS2 entirely.

Run with ros_robot_controller STOPPED so this owns /dev/rrc.

Chassis: the vendor SDK's set_motor_duty takes [[id, duty], ...] with duty in
percent. The mecanum mix is copied from the vendor's ROS node so behaviour
matches what we already verified over /cmd_vel:

    motor1 = linear_x - linear_y - angular_z * (wheelbase + track_width) / 2
    motor2 = linear_x + linear_y - angular_z * (wheelbase + track_width) / 2
    motor3 = linear_x + linear_y + angular_z * (wheelbase + track_width) / 2
    motor4 = linear_x - linear_y + angular_z * (wheelbase + track_width) / 2
    motor_speeds = [-motor1, motor3, -motor2, motor4]     # ids 1..4

with speed_convert(v) = clamp(v / max_linear_speed * 100, -100, 100).

Gimbal: pwm_servo_set_position(duration_s, [[id, pulse], ...])
    id 1 = tilt (1200..1900), id 2 = pan (800..2200), 1500 = centre
"""
import sys
import time

sys.path.insert(0, "/home/pi/board_demo")
import ros_robot_controller_sdk as rrc

PAN_ID, TILT_ID = 2, 1
WB, TW = 0.1368, 0.1410
MAX_LINEAR = 1.0

board = rrc.Board()
board.enable_reception()
time.sleep(0.4)
print("board opened")
print("battery:", board.get_battery())


def motors_off():
    board.set_motor_duty([[1, 0], [2, 0], [3, 0], [4, 0]])


def duty(v):
    return max(-100.0, min(100.0, (v / MAX_LINEAR) * 100.0))


def mix(linear_x, linear_y, angular_z):
    r = (WB + TW) / 2.0
    m1 = linear_x - linear_y - angular_z * r
    m2 = linear_x + linear_y - angular_z * r
    m3 = linear_x + linear_y + angular_z * r
    m4 = linear_x - linear_y + angular_z * r
    return [duty(-m1), duty(m3), duty(-m2), duty(m4)]


def drive_for(linear_x, angular_z, seconds):
    """Drive at a Twist-equivalent command for a duration."""
    speeds = mix(linear_x, 0.0, angular_z)
    payload = [[i + 1, speeds[i]] for i in range(4)]
    print(f"  duty: {[round(s,1) for s in speeds]}")
    t0 = time.time()
    try:
        while time.time() - t0 < seconds:
            board.set_motor_duty(payload)
            time.sleep(0.05)
    finally:
        motors_off()
    return time.time() - t0


def gimbal(tilt=None, pan=None, duration=0.5):
    pairs = []
    if tilt is not None:
        pairs.append([TILT_ID, int(tilt)])
    if pan is not None:
        pairs.append([PAN_ID, int(pan)])
    if pairs:
        board.pwm_servo_set_position(duration, pairs)
        time.sleep(duration + 0.5)


def gimbal_pos():
    return board.pwm_servo_read_position(TILT_ID), board.pwm_servo_read_position(PAN_ID)


print()
print("=== A. gimbal: tilt down ===")
print("  before:", gimbal_pos())
gimbal(tilt=1300)
print("  after: ", gimbal_pos())

print()
print("=== B. gimbal: tilt up ===")
gimbal(tilt=1800)
print("  after: ", gimbal_pos())

print()
print("=== C. gimbal: pan right ===")
gimbal(pan=1700)
print("  after: ", gimbal_pos())

print()
print("=== D. gimbal back to centre ===")
gimbal(tilt=1500, pan=1500)
print("  after: ", gimbal_pos())

print()
print("=== E. chassis: forward 0.25 m/s for 1.6 s (about 0.4 m) ===")
t = drive_for(0.25, 0.0, 1.6)
print(f"  drove {t:.2f} s, motors zeroed")

print()
print("=== F. chassis: backward 0.25 m/s for 1.6 s ===")
t = drive_for(-0.25, 0.0, 1.6)
print(f"  drove {t:.2f} s, motors zeroed")

motors_off()
print()
print("FULL_SERIAL_TEST_DONE")
