#!/usr/bin/env python3
# encoding: utf-8
"""Read back the real PWM servo state from the board.

GetPWMServoState.srv:
    ros_robot_controller_msgs/GetPWMServoCmd[] cmd
    ---
    bool success
    ros_robot_controller_msgs/PWMServoState[] state

This tells us which servo ids physically answer, which is the fact we need:
if id 1/2 read back a position, the servo exists and we can command it;
if they return nothing, those ids are not wired.
"""
import time
import rclpy
from rclpy.node import Node
from ros_robot_controller_msgs.srv import GetPWMServoState
from ros_robot_controller_msgs.msg import PWMServoState, SetPWMServoState


class Probe(Node):
    def __init__(self):
        super().__init__("turpi_servo_readback")
        self.cli = self.create_client(
            GetPWMServoState, "/ros_robot_controller/pwm_servo/get_state"
        )
        self.pub = self.create_publisher(
            SetPWMServoState, "/ros_robot_controller/pwm_servo/set_state", 10
        )

    def read(self, ids):
        if not self.cli.wait_for_service(timeout_sec=5.0):
            print("  SERVICE UNAVAILABLE")
            return None
        req = GetPWMServoState.Request()
        for i in ids:
            c = req.cmd.add() if hasattr(req.cmd, "add") else None
            if c is None:
                from ros_robot_controller_msgs.msg import GetPWMServoCmd
                c = GetPWMServoCmd()
                req.cmd.append(c)
            c.id = int(i)
            c.get_position = True
            c.get_offset = False
        fut = self.cli.call_async(req)
        rclpy.spin_until_future_complete(self, fut, timeout_sec=6.0)
        r = fut.result()
        return r

    def set_pos(self, servo_id, position, duration=0.02):
        msg = SetPWMServoState()
        s = PWMServoState()
        s.id = [servo_id]
        s.position = [int(position)]
        s.offset = [0]
        msg.state.append(s)
        msg.duration = float(duration)
        self.pub.publish(msg)


def main():
    rclpy.init()
    node = Probe()
    time.sleep(1.5)

    print("=== read back ids 1..6 ===")
    res = node.read([1, 2, 3, 4, 5, 6])
    if res is not None:
        print(f"  success={res.success}")
        for st in res.state:
            print(f"  id={list(st.id)} position={list(st.position)} offset={list(st.offset)}")

    print()
    print("=== command id1=1200 then read back id1 ===")
    node.set_pos(1, 1200)
    time.sleep(1.5)
    res = node.read([1])
    if res is not None:
        print(f"  success={res.success}")
        for st in res.state:
            print(f"  id={list(st.id)} position={list(st.position)}")

    print()
    print("=== command id2=1800 then read back id2 ===")
    node.set_pos(2, 1800)
    time.sleep(1.5)
    res = node.read([2])
    if res is not None:
        print(f"  success={res.success}")
        for st in res.state:
            print(f"  id={list(st.id)} position={list(st.position)}")

    print()
    print("=== restore centre ===")
    node.set_pos(1, 1500)
    node.set_pos(2, 1500)
    time.sleep(0.5)

    node.destroy_node()
    rclpy.shutdown()


if __name__ == "__main__":
    main()
