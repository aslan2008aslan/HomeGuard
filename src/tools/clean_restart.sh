#!/bin/bash
# Run ON the Raspberry Pi. KILL EVERY turpi_device.py process, in the container AND on
# the host, then verify nothing is left before starting exactly ONE.
#
# Root cause found: two processes with the SAME device id (turpi-01) were fighting.
# device.py L443: "replaced by another connection with the same id; not reconnecting"
# -> they kicked each other off in a loop, and one kept a socket open while doing nothing.
# This is why sockets appeared/disappeared and the log never advanced.

echo '=== BEFORE: every turpi_device process, container + host ==='
docker exec turbopi ps -eo pid,ppid,etime,cmd | grep turpi_device | grep -v grep || echo '  container: none'
ps -eo pid,ppid,etime,cmd | grep turpi_device | grep -v grep || echo '  host: none'

echo
echo '=== killing ALL of them ==='
# container side: match on the script path so we do not miss any spawn style
for p in $(docker exec turbopi ps -eo pid,cmd | grep 'turpi_device.py' | grep -v grep | awk '{print $1}'); do
  echo "  container kill $p"
  docker exec -u root turbopi kill -9 "$p" 2>/dev/null
done
# host side: in case an old process was started outside the container
for p in $(ps -eo pid,cmd | grep 'turpi_device.py' | grep -v grep | awk '{print $1}'); do
  echo "  host kill $p"
  sudo kill -9 "$p" 2>/dev/null
done
sleep 3

echo
echo '=== AFTER: must be completely empty ==='
docker exec turbopi ps -eo pid,ppid,cmd | grep turpi_device | grep -v grep && echo '  !! STILL RUNNING (container)' || echo '  container: clean'
ps -eo pid,cmd | grep turpi_device | grep -v grep && echo '  !! STILL RUNNING (host)' || echo '  host: clean'

echo
echo '=== sockets to hub must be gone ==='
ss -tn 2>/dev/null | grep ":4180" && echo '  !! socket still present' || echo '  no sockets (good)'

echo
echo '=== now start EXACTLY ONE ==='
docker exec -d -u ubuntu -w /home/ubuntu turbopi /bin/zsh -c \
  "source ~/ros2_ws/.zshrc >/dev/null 2>&1; export PYTHONPATH=/opt/agh_mhs/python/src:\$PYTHONPATH; cd /tmp && exec python3 -u /tmp/turpi_device.py ws://192.168.3.149:4180 >> /tmp/turpi.log 2>&1"

sleep 12
echo
echo '=== verify: exactly ONE process, PPID 0, and a growing log ==='
docker exec turbopi ps -eo pid,ppid,etime,cmd | grep turpi_device | grep -v grep || echo '  NO PROCESS'
echo "  process count: $(docker exec turbopi ps -eo cmd | grep -c 'turpi_device.py' )"
echo
A=$(docker exec turbopi wc -c < /tmp/turpi.log 2>/dev/null || echo 0)
sleep 8
B=$(docker exec turbopi wc -c < /tmp/turpi.log 2>/dev/null || echo 0)
echo "  log bytes: $A -> $B   (must grow)"
docker exec turbopi tail -4 /tmp/turpi.log 2>/dev/null
echo
echo '=== sockets ==='
ss -tn 2>/dev/null | grep ":4180" || echo '  none'
