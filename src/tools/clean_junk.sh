#!/bin/bash
# 清理车上缓冲垃圾。保守策略：只删明确的临时产物，不碰运行中的东西。
set -u
BEFORE=$(df -k / | awk 'NR==2{print $3}')
echo "清理前已用: $((BEFORE/1024)) MB"

echo
echo "===== 1. 核心转储（崩溃残留）====="
for f in /tmp/core /tmp/*.core; do
  [ -f "$f" ] || continue
  SZ=$(du -h "$f" 2>/dev/null | cut -f1)
  echo "  删除 $f ($SZ)"
  docker exec -u root turbopi rm -f "$f" 2>/dev/null
  sudo rm -f "$f" 2>/dev/null
done
# 关掉容器内 core dump，防止再生成
docker exec -u root turbopi sh -c 'echo 0 > /proc/sys/kernel/core_pattern 2>/dev/null' 2>/dev/null || true

echo
echo "===== 2. 过期的调试日志（保留 turpi.log / keeper.log / bringup.log）====="
docker exec turbopi sh -c '
for f in /tmp/cam.log /tmp/cam2.log /tmp/camok.log /tmp/cmdvel_echo.log \
         /tmp/motor_echo.log /tmp/sweep.log /tmp/tA.log /tmp/tB.log \
         /tmp/bringup2.log /tmp/usbcam.log; do
  [ -f "$f" ] || continue
  SZ=$(du -h "$f" | cut -f1)
  # 只删 1 天前的
  if [ -n "$(find "$f" -mtime +0 2>/dev/null)" ]; then
    echo "  删除 $f ($SZ)"
    rm -f "$f"
  else
    echo "  保留 $f ($SZ) — 今天还在写"
  fi
done'

echo
echo "===== 3. wvs.log 截断（web_video_server 刷得快）====="
docker exec turbopi sh -c '
if [ -f /tmp/wvs.log ]; then
  SZ=$(du -h /tmp/wvs.log | cut -f1)
  echo "  wvs.log 当前 $SZ → 截断为最近 100 行"
  tail -100 /tmp/wvs.log > /tmp/wvs.log.tmp && mv /tmp/wvs.log.tmp /tmp/wvs.log
fi'
sudo sh -c 'if [ -f /tmp/wvs.log ]; then echo "  宿主 wvs.log $(du -h /tmp/wvs.log|cut -f1) → 清空"; : > /tmp/wvs.log; fi' 2>/dev/null

echo
echo "===== 4. ROS 日志（保留最近）====="
docker exec turbopi sh -c '
if [ -d /home/ubuntu/.ros/log ]; then
  SZ=$(du -sh /home/ubuntu/.ros/log | cut -f1)
  echo "  .ros/log 当前 $SZ"
  # 删除 2 天前的日志目录
  find /home/ubuntu/.ros/log -maxdepth 1 -type d -mtime +1 -exec rm -rf {} + 2>/dev/null
  find /home/ubuntu/.ros/log -maxdepth 1 -type f -mtime +1 -delete 2>/dev/null
  echo "  清理后 $(du -sh /home/ubuntu/.ros/log | cut -f1)"
fi'

echo
echo "===== 5. 快照残留 ====="
docker exec turbopi sh -c 'rm -f /tmp/*.jpg /tmp/s.jpg /tmp/snap* 2>/dev/null; echo "  已清"'

echo
echo "===== 6. 我上传的排查脚本（保留 keeper 相关）====="
echo "  策略：/tmp 下的 .sh 是工具，下次还要用 → 保留"
echo "  但删除已失效的："
for f in /tmp/dds_diag.sh /tmp/find_cam_topic.sh /tmp/fix_ros_stack.sh \
         /tmp/diag_offline.sh /tmp/kick_device.sh /tmp/scan_junk.sh; do
  [ -f "$f" ] || continue
  echo "  删除 $f"
  sudo rm -f "$f"
done

echo
echo "===== 7. 确认运行中的东西没被影响 ====="
echo "--- keeper ---"
ps -eo pid,args | grep 'bash /tmp/keeper.sh' | grep -v grep || echo "  ⚠ keeper 不在了！"
echo "--- 设备程序 ---"
docker exec turbopi sh -c 'ps -eo cmd | grep "[t]urpi_device" | head -1' || echo "  ⚠ 设备程序不在了"
echo "--- usb_cam ---"
docker exec turbopi sh -c 'ps -eo cmd | grep -c "[u]sb_cam_node"' | sed 's/^/  /'
echo "--- 快照 ---"
docker exec turbopi sh -c 'curl -s -o /tmp/t.jpg -w "  HTTP %{http_code}\n" --max-time 8 "http://127.0.0.1:8080/snapshot?topic=/image_raw"'

echo
AFTER=$(df -k / | awk 'NR==2{print $3}')
echo "清理后已用: $((AFTER/1024)) MB  (释放 $(( (BEFORE-AFTER)/1024 )) MB)"
