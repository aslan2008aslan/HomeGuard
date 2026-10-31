#!/usr/bin/env python3
# encoding: utf-8
"""Chassis test at speeds proven to move the wheels (25% duty and up).

The direct serial test moved the wheels at duty 25, which on this firmware
maps to Twist linear.x = 0.25 (motor_speed = speed / max_linear_speed * 100,
with max_linear_speed = 1.0). So we test 0.25, 0.35 and 0.5.

Safety: every pulse is followed by an explicit zero, a watchdog forces zero,
and finally always zeroes.
"""
import sys
import time
import threading

import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist


class Chassis(Node):
    def __init__(self):
        super().__init__("turpi_speed_test")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)

    def drive(self, x=0.0, y=0.0, z=0.0):
        t = Twist()
        t.linear.x = float(x)
        t.linear.y = float(y)
        t.angular.z = float(z)
        self.pub.publish(t)

    def stop(self):
        for _ in range(4):
            self.drive()
            time.sleep(0.05)


class Watchdog(threading.Thread):
    def __init__(self, node, deadline):
        super().__init__(daemon=True)
        self.node, self.deadline, self.cancelled = node, deadline, False

    def run(self):
        time.sleep(self.deadline)
        if not self.cancelled:
            self.node.get_logger().warn("WATCHDOG: forcing stop")
            self.node.stop()


def main():
    rclpy.init()
    node = Chassis()
    time.sleep(1.5)
    wd = Watchdog(node, 20.0)
    wd.start()

    try:
        for speed in (0.25, 0.35, 0.5):
            print(f"--- speed {speed} m/s ({int(speed*100)}% duty), 3 pulses of 0.5 s ---")
            for i in range(3):
                node.drive(speed)
                time.sleep(0.5)
                node.stop()
                time.sleep(0.6)
                print(f"    pulse {i+1}/3 @ {speed}")
            time.sleep(0.5)
        print("ALL SPEEDS DONE")
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}")
    finally:
        node.stop()
        time.sleep(0.3)
        node.stop()
        print("FINAL STOP")

    wd.cancelled = True
    node.destroy_node()
    rclpy.shutdown()
    print("DONE")


if __name__ == "__main__":
    main()
