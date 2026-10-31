#!/usr/bin/env python3
# encoding: utf-8
"""Objective motion check: sample the IMU while driving, and report whether it changed.

If the chassis really moves, the IMU sees acceleration / angular rate.
If nothing moves, the readings stay flat.
"""
import sys
import time

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Imu
from geometry_msgs.msg import Twist


class Probe(Node):
    def __init__(self):
        super().__init__("turpi_motion_probe")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(Imu, "/ros_robot_controller/imu_raw", self.on_imu, 10)
        self.samples = []
        self.got_imu = False

    def on_imu(self, msg):
        self.got_imu = True
        a = msg.linear_acceleration
        g = msg.angular_velocity
        self.samples.append((time.time(), a.x, a.y, a.z, g.x, g.y, g.z))

    def drive(self, x=0.0, y=0.0, z=0.0):
        t = Twist()
        t.linear.x = float(x)
        t.linear.y = float(y)
        t.angular.z = float(z)
        self.pub.publish(t)


def main():
    speed = float(sys.argv[1]) if len(sys.argv) > 1 else 0.3

    rclpy.init()
    node = Probe()
    time.sleep(2.0)

    print(f"imu topic seen: {node.got_imu}")
    if not node.got_imu:
        # list what IMU-ish topics exist by trying the other common name
        print("no IMU on /ros_robot_controller/imu_raw; will rely on timing only")

    print(f"driving forward at {speed} m/s for 2.0 s")
    node.samples.clear()
    t0 = time.time()
    while time.time() - t0 < 2.0:
        node.drive(speed, 0.0, 0.0)
        rclpy.spin_once(node, timeout_sec=0.05)
    node.drive(0.0, 0.0, 0.0)
    for _ in range(5):
        node.drive(0.0, 0.0, 0.0)
        rclpy.spin_once(node, timeout_sec=0.1)

    n = len(node.samples)
    print(f"imu samples collected: {n}")
    if n:
        acc = [s[1:4] for s in node.samples]
        gyr = [s[4:7] for s in node.samples]
        axs = [a[0] for a in acc]
        azs = [a[2] for a in acc]
        gzs = [g[2] for g in gyr]
        print(f"  accel.x  min={min(axs):+.4f} max={max(axs):+.4f} range={max(axs)-min(axs):.4f}")
        print(f"  accel.z  min={min(azs):+.4f} max={max(azs):+.4f} range={max(azs)-min(azs):.4f}")
        print(f"  gyro.z   min={min(gzs):+.4f} max={max(gzs):+.4f} range={max(gzs)-min(gzs):.4f}")

        # A moving chassis perturbs linear acceleration along x.
        motion = (max(axs) - min(axs)) > 0.15
        print("VERDICT:", "MOTION DETECTED" if motion else "NO CLEAR MOTION (readings flat)")

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
