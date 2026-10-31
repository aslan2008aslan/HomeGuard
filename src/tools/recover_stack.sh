#!/bin/bash
# 设备掉线恢复：ROS 栈全死（僵尸）+ 设备进程空转。
# 步骤：清僵尸 -> 重启容器（彻底）-> 拉栈 -> 验判据 -> 启设备。
set -u
HUB="${1:-ws://192.168.3.149:4180}"
SRC='source /opt/ros/humble/setup.zsh >/dev/null 2>&1; source /home/ubuntu/ros2_ws/install/setup.zsh >/dev/null 2>&1'
log(){ echo; echo "===== $* ====="; }

log "0. 现状"
docker exec turbopi ps -eo pid,stat,cmd 2>/dev/null | grep -cE 'Z' | sed 's/^/  僵尸进程数: /'

log "1. 停设备程序 + 重启容器（清所有僵尸）"
docker exec -u root turbopi pkill -f turpi_device.py 2>/dev/null
sleep 2
docker restart turbopi 2>&1 | tail -1
echo "  等待容器起来..."
sleep 20
docker exec turbopi ps -eo pid,stat,cmd 2>/dev/null | grep -cE 'Z' | sed 's/^/  重启后僵尸数: /'

log "2. 手动拉起 ROS 栈（容器重启后不自启！）"
docker exec -d -u ubuntu -w /home/ubuntu turbopi /bin/zsh -c \
  "source /opt/ros/humble/setup.zsh >/dev/null 2>&1; source ~/ros2_ws/install/setup.zsh >/dev/null 2>&1; exec ros2 launch bringup bringup.launch.py > /tmp/bringup.log 2>&1"
echo "  等待 45 秒（节点初始化 + DDS 发现）..."
sleep 45

log "3. 验证 ROS 栈"
docker exec turbopi sh -c 'ps -eo pid,stat,cmd | grep -cE "Z"' | sed 's/^/  僵尸数: /'
echo "--- 关键节点 ---"
docker exec turbopi ps -eo pid,stat,cmd 2>/dev/null | grep -E '[m]ecanum|[u]sb_cam|[r]os_robot|[w]eb_video' | head -6
echo "--- /cmd_vel ---"
docker exec turbopi zsh -c "$SRC; timeout 25 ros2 topic info /cmd_vel 2>&1" 2>/dev/null | tr -d '\r' | head -4
echo "--- 快照接口 ---"
docker exec turbopi sh -c 'C=$(curl -s -o /dev/null -w "%{http_code}" --max-time 8 "http://127.0.0.1:8080/snapshot?topic=/image_raw" 2>/dev/null); echo "  HTTP $C"'

log "4. 启动设备程序"
docker exec -u root turbopi pkill -f turpi_device.py 2>/dev/null
sleep 2
docker exec -d -u ubuntu -w /home/ubuntu turbopi /bin/zsh -c \
  "source ~/ros2_ws/.zshrc >/dev/null 2>&1; export PYTHONPATH=/opt/agh_mhs/python/src:\$PYTHONPATH; cd /tmp && exec python3 -u /tmp/turpi_device.py $HUB >> /tmp/turpi.log 2>&1"
sleep 12

log "5. 验证设备进程"
N=$(docker exec turbopi ps -eo cmd 2>/dev/null | grep -c '[t]urpi_device' || echo 0)
echo "  进程数: $N  ($([ "$N" -eq 1 ] && echo '✓' || echo '✗'))"
echo "--- 日志尾部 ---"
docker exec turbopi tail -8 /tmp/turpi.log 2>/dev/null | sed 's/^/  /'

log "6. 结论"
echo "  僵尸=0 且 /cmd_vel 有订阅者 且 快照 200 且 进程=1 → 应恢复 available"
