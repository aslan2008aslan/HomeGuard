#!/bin/bash
set -u
SRC='source /opt/ros/humble/setup.zsh >/dev/null 2>&1; source /home/ubuntu/ros2_ws/install/setup.zsh >/dev/null 2>&1'

echo "===== 1. /image_raw 是否有数据 ====="
docker exec turbopi zsh -c "$SRC; timeout 20 ros2 topic info /image_raw 2>&1" 2>/dev/null | tr -d '\r' | head -4

echo
echo "===== 2. web_video_server 是否在跑 ====="
docker exec turbopi ps -eo pid,stat,cmd 2>/dev/null | grep -E '[w]eb_video' || echo "  未运行"

echo
echo "===== 3. 快照接口实测 ====="
docker exec turbopi sh -c '
for url in "http://127.0.0.1:8080/snapshot?topic=/image_raw" "http://127.0.0.1:8080/snapshot?topic=/image_raw/compressed"; do
  code=$(curl -s -o /tmp/snap.jpg -w "%{http_code}" --max-time 6 "$url" 2>/dev/null)
  size=$(wc -c < /tmp/snap.jpg 2>/dev/null || echo 0)
  echo "  $url"
  echo "    HTTP $code, $size 字节"
done'

echo
echo "===== 4. 8080 端口占用 ====="
docker exec turbopi sh -c 'netstat -tlnp 2>/dev/null | grep 8080 || ss -tlnp 2>/dev/null | grep 8080 || echo "  8080 无监听"'

echo
echo "===== 5. 若快照失败，重启 web_video_server ====="
CODE=$(docker exec turbopi sh -c 'curl -s -o /dev/null -w "%{http_code}" --max-time 5 "http://127.0.0.1:8080/snapshot?topic=/image_raw" 2>/dev/null' 2>/dev/null || echo 000)
if [ "$CODE" != "200" ]; then
  echo "  快照返回 $CODE，重启 web_video_server..."
  docker exec -u root turbopi pkill -9 -f web_video_server 2>/dev/null
  sleep 3
  docker exec -d -u ubuntu -w /home/ubuntu turbopi /bin/zsh -c \
    'source /opt/ros/humble/setup.zsh >/dev/null 2>&1; source ~/ros2_ws/install/setup.zsh >/dev/null 2>&1; exec ros2 run web_video_server web_video_server > /tmp/wvs.log 2>&1'
  sleep 10
  echo "  重启后测试:"
  docker exec turbopi sh -c '
for url in "http://127.0.0.1:8080/snapshot?topic=/image_raw"; do
  code=$(curl -s -o /tmp/snap.jpg -w "%{http_code}" --max-time 8 "$url" 2>/dev/null)
  size=$(wc -c < /tmp/snap.jpg 2>/dev/null || echo 0)
  echo "    HTTP $code, $size 字节"
done'
  docker exec turbopi tail -5 /tmp/wvs.log 2>/dev/null | sed 's/^/    /'
fi
