#!/bin/bash
# 上电后一键诊断。 设计目标：一次跑完，不中途停 ROS 节点，
# 避免像前几次「排查到一半断电」那样丢失结果。
# 全程只读，不改任何持久配置。
set -u
SDKPATH=/home/pi/demo
log() { echo; echo "===== $* ====="; }

log "0. 系统与供电"
uptime | sed 's/^/  /'
echo "  温度: $(vcgencmd measure_temp 2>/dev/null | cut -d= -f2)"
echo "  欠压标志(1=曾欠压): $(vcgencmd get_throttled 2>/dev/null)"
echo "  内存: $(free -m | awk '/Mem:/{print $3"/"$2" MB"}')"

log "1. 串口设备现状"
ls -l /dev/rrc /dev/ttyAMA0 /dev/ttyUSB* 2>&1 | grep -v '^ls:'
echo "  谁持有 ttyAMA0:"
sudo lsof /dev/ttyAMA0 2>/dev/null | tail -3 || echo "    (无)"
echo "  谁持有 ttyUSB0:"
sudo lsof /dev/ttyUSB0 2>/dev/null | tail -3 || echo "    (无)"

log "2. 容器与 ROS 节点数（这两个是关键基线）"
docker ps --filter name=turbopi --format '  容器 {{.Names}} {{.Status}}'
N=$(docker exec turbopi sh -c 'source ~/ros2_ws/install/setup.bash 2>/dev/null; timeout 20 ros2 node list 2>/dev/null | wc -l' 2>/dev/null)
echo "  ROS 节点数: ${N:-0}  (正常应 >= 7)"
docker exec turbopi sh -c 'source ~/ros2_ws/install/setup.bash 2>/dev/null; timeout 20 ros2 topic info /cmd_vel 2>/dev/null | head -4' 2>&1 | sed 's/^/  /'

log "3. 电池（两条路径都试，确定扩展板挂在哪个口）"
echo "--- 3a. /dev/rrc (ttyAMA0, 厂商默认) ---"
PYTHONPATH=$SDKPATH timeout 20 python3 -c "
import time, ros_robot_controller_sdk as rrc
try:
    b = rrc.Board()
    b.enable_reception(); time.sleep(1.0)
    vs=[b.get_battery() for _ in range(6)]
    ok=[v for v in vs if v is not None]
    print('  采样:', vs)
    print('  结论:', ('**通了** 电压 %d mV'%ok[0]) if ok else '无数据')
except Exception as e:
    print('  异常:', type(e).__name__, e)
" 2>&1 | tail -4

echo "--- 3b. /dev/ttyUSB0 (CH340, 待验证假设) ---"
PYTHONPATH=$SDKPATH timeout 20 python3 -c "
import time, ros_robot_controller_sdk as rrc
try:
    b = rrc.Board(device='/dev/ttyUSB0')
    b.enable_reception(); time.sleep(1.0)
    vs=[b.get_battery() for _ in range(6)]
    ok=[v for v in vs if v is not None]
    print('  采样:', vs)
    print('  结论:', ('**通了** 电压 %d mV'%ok[0]) if ok else '无数据')
except Exception as e:
    print('  异常:', type(e).__name__, e)
" 2>&1 | tail -4

log "4. 判据汇总"
echo "  → 3a 有数   : 串口正常，直接跑运动流程"
echo "  → 3b 有数   : 扩展板在 USB 上，需改 /dev/rrc 软链后重测"
echo "  → 都无数   : 纯硬件问题，查指示灯/排线/供电"
