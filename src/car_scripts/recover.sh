#!/bin/bash
# Recovery script: bring the ROS2 stack back up after the container is restarted.
# Run this ON THE PI (locally or over SSH) if the robot stops responding.
#
# Why this is needed: the turbopi container's main process is `tail -f /dev/null`,
# so restarting the container does NOT start ROS2. The vendor script does that.
# The systemd unit (start_node.service) points at a path that does not exist
# (/home/pi/armpi_fpv/start_node.sh), so it cannot be relied on.

set -u

CONTAINER=turbopi
VENDOR_START=/home/pi/turbopi/start_node.sh

echo "=== 1. container state ==="
docker ps -a --filter "name=$CONTAINER" --format '{{.Names}} {{.Status}}'

echo
echo "=== 2. start the container if it is not running ==="
if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "container not running; starting"
  docker start "$CONTAINER"
  sleep 5
else
  echo "container already running"
fi

echo
echo "=== 3. is ROS2 already up inside it? ==="
if docker exec -u ubuntu "$CONTAINER" /bin/bash -lc 'pgrep -f "ros2 launch bringup" >/dev/null'; then
  echo "bringup already running; nothing to do"
else
  echo "bringup not running; launching the vendor script"
  if [ -f "$VENDOR_START" ]; then
    bash "$VENDOR_START" >/tmp/vendor_start.log 2>&1 &
    echo "launched in background; log: /tmp/vendor_start.log"
  else
    echo "VENDOR SCRIPT MISSING: $VENDOR_START"
    echo "starting bringup directly instead"
    docker exec -d -u ubuntu -w /home/ubuntu "$CONTAINER" \
      /bin/zsh -c 'source ~/.zshrc && ros2 launch bringup bringup.launch.py' \
      >/tmp/direct_start.log 2>&1
  fi
  sleep 15
fi

echo
echo "=== 4. verify ==="
docker exec -u ubuntu "$CONTAINER" /bin/bash -lc 'ps -ef | grep -E "bringup|ros_robot_controller|mecanum|usb_cam" | grep -v grep' | head -10

echo
echo "=== 5. serial port holder ==="
sudo lsof /dev/ttyAMA0 2>/dev/null | tail -2 || echo "(nobody holds it)"

echo
echo "=== 6. camera service ==="
curl -s -o /dev/null -w "web_video_server http=%{http_code}\n" \
  'http://127.0.0.1:8080/snapshot?topic=/image_raw' 2>/dev/null

echo
echo "RECOVER_DONE"
