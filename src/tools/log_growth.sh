#!/bin/bash
set -u
LOG=/tmp/turpi.log

echo "===== 1. 日志现状 ====="
docker exec turbopi sh -c "wc -lc < $LOG" | awk '{print "  行数: "$1"  字节: "$2}'
docker exec turbopi sh -c "ls -lh $LOG"
echo "--- 磁盘余量 ---"
df -h / | tail -1 | awk '{print "  已用 "$3"/"$2" ("$5"), 可用 "$4}'

echo
echo "===== 2. 该消息的占比 ====="
docker exec turbopi sh -c "grep -c 'without a value yet' $LOG" | sed 's/^/  该消息行数: /'
docker exec turbopi sh -c "wc -l < $LOG" | sed 's/^/  总行数: /'

echo
echo "===== 3. 增长速率实测（30 秒）====="
A=$(docker exec turbopi sh -c "wc -c < $LOG" | tr -cd '0-9')
A2=$(docker exec turbopi sh -c "wc -l < $LOG" | tr -cd '0-9')
echo "  T0: $A 字节 / $A2 行"
sleep 30
B=$(docker exec turbopi sh -c "wc -c < $LOG" | tr -cd '0-9')
B2=$(docker exec turbopi sh -c "wc -l < $LOG" | tr -cd '0-9')
echo "  T30: $B 字节 / $B2 行"
echo "  → 增长 $((B-A)) 字节 / $((B2-A2)) 行 每 30 秒"
if [ $((B2-A2)) -gt 0 ]; then
  PERHOUR=$(( (B2-A2) * 120 ))
  echo "  → 折合每小时约 $PERHOUR 行"
  echo "  → 折合每天约 $((PERHOUR*24)) 行"
  # 假设每行 50 字节
  echo "  → 每天约 $(( PERHOUR*24*50 / 1048576 )) MB"
fi

echo
echo "===== 4. 这条消息是哪里打的 ====="
docker exec turbopi sh -c 'grep -n "without a value yet" /tmp/turpi_device_patched.py /tmp/turpi_device.py 2>/dev/null' || echo "  在设备程序里没找到（可能在 agnes_mhs 库）"
echo "--- 在 agnes_mhs 里找 ---"
docker exec turbopi sh -c 'grep -rn "without a value yet" /opt/agh_mhs/python/src 2>/dev/null | head -5'

echo
echo "===== 5. 为什么反复出现（battery 字段拿不到值）====="
docker exec turbopi sh -c 'grep -n "BATTERY_LOW_MV\|battery_percent\|wait_for_battery" /tmp/turpi_device_patched.py | head -8'

echo
echo "===== 6. 是否有 logrotate ====="
ls /etc/logrotate.d/ 2>/dev/null | head -5
echo "--- 容器内 ---"
docker exec turbopi sh -c 'ls /etc/logrotate.d/ 2>/dev/null | head -5 || echo "  无 logrotate"' 
echo "--- 我的 keeper 有没有清理逻辑 ---"
grep -c 'turpi.log' /home/pi/turbopi_agh/keeper.sh | sed 's/^/  keeper 中提到 turpi.log 次数: /'
