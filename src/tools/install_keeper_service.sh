#!/bin/bash
# 安装 keeper 为 systemd 开机自启服务
set -eu

HUB="${1:-ws://192.168.3.149:4180}"
DIR=/home/pi/turbopi_agh

echo "===== 1. 准备目录与文件 ====="
sudo mkdir -p "$DIR"
sudo cp /tmp/keeper.sh "$DIR/keeper.sh"
sudo chmod +x "$DIR/keeper.sh"
sudo sed -i 's/\r$//' "$DIR/keeper.sh"
echo "  $DIR/keeper.sh"

echo
echo "===== 2. 停掉手动跑的 keeper（避免冲突）====="
if [ -f /tmp/keeper.lock ]; then
  OLD=$(cat /tmp/keeper.lock)
  sudo kill -9 "$OLD" 2>/dev/null && echo "  已停手动 keeper pid=$OLD" || true
  sudo rm -f /tmp/keeper.lock
fi
for p in $(ps -eo pid,args | awk '/bash \/tmp\/keeper\.sh/ {print $1}'); do
  sudo kill -9 "$p" 2>/dev/null && echo "  兜底停 $p" || true
done
sleep 2

echo
echo "===== 3. 装 systemd 服务 ====="
sudo cp /tmp/turpi-keeper.service /etc/systemd/system/turpi-keeper.service
# 写入 hub 地址
sudo sed -i "s|Environment=TURPI_HUB=.*|Environment=TURPI_HUB=$HUB|" /etc/systemd/system/turpi-keeper.service
sudo sed -i 's/\r$//' /etc/systemd/system/turpi-keeper.service
sudo systemctl daemon-reload
echo "  已 daemon-reload"

echo
echo "===== 4. 开机自启 ====="
sudo systemctl enable turpi-keeper.service 2>&1 | tail -3

echo
echo "===== 5. 启动 ====="
sudo systemctl restart turpi-keeper.service
sleep 8

echo
echo "===== 6. 验证 ====="
echo "--- 服务状态 ---"
sudo systemctl is-enabled turpi-keeper.service | sed 's/^/  开机自启: /'
sudo systemctl is-active  turpi-keeper.service | sed 's/^/  当前状态: /'
echo "--- 进程 ---"
ps -eo pid,args | grep '[k]eeper.sh' || echo "  ⚠ 无进程"
echo "--- 最近日志 ---"
sudo journalctl -u turpi-keeper -n 8 --no-pager 2>/dev/null | tail -8

echo
echo "===== 7. 关键安全项确认 ====="
echo "  hub 地址: $(grep TURPI_HUB /etc/systemd/system/turpi-keeper.service | cut -d= -f3)"
echo "  AUTO_RESTART_DEV 未设 → 仅拉起已消失的进程（安全默认）"
