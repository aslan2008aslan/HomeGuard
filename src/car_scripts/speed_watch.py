#!/usr/bin/env python3
# encoding: utf-8
"""Watch what the chassis node actually publishes, while we command it.

Subscribes to /ros_robot_controller/set_motor_speeds (the output of
mecanum_chassis_node) and reports the motor values it produces for a
given Twist. This proves the chain Twist -> motor speeds works,
independent of whether we can see the wheels.
"""
import sys
import time

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from ros_robot_controller_msgs.msg import MotorsSpeedControl


class Watch(Node):
    def __init__(self):
        super().__init__("turpi_speed_watch")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.received = []
        self.create_subscription(
            MotorsSpeedControl,
            "/ros_robot_controller/set_motor_speeds",
            self.on_speeds,
            10,
        )

    def on_speeds(self, msg):
        vals = []
        for m in msg.data:
            vals.append((getattr(m, "id", None), getattr(m, "speed", None)))
        self.received.append(vals)

    def drive(self, x=0.0, y=0.0, z=0.0):
        t = Twist()
        t.linear.x = float(x)
        t.linear.y = float(y)
        t.angular.z = float(z)
        self.pub.publish(t)


def main():
    x = float(sys.argv[1]) if len(sys.argv) > 1 else 0.3
    z = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0

    rclpy.init()
    node = Watch()
    time.sleep(2.0)

    print(f"commanding linear.x={x} angular.z={z} for 1.5 s")
    node.received.clear()
    t0 = time.time()
    while time.time() - t0 < 1.5:
        node.drive(x, 0.0, z)
        rclpy.spin_once(node, timeout_sec=0.05)

    node.drive(0.0, 0.0, 0.0)
    for _ in range(5):
        node.drive(0.0, 0.0, 0.0)
        rclpy.spin_once(node, timeout_sec=0.1)

    print(f"set_motor_speeds messages received: {len(node.received)}")
    for i, v in enumerate(node.received[:6]):
        print(f"  msg{i}: {v}")
    if len(node.received) > 1:
        print(f"  last: {node.received[-1]}")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
