#!/usr/bin/env python3
# encoding: utf-8
"""Move the gimbal to three very different tilts and hold each briefly.

Usage: sweep_tilt.py
Prints a line per position so the caller knows when to capture.
Ends with a return to 1500.
"""
import time
import rclpy
from rclpy.node import Node
from ros_robot_controller_msgs.msg import PWMServoState, SetPWMServoState

TILT_ID = 1
PAN_ID = 2
POSITIONS = [1250, 1500, 1800]
HOLD = 5.0


def main():
    rclpy.init()
    node = Node("turpi_sweep")
    pub = node.create_publisher(
        SetPWMServoState, "/ros_robot_controller/pwm_servo/set_state", 10
    )

    def set_pos(tilt, duration=0.5):
        msg = SetPWMServoState()
        for sid, pos in ((TILT_ID, tilt), (PAN_ID, 1500)):
            s = PWMServoState()
            s.id = [sid]
            s.position = [pos]
            s.offset = [0]
            msg.state.append(s)
        msg.duration = duration
        pub.publish(msg)

    time.sleep(1.5)
    for tilt in POSITIONS:
        set_pos(tilt)
        print(f"HOLDING tilt={tilt}", flush=True)
        deadline = time.time() + HOLD
        while time.time() < deadline:
            rclpy.spin_once(node, timeout_sec=0.2)

    set_pos(1500)
    print("CENTRED", flush=True)
    time.sleep(1.0)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
