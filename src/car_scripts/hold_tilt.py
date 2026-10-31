#!/usr/bin/env python3
# encoding: utf-8
"""Hold the gimbal at a given tilt so a picture can be taken in that pose.

Usage: hold_tilt.py <position> <seconds>
Prints one line when the position is set, so the caller knows when to capture.

Axis mapping (see the vendor's tracking.py):
    id 2 = horizontal (pan),  id 1 = vertical (tilt)
"""
import sys
import time
import rclpy
from rclpy.node import Node
from ros_robot_controller_msgs.msg import PWMServoState, SetPWMServoState

TILT_ID = 1
CENTRE = 1500


def main():
    position = int(sys.argv[1]) if len(sys.argv) > 1 else CENTRE
    hold_s = float(sys.argv[2]) if len(sys.argv) > 2 else 6.0

    rclpy.init()
    node = Node("turpi_hold_tilt")
    pub = node.create_publisher(
        SetPWMServoState, "ros_robot_controller/pwm_servo/set_state", 10
    )

    msg = SetPWMServoState()
    s = PWMServoState()
    s.id = [TILT_ID]
    s.position = [position]
    s.offset = [0]
    msg.state.append(s)
    msg.duration = 0.4

    time.sleep(1.0)  # discovery
    pub.publish(msg)
    print(f"SET tilt={position}", flush=True)

    # Keep the pose alive long enough for a capture, then return to centre.
    deadline = time.time() + hold_s
    while time.time() < deadline:
        rclpy.spin_once(node, timeout_sec=0.2)

    back = SetPWMServoState()
    s2 = PWMServoState()
    s2.id = [TILT_ID]
    s2.position = [CENTRE]
    s2.offset = [0]
    back.state.append(s2)
    back.duration = 0.4
    pub.publish(back)
    print("CENTRED", flush=True)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
