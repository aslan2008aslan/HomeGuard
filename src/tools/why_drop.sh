#!/bin/bash
# 掉线根因系统性取证
set -u
echo "########## 1. 系统资源 ##########"
uptime | sed 's/^/  /'
free -m | head -2 | sed 's/^/  /'
echo "  温度: $(vcgencmd measure_temp 2>/dev/null | cut -d= -f2)"
echo "  欠压: $(vcgencmd get_throttled 2>/dev/null)"
echo "  SD 卡: $(df -h / | tail -1 | awk '{print $3"/"$2" ("$5")"}')"

echo
echo "########## 2. 内存压力（容器内）##########"
docker exec turbopi sh -c 'free -m | head -2; echo "  交换:"; cat /proc/swaps 2>/dev/null | tail -2'

echo
echo "########## 3. OOM 记录（关键：进程被杀？）##########"
echo "--- 内核 OOM ---"
sudo dmesg 2>/dev/null | grep -i 'oom\|killed process' | tail -8 || echo "  无记录"
echo "--- journald OOM ---"
sudo journalctl -k --since "2 hours ago" --no-pager 2>/dev/null | grep -i 'oom\|killed' | tail -6 || echo "  无"

echo
echo "########## 4. 网络稳定性（掉线常见真因）##########"
echo "--- wlan0 接口错误 ---"
ip -s link show wlan0 2>/dev/null | tail -4
echo "--- 无线信号 ---"
iwconfig wlan0 2>/dev/null | grep -E 'Quality|Signal|Bit Rate' || echo "  iwconfig 不可用"
echo "--- 掉线重连记录 ---"
sudo journalctl -u wpa_supplicant --since "2 hours ago" --no-pager 2>/dev/null | grep -iE 'disconnect|reconnect|deauth|associated' | tail -8 || echo "  无 wpa_supplicant 记录"
echo "--- DHCP 续约 ---"
sudo journalctl --since "2 hours ago" --no-pager 2>/dev/null | grep -iE 'dhcp|dhcpcd' | tail -5 || echo "  无"

echo
echo "########## 5. 容器重启历史（关键）##########"
docker inspect turbopi --format '  当前启动: {{.State.StartedAt}}
  重启次数: {{.RestartCount}}' 2>/dev/null
echo "--- 容器事件 ---"
docker events --since 2h --until 0s --filter container=turbopi 2>/dev/null | head -10 || echo "  无事件"

echo
echo "########## 6. 设备程序崩溃记录 ##########"
echo "--- core 转储 ---"
docker exec turbopi sh -c 'ls -lh /tmp/core* 2>/dev/null' || echo "  无"
echo "--- turpi.log 中的异常 ---"
docker exec turbopi sh -c 'grep -iE "error|traceback|exception|kill|abort|segfault" /tmp/turpi.log 2>/dev/null | tail -8' || echo "  无"
echo "--- 日志行数与最后修改 ---"
docker exec turbopi sh -c 'wc -l < /tmp/turpi.log; stat -c "%y" /tmp/turpi.log'

echo
echo "########## 7. keeper 干预历史 ##########"
sudo journalctl -u turpi-keeper --since "3 hours ago" --no-pager 2>/dev/null | grep -E '拉起|重启|停机|异常' | tail -12 || echo "  无"

echo
echo "########## 8. DDS / 网络配置 ##########"
echo "--- 网络接口 ---"
ip -4 addr show 2>/dev/null | grep -E '^[0-9]|inet ' | head -10
echo "--- ROS 相关环境 ---"
docker exec turbopi sh -c 'env | grep -E "ROS_|RMW_|CYCLONE|FASTRTPS" | head -8' || echo "  无"

echo
echo "########## 9. 时间同步（DDS 对时间敏感）##########"
timedatectl 2>/dev/null | head -6
echo "--- 时钟跳变 ---"
sudo journalctl --since "2 hours ago" --no-pager 2>/dev/null | grep -iE 'time.*jump|clock.*step' | tail -4 || echo "  无"
