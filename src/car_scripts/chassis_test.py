#!/usr/bin/env python3
# encoding: utf-8
"""Chassis motion test, staged and time-boxed.

Publishes geometry_msgs/Twist on /cmd_vel (the topic the vendor's
mecanum_chassis_node subscribes to; it converts Twist -> motor speeds).

Safety:
  - starts by publishing zero and pausing
  - every motion is followed by an explicit zero
  - a watchdog thread publishes zero unconditionally after a deadline,
    so the robot stops even if the main flow raises
  - the finally block publishes zero again
"""
import sys
import time
import threading

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class Chassis(Node):
    def __init__(self):
        super().__init__("turpi_chassis_test")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)

    def drive(self, x=0.0, y=0.0, z=0.0):
        t = Twist()
        t.linear.x = float(x)
        t.linear.y = float(y)
        t.linear.z = 0.0
        t.angular.x = 0.0
        t.angular.y = 0.0
        t.angular.z = float(z)
        self.pub.publish(t)
        return t

    def stop(self):
        for _ in range(3):
            self.drive(0.0, 0.0, 0.0)
            time.sleep(0.05)


class Watchdog(threading.Thread):
    """Publishes zero on /cmd_vel after `deadline` seconds, no matter what."""

    def __init__(self, node, deadline):
        super().__init__(daemon=True)
        self.node = node
        self.deadline = deadline
        self.cancelled = False

    def run(self):
        time.sleep(self.deadline)
        if not self.cancelled:
            self.node.get_logger().warn("WATCHDOG: forcing stop")
            self.node.stop()


def main():
    stage = sys.argv[1] if len(sys.argv) > 1 else "zero"

    rclpy.init()
    node = Chassis()
    time.sleep(1.5)  # let discovery settle

    # Watchdog fires well after the longest planned motion.
    wd = Watchdog(node, deadline=12.0)
    wd.start()

    try:
        if stage == "zero":
            print("STAGE zero: publishing zero only")
            node.stop()
            time.sleep(1.0)
            print("STAGE zero done (no motion expected)")

        elif stage == "forward":
            print("STAGE forward: 6 pulses of 0.1 m/s, 0.3 s each")
            for i in range(6):
                node.drive(0.1, 0.0, 0.0)
                time.sleep(0.3)
                node.drive(0.0, 0.0, 0.0)
                time.sleep(0.7)
                print(f"  pulse {i + 1}/6 sent")
            print("STAGE forward done")

        elif stage == "turn":
            print("STAGE turn: 4 pulses of 0.3 rad/s, 0.3 s each")
            for i in range(4):
                node.drive(0.0, 0.0, 0.3)
                time.sleep(0.3)
                node.drive(0.0, 0.0, 0.0)
                time.sleep(0.7)
                print(f"  pulse {i + 1}/4 sent")
            print("STAGE turn done")

        else:
            print(f"unknown stage: {stage}")

    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")
    finally:
        node.stop()
        time.sleep(0.3)
        node.stop()
        print("FINAL STOP sent")

    wd.cancelled = True
    node.destroy_node()
    rclpy.shutdown()
    print("DONE")


if __name__ == "__main__":
    main()
