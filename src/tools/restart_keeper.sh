#!/bin/bash
# 重启 keeper（避免 pkill 误杀自身：用 PID 文件）
set -u
echo "--- 停旧 keeper ---"
if [ -f /tmp/keeper.lock ]; then
  OLD=$(cat /tmp/keeper.lock)
  if kill -0 "$OLD" 2>/dev/null; then
    kill -9 "$OLD" 2>/dev/null && echo "  已杀 pid=$OLD"
  fi
  rm -f /tmp/keeper.lock
fi
# 兜底：按完整路径杀
for p in $(ps -eo pid,args | awk '/bash \/tmp\/keeper\.sh/ {print $1}'); do
  kill -9 "$p" 2>/dev/null && echo "  兜底杀 $p"
done
sleep 2
echo "  剩余: $(ps -eo args | grep -c 'bash /tmp/keeper\.sh')"

echo "--- 启动新 keeper ---"
nohup setsid bash /tmp/keeper.sh ws://192.168.3.149:4180 > /tmp/keeper.log 2>&1 < /dev/null &
sleep 8
echo "--- 进程 ---"
ps -eo pid,args | grep 'bash /tmp/keeper\.sh' | grep -v grep || echo "  未启动"
echo "--- 日志 ---"
cat /tmp/keeper.log | head -6
