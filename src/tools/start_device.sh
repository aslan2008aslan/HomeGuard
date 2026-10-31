#!/bin/bash
# Run ON the Raspberry Pi. Restart the device with logging that CANNOT be swallowed,
# then watch it long enough to catch the reconnect loop.
#
# Why the previous redirects failed: `> /tmp/turpi.log` after `docker exec -d ...`
# redirects DOCKER'S OWN stdout (which is empty), not the container process output.
# The correct place is INSIDE the quoted shell string, escaped so the remote shell
# performs it -- i.e. `... exec python3 ... > /tmp/turpi.log 2>&1` as part of -c.
HUB="ws://192.168.3.149:4180"
LOG=/tmp/turpi.log

echo "=== stop leftovers ==="
for p in $(docker exec turbopi pgrep -f turpi_device.py 2>/dev/null); do
  echo "  killing $p"; docker exec -u root turbopi kill -9 "$p" 2>/dev/null
done
sleep 2

# Fresh log so old contents can't be mistaken for new output.
docker exec -u root turbopi sh -c "rm -f $LOG; touch $LOG; chmod 666 $LOG"
echo "  log reset"

echo
echo "=== start (redirect INSIDE the -c string, where the remote shell does it) ==="
docker exec -d -u ubuntu -w /home/ubuntu turbopi /bin/zsh -c \
  "source ~/ros2_ws/.zshrc >/dev/null 2>&1; export PYTHONPATH=/opt/agh_mhs/python/src:\$PYTHONPATH; cd /tmp && exec python3 -u /tmp/turpi_device.py $HUB >> $LOG 2>&1"

echo
echo "=== watch log growth over ~45s (catches the reconnect loop) ==="
for i in 1 2 3 4 5 6 7 8 9; do
  sleep 5
  SZ=$(docker exec turbopi wc -c < $LOG 2>/dev/null || echo 0)
  NS=$(ss -tn 2>/dev/null | grep -c ":4180" || echo 0)
  echo "  t=$((i*5))s  log=${SZ}B  sockets=${NS}"
done

echo
echo "=== process ==="
docker exec turbopi ps -o pid,ppid,stat,etime,cmd -C python3 2>/dev/null | grep -E 'PID|turpi_device' || echo '  NO PROCESS'
echo
echo "=== log contents ==="
docker exec turbopi cat $LOG 2>/dev/null | tail -25
echo
echo "=== sockets (multiple = reconnect loop) ==="
ss -tn 2>/dev/null | grep ":4180" || echo '  none'
