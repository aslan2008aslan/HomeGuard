#!/bin/bash
set -u
SRC='source /opt/ros/humble/setup.zsh >/dev/null 2>&1; source /home/ubuntu/ros2_ws/install/setup.zsh >/dev/null 2>&1'

echo "===== 正确 source 后的节点数 ====="
docker exec turbopi zsh -c "$SRC; timeout 25 ros2 node list 2>&1" 2>&1 | tr -d '\r' | head -20

echo
echo "===== /cmd_vel 订阅者（车能动的前提）====="
docker exec turbopi zsh -c "$SRC; timeout 20 ros2 topic info /cmd_vel 2>&1" 2>&1 | tr -d '\r' | head -6

echo
echo "===== 相关话题是否存在 ====="
for t in /cmd_vel /ros_robot_controller/set_motor_speeds /ros_robot_controller/battery; do
  R=$(docker exec turbopi zsh -c "$SRC; timeout 15 ros2 topic info $t 2>&1" 2>&1 | tr -d '\r' | head -2 | tr '\n' ' ')
  echo "  $t -> $R"
done
