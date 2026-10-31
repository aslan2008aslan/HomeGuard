#!/bin/bash
set -u
echo "--- 快照接口 ---"
docker exec turbopi sh -c 'curl -s -o /tmp/s.jpg -w "  HTTP %{http_code}, " --max-time 8 "http://127.0.0.1:8080/snapshot?topic=/image_raw"; wc -c < /tmp/s.jpg'
echo "--- 僵尸数 ---"
docker exec turbopi sh -c 'ps -eo stat= | grep -c Z'
echo "--- 设备进程 ---"
docker exec turbopi ps -eo pid,etime,cmd 2>/dev/null | grep '[t]urpi_device' | head -2
echo "--- 关键节点 ---"
docker exec turbopi ps -eo pid,stat,cmd 2>/dev/null | grep -E '[m]ecanum|[u]sb_cam|[w]eb_video' | head -4
