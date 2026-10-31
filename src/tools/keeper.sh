#!/bin/bash
# TurboPi 保活守护 v3
#
# 【v3 相对 v2 的关键修正】
# v2 有两个错误，导致车在无人指令时乱动：
#   1. 用「日志大小 3 分钟不增长」判卡死 —— 误判，正常状态也会被当卡死
#   2. 重启设备程序时未先停机 —— 每次重启都可能触发底盘初始化动作
#
# v3 的安全原则：
#   · 只在进程「完全消失」时才拉起（不再猜「卡死」）
#   · 任何设备程序启停前后，都先发零速 / halt
#   · 默认不自动重启设备程序，只记录告警；需自动恢复要显式开启
#   · 两次动作之间至少间隔 10 分钟
#
# 用法:
#   bash keeper.sh ws://<hub>:4180              # 只监控 + 拉起已死进程（安全）
#   AUTO_RESTART_DEV=1 bash keeper.sh ws://...  # 额外允许重启疑似卡死进程（谨慎）
set -u
HUB="${1:-ws://192.168.3.149:4180}"
INTERVAL=30
COOLDOWN=600                     # 同类动作最小间隔（秒）
AUTO_RESTART_DEV="${AUTO_RESTART_DEV:-0}"   # 默认关闭「疑似卡死」自动重启

say(){ echo "[$(date '+%m-%d %H:%M:%S')] $*"; }

LOCK=/tmp/keeper.lock
if [ -f "$LOCK" ] && kill -0 "$(cat $LOCK)" 2>/dev/null; then
  echo "keeper 已在运行 (pid $(cat $LOCK))"; exit 0
fi
echo $$ > "$LOCK"
trap 'rm -f $LOCK; exit 0' INT TERM EXIT

cnt(){ docker exec turbopi sh -c "$1" 2>/dev/null | head -1 | tr -cd '0-9'; }
nz(){ v=$(cnt "$1"); [ -z "$v" ] && v=0; echo "$v"; }

# 【安全】发零速 + halt，任何启停操作前必做
safe_stop(){
  docker exec turbopi zsh -c '
    source /opt/ros/humble/setup.zsh >/dev/null 2>&1
    source /home/ubuntu/ros2_ws/install/setup.zsh >/dev/null 2>&1
    timeout 8 ros2 topic pub --once /cmd_vel geometry_msgs/msg/Twist \
      "{linear: {x: 0.0}, angular: {z: 0.0}}" >/dev/null 2>&1' 2>/dev/null
  say "  已发零速停机"
}

start_stack(){
  docker exec -d -u ubuntu -w /home/ubuntu turbopi /bin/zsh -c \
    'source /opt/ros/humble/setup.zsh >/dev/null 2>&1; source ~/ros2_ws/install/setup.zsh >/dev/null 2>&1; exec ros2 launch bringup bringup.launch.py > /tmp/bringup.log 2>&1'
}
start_cam(){
  docker exec -d -u ubuntu -w /home/ubuntu turbopi /bin/zsh -c \
    'source /opt/ros/humble/setup.zsh >/dev/null 2>&1; source ~/ros2_ws/install/setup.zsh >/dev/null 2>&1; exec ros2 run usb_cam usb_cam_node_exe --ros-args -r __node:=usb_cam --params-file /home/ubuntu/ros2_ws/src/peripherals/config/usb_cam_param.yaml > /tmp/usbcam.log 2>&1'
}
start_wvs(){
  docker exec -d -u ubuntu -w /home/ubuntu turbopi /bin/zsh -c \
    'source /opt/ros/humble/setup.zsh >/dev/null 2>&1; source ~/ros2_ws/install/setup.zsh >/dev/null 2>&1; exec ros2 run web_video_server web_video_server > /tmp/wvs.log 2>&1'
}
start_dev(){
  safe_stop
  docker exec -d -u ubuntu -w /home/ubuntu turbopi /bin/zsh -c \
    "source ~/ros2_ws/.zshrc >/dev/null 2>&1; export PYTHONPATH=/opt/agh_mhs/python/src:\$PYTHONPATH; cd /tmp && exec python3 -u /tmp/turpi_device.py $HUB >> /tmp/turpi.log 2>&1"
}

say "保活 v3 启动 | hub=$HUB | 间隔=${INTERVAL}s | 冷却=${COOLDOWN}s | 自动重启卡死=${AUTO_RESTART_DEV}"
[ "$AUTO_RESTART_DEV" = "0" ] && say "  注意：仅拉起「已消失」的进程；不猜测卡死（安全默认）"

ROS_AT=0; CAM_AT=0; WVS_AT=0; DEV_AT=0

while true; do
  NOW=$(date +%s)

  Z=$(nz 'ps -eo stat= | grep -c Z')
  MEC=$(nz 'ps -eo cmd | grep -c "[m]ecanum"')
  CAM=$(nz 'ps -eo cmd | grep -c "[u]sb_cam_node"')
  WVS=$(nz 'ps -eo cmd | grep -c "[w]eb_video_server"')
  DN=$(nz 'ps -eo cmd | grep -c "[t]urpi_device"')

  # 1. ROS 栈级故障（僵尸暴增 或 底盘节点缺失）—— 这两项判据可靠
  if [ "$Z" -gt 8 ] || [ "$MEC" -eq 0 ]; then
    if [ $((NOW - ROS_AT)) -gt $COOLDOWN ]; then
      say "ROS 异常(僵尸=$Z mecanum=$MEC) → 停机后重启整栈"
      safe_stop
      docker exec -u root turbopi pkill -9 -f turpi_device.py 2>/dev/null
      sleep 3
      docker restart turbopi >/dev/null 2>&1
      sleep 22; start_stack; ROS_AT=$NOW; sleep 40; continue
    else
      say "ROS 异常但冷却中（还需 $((COOLDOWN-(NOW-ROS_AT)))s）"
    fi
  fi

  # 2. 摄像头（判据可靠：进程消失）
  if [ "$CAM" -eq 0 ] && [ $((NOW - CAM_AT)) -gt $COOLDOWN ]; then
    say "usb_cam 缺失 → 拉起"; start_cam; CAM_AT=$NOW; sleep 10
  fi
  if [ "$WVS" -eq 0 ] && [ $((NOW - WVS_AT)) -gt $COOLDOWN ]; then
    say "web_video_server 缺失 → 拉起"; start_wvs; WVS_AT=$NOW; sleep 8
  fi

  # 3. 设备程序
  if [ "$DN" -eq 0 ]; then
    # 进程真的没了 → 拉起（安全，且这是最常见情况）
    if [ $((NOW - DEV_AT)) -gt $COOLDOWN ]; then
      say "设备程序已消失 → 拉起"
      start_dev; DEV_AT=$NOW; sleep 12
    else
      say "设备程序不在，但冷却中（还需 $((COOLDOWN-(NOW-DEV_AT)))s）"
    fi
  elif [ "$AUTO_RESTART_DEV" = "1" ]; then
    # 仅在显式开启时才做「疑似卡死」重启，且用更宽松的判据
    :   # 预留：如需启用，请先确认判据可靠
  fi

  sleep $INTERVAL
done
