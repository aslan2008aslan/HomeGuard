#!/bin/bash
# 用打过补丁的设备程序启动 + 更新 keeper 指向新路径
set -u
HUB="${1:-ws://192.168.3.149:4180}"
NEW="/tmp/turpi_device_patched.py"

echo "===== 0. 停 keeper ====="
sudo systemctl stop turpi-keeper 2>/dev/null && echo "  已停" || echo "  未运行"
sleep 2

echo
echo "===== 1. 停旧设备程序（先发零速）====="
docker exec turbopi zsh -c '
  source /opt/ros/humble/setup.zsh >/dev/null 2>&1
  source /home/ubuntu/ros2_ws/install/setup.zsh >/dev/null 2>&1
  timeout 8 ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist "{linear: {x: 0.0}, angular: {z: 0.0}}" >/dev/null 2>&1' 2>/dev/null
echo "  已发零速"
docker exec -u root turbopi pkill -9 -f turpi_device 2>/dev/null
sleep 3
docker exec turbopi sh -c 'ps -eo cmd | grep -c "[t]urpi_device"' | tr -cd '0-9' | sed 's/^/  剩余: /'

echo
echo "===== 2. 确认补丁文件在容器内 ====="
docker exec turbopi sh -c "ls -l $NEW; grep -c 'MHS-RECONNECT' $NEW" | sed 's/^/  /'

echo
echo "===== 3. 启动（指向补丁版）====="
docker exec -d -u ubuntu -w /home/ubuntu turbopi /bin/zsh -c \
  "source ~/ros2_ws/.zshrc >/dev/null 2>&1; export PYTHONPATH=/opt/agh_mhs/python/src:\$PYTHONPATH; cd /tmp && exec python3 -u $NEW $HUB >> /tmp/turpi.log 2>&1"
echo "  等 18 秒"
sleep 18

echo
echo "===== 4. 验证 ====="
docker exec turbopi ps -eo pid,etime,cmd 2>/dev/null | grep '[t]urpi_device' | sed 's/^/  /' || echo "  ⚠ 未启动"
echo "--- 日志尾部（应有 reconnect 相关输出）---"
docker exec turbopi tail -10 /tmp/turpi.log 2>/dev/null | sed 's/^/  /'

echo
echo "===== 5. 让 keeper 也指向补丁版 ====="
# keeper.sh 里的启动命令要改路径
sudo sed -i "s#/tmp/turpi_device\.py#$NEW#g" /home/pi/turbopi_agh/keeper.sh
echo "  已改 keeper 路径:"
grep -n 'turpi_device' /home/pi/turbopi_agh/keeper.sh | sed 's/^/  /'

echo
echo "===== 6. 恢复 keeper ====="
sudo systemctl start turpi-keeper 2>/dev/null && echo "  已启动"
sleep 3
systemctl is-active turpi-keeper | sed 's/^/  状态: /'
