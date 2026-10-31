#!/bin/bash
# 紧急：停止一切可能让车动的源头
set -u
echo "===== 1. 停 keeper（它是我加的，先停掉止血）====="
if [ -f /tmp/keeper.lock ]; then
  OLD=$(cat /tmp/keeper.lock)
  kill -9 "$OLD" 2>/dev/null && echo "  已停 keeper pid=$OLD"
  rm -f /tmp/keeper.lock
fi
for p in $(ps -eo pid,args | awk '/bash \/tmp\/keeper\.sh/ {print $1}'); do
  kill -9 "$p" 2>/dev/null && echo "  兜底停 $p"
done
ps -eo args | grep -c 'bash /tmp/keeper\.sh' | sed 's/^/  剩余 keeper: /'

echo
echo "===== 2. 停设备程序（它会发 /cmd_vel）====="
docker exec -u root turbopi pkill -9 -f turpi_device.py 2>/dev/null
sudo pkill -9 -f turpi_device.py 2>/dev/null
sleep 3
docker exec turbopi sh -c 'ps -eo cmd | grep -c "[t]urpi_device"' | sed 's/^/  剩余设备程序: /'

echo
echo "===== 3. 确认还有谁在发 /cmd_vel ====="
SRC='source /opt/ros/humble/setup.zsh >/dev/null 2>&1; source /home/ubuntu/ros2_ws/install/setup.zsh >/dev/null 2>&1'
docker exec turbopi zsh -c "$SRC; timeout 20 ros2 topic info /cmd_vel 2>&1" 2>/dev/null | tr -d '\r' | head -4

echo
echo "===== 4. 直接给底盘发停止指令（硬停）====="
docker exec turbopi zsh -c "$SRC; timeout 15 ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.0}, angular: {z: 0.0}}' 2>&1" 2>/dev/null | tr -d '\r' | tail -3
echo "  已发零速"

echo
echo "===== 5. 确认真机停止：看电机话题 ====="
docker exec turbopi zsh -c "$SRC; timeout 10 ros2 topic echo /ros_robot_controller/set_motor_speeds --once 2>&1" 2>/dev/null | tr -d '\r' | head -14

echo
echo "===== 6. 检查是否还有开机自启的运动节点 ====="
docker exec turbopi ps -eo pid,cmd 2>/dev/null | grep -iE '[l]ine_follow|[a]voidance|[t]racking|[g]esture|[m]ecanum' | head -5
