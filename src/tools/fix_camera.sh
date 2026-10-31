#!/bin/bash
# 修复摄像头：僵尸 usb_cam 导致图像源无数据。
# 只重启 usb_cam 节点，不动整个栈。
set -u
SRC='source /opt/ros/humble/setup.zsh >/dev/null 2>&1; source /home/ubuntu/ros2_ws/install/setup.zsh >/dev/null 2>&1'

echo "===== 1. 现状 ====="
docker exec turbopi ps -eo pid,stat,cmd 2>/dev/null | grep '[u]sb_cam'

echo
echo "===== 2. 清掉僵尸 + 用 ros2 run 单独拉起 usb_cam ====="
docker exec -u root turbopi pkill -9 -f usb_cam 2>/dev/null
sleep 3
echo "  清理后: $(docker exec turbopi ps -eo cmd 2>/dev/null | grep -c '[u]sb_cam')"

docker exec -d -u ubuntu -w /home/ubuntu turbopi /bin/zsh -c \
  'source /opt/ros/humble/setup.zsh >/dev/null 2>&1; source ~/ros2_ws/install/setup.zsh >/dev/null 2>&1; V4L2_CAMERA=$(v4l2-ctl --list-devices 2>/dev/null | grep -A2 -i "icspring\|usb" | grep -o "/dev/video[0-9]*" | head -1); export V4L2_CAMERA=${V4L2_CAMERA:-/dev/video0}; echo "using $V4L2_CAMERA"; exec ros2 run usb_cam usb_cam_node_exe --ros-args -r __node:=usb_cam --params-file /home/ubuntu/ros2_ws/src/peripherals/config/usb_cam_param.yaml > /tmp/usbcam.log 2>&1'
echo "  已拉起，等 12 秒"
sleep 12

echo
echo "===== 3. 验证 ====="
docker exec turbopi ps -eo pid,stat,cmd 2>/dev/null | grep '[u]sb_cam'
echo "--- 日志 ---"
docker exec turbopi tail -8 /tmp/usbcam.log 2>/dev/null | sed 's/^/  /'
echo "--- 话题发布者 ---"
docker exec turbopi zsh -c "$SRC; timeout 20 ros2 topic info /camera/image_raw 2>&1" 2>&1 | tr -d '\r' | head -4

echo
echo "===== 4. 帧率实测 ====="
docker exec turbopi zsh -c "$SRC; timeout 20 ros2 topic hz /camera/image_raw 2>&1" 2>&1 | tr -d '\r' | head -5
