#!/usr/bin/env python3
# encoding: utf-8
"""Determine whether the gimbal servos are PWM or bus servos.

PWM servos: read back instantly from the board (pwm_servo_read_position).
Bus servos: answer over the servo bus, and need torque enabled before they
hold a position (bus_servo_enable_torque).

Run with ros_robot_controller stopped so this owns /dev/rrc.
"""
import sys
import time

sys.path.insert(0, "/home/pi/board_demo")
import ros_robot_controller_sdk as rrc

board = rrc.Board()
board.enable_reception()
time.sleep(0.4)
print("board opened")

print()
print("=== PWM read for ids 1..6 ===")
for sid in range(1, 7):
    try:
        print(f"  id {sid}: pwm_position={board.pwm_servo_read_position(sid)}")
    except Exception as exc:  # noqa: BLE001
        print(f"  id {sid}: pwm error {exc}")
    time.sleep(0.15)

print()
print("=== BUS servo read for ids 1..6 (different protocol) ===")
for sid in range(1, 7):
    try:
        pos = board.bus_servo_read_position(sid)
        vin = board.bus_servo_read_vin(sid)
        temp = board.bus_servo_read_temp(sid)
        torque = board.bus_servo_read_torque_state(sid)
        print(f"  id {sid}: pos={pos} vin={vin} temp={temp} torque={torque}")
    except Exception as exc:  # noqa: BLE001
        print(f"  id {sid}: bus error {exc}")
    time.sleep(0.25)

print()
print("=== try enabling torque on bus ids 1 and 2, then re-read ===")
for sid in (1, 2):
    try:
        board.bus_servo_enable_torque(sid, 1)
        time.sleep(0.3)
        print(f"  id {sid}: after enable_torque -> pos={board.bus_servo_read_position(sid)}")
    except Exception as exc:  # noqa: BLE001
        print(f"  id {sid}: enable_torque failed {exc}")

print()
print("=== ask a bus servo to move, if it is one ===")
try:
    board.bus_servo_set_position(0.5, [[1, 1300]])
    time.sleep(1.0)
    print("  after bus move id1 ->", board.bus_servo_read_position(1))
    board.bus_servo_set_position(0.5, [[1, 1500]])
    time.sleep(1.0)
    print("  restored id1 ->", board.bus_servo_read_position(1))
except Exception as exc:  # noqa: BLE001
    print(f"  bus move failed: {exc}")

print()
print("SERVO_TYPE_PROBE_DONE")
