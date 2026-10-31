#!/bin/bash
# 恢复设备与 hub 的连接：重启设备程序
set -u
HUB="${1:-ws://192.168.3.149:4180}"

echo "--- 重启前确认 ---"
docker exec turbopi ps -eo pid,etime,cmd 2>/dev/null | grep '[t]urpi_device' || echo "  不在"

echo
echo "--- 先发零速（安全）---"
docker exec turbopi zsh -c '
  source /opt/ros/humble/setup.zsh >/dev/null 2>&1
  source /home/ubuntu/ros2_ws/install/setup.zsh >/dev/null 2>&1
  timeout 8 ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0}, angular: {z: 0.0}}" >/dev/null 2>&1' 2>/dev/null
echo "  已发零速"

echo
echo "--- 重启设备程序 ---"
docker exec -u root turbopi pkill -9 -f turpi_device.py 2>/dev/null
sleep 4
docker exec -d -u ubuntu -w /home/ubuntu turbopi /bin/zsh -c \
  "source ~/ros2_ws/.zshrc >/dev/null 2>&1; export PYTHONPATH=/opt/agh_mhs/python/src:\$PYTHONPATH; cd /tmp && exec python3 -u /tmp/turpi_device.py $HUB >> /tmp/turpi.log 2>&1"
echo "  已启动，等 15 秒"
sleep 15

echo
echo "--- 验证 ---"
docker exec turbopi ps -eo pid,etime,cmd 2>/dev/null | grep '[t]urpi_device' || echo "  ⚠ 未启动"
echo "--- 日志尾部 ---"
docker exec turbopi tail -8 /tmp/turpi.log 2>/dev/null | sed 's/^/  /'
