#!/bin/bash
# 重启后全面能力自检
set -u
SRC='source /opt/ros/humble/setup.zsh >/dev/null 2>&1; source /home/ubuntu/ros2_ws/install/setup.zsh >/dev/null 2>&1'
PASS=0; FAIL=0
ck(){ if [ "$2" = "1" ]; then echo "  ✅ $1"; PASS=$((PASS+1)); else echo "  ❌ $1  ($3)"; FAIL=$((FAIL+1)); fi }

echo "########## 0. 系统 ##########"
uptime | sed 's/^/  /'
echo "  温度: $(vcgencmd measure_temp 2>/dev/null | cut -d= -f2)"
echo "  欠压: $(vcgencmd get_throttled 2>/dev/null)"

echo
echo "########## 1. 串口 + 电池 ##########"
BAT=$(PYTHONPATH=/home/pi/demo timeout 20 python3 -c "
import serial, time
s=serial.Serial('/dev/ttyAMA0',1000000,timeout=0.5)
for _ in range(3): s.reset_input_buffer(); time.sleep(0.3)
s.close()
import ros_robot_controller_sdk as rrc
b=rrc.Board(); b.enable_reception(); time.sleep(1.5)
vs=[b.get_battery() for _ in range(8)]
ok=[v for v in vs if v is not None]
print(ok[0] if ok else 'NONE')
" 2>/dev/null | tail -1)
echo "  电池读数: $BAT"
[ "$BAT" != "NONE" ] && [ -n "$BAT" ] && ck "串口/电池" 1 || ck "串口/电池" 0 "读不到"

echo
echo "########## 2. ROS 栈 ##########"
Z=$(docker exec turbopi sh -c 'ps -eo stat= | grep -c Z' 2>/dev/null | head -1 | tr -cd '0-9')
echo "  僵尸进程: ${Z:-?}"
[ "${Z:-9}" -le 3 ] && ck "无僵尸堆积" 1 || ck "无僵尸堆积" 0 "僵尸=$Z"
MEC=$(docker exec turbopi sh -c 'ps -eo cmd | grep -c "[m]ecanum"' 2>/dev/null | head -1 | tr -cd '0-9')
[ "${MEC:-0}" -ge 1 ] && ck "mecanum_chassis_node" 1 || ck "mecanum_chassis_node" 0 "缺失"
CV=$(docker exec turbopi zsh -c "$SRC; timeout 20 ros2 topic info /cmd_vel 2>&1" 2>/dev/null | tr -d '\r' | grep -c 'Subscription count: 1')
[ "$CV" -ge 1 ] && ck "/cmd_vel 有订阅者" 1 || ck "/cmd_vel 有订阅者" 0 "无订阅者"

echo
echo "########## 3. 摄像头 ##########"
CAM=$(docker exec turbopi sh -c 'ps -eo cmd | grep -c "[u]sb_cam_node"' 2>/dev/null | head -1 | tr -cd '0-9')
[ "${CAM:-0}" -ge 1 ] && ck "usb_cam 进程" 1 || ck "usb_cam 进程" 0 "缺失"
IR=$(docker exec turbopi zsh -c "$SRC; timeout 20 ros2 topic info /image_raw 2>&1" 2>/dev/null | tr -d '\r' | grep -c 'Publisher count: 1')
[ "$IR" -ge 1 ] && ck "/image_raw 有发布者" 1 || ck "/image_raw 有发布者" 0 "无发布者"
WVS=$(docker exec turbopi sh -c 'ps -eo cmd | grep -c "[w]eb_video_server"' 2>/dev/null | head -1 | tr -cd '0-9')
[ "${WVS:-0}" -ge 1 ] && ck "web_video_server 进程" 1 || ck "web_video_server 进程" 0 "缺失"
HTTP=$(docker exec turbopi sh -c 'curl -s -o /tmp/t.jpg -w "%{http_code}" --max-time 8 "http://127.0.0.1:8080/snapshot?topic=/image_raw" 2>/dev/null' 2>/dev/null | tr -cd '0-9')
SZ=$(docker exec turbopi sh -c 'wc -c < /tmp/t.jpg 2>/dev/null' 2>/dev/null | tr -cd '0-9')
echo "  快照: HTTP $HTTP, ${SZ:-0} 字节"
[ "$HTTP" = "200" ] && [ "${SZ:-0}" -gt 1000 ] && ck "快照接口" 1 || ck "快照接口" 0 "HTTP=$HTTP"

echo
echo "########## 4. 设备程序 ##########"
DN=$(docker exec turbopi sh -c 'ps -eo cmd | grep -c "[t]urpi_device"' 2>/dev/null | head -1 | tr -cd '0-9')
[ "${DN:-0}" -eq 1 ] && ck "设备程序唯一(=$DN)" 1 || ck "设备程序唯一" 0 "数量=$DN"
echo "  --- 日志尾部 ---"
docker exec turbopi tail -6 /tmp/turpi.log 2>/dev/null | sed 's/^/    /'

echo
echo "########## 5. 保活服务 ##########"
EN=$(systemctl is-enabled turpi-keeper 2>/dev/null)
AC=$(systemctl is-active turpi-keeper 2>/dev/null)
echo "  开机自启: $EN / 状态: $AC"
[ "$AC" = "active" ] && ck "keeper 运行中" 1 || ck "keeper 运行中" 0 "$AC"

echo
echo "########## 6. 音频 ##########"
docker exec turbopi sh -c 'grep -c "speaker unmute ok" /tmp/turpi.log 2>/dev/null' 2>/dev/null | tr -cd '0-9' | sed 's/^/  扬声器初始化次数: /'

echo
echo "======================================"
echo "  通过: $PASS   失败: $FAIL"
echo "  工作区时间: $(date '+%H:%M:%S')"
echo "======================================"
