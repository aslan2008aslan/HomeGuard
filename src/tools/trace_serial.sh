#!/bin/bash
# 追查宿主上的 ros_robot 进程 + GPIO 引脚实际状态 + 串口底层自测
set -u
SDKPATH=/home/pi/demo

echo "===== 1. 宿主上的 ros_robot 进程是什么 ====="
ps -ef | grep -i '[r]os_robot' | head -10
echo "--- 它的完整命令行 ---"
for p in $(pgrep -f 'ros_robot'); do echo "PID $p:"; tr '\0' ' ' < /proc/$p/cmdline; echo; echo "  父进程: $(ps -o ppid= -p $p 2>/dev/null)"; echo "  启动于: $(ps -o lstart= -p $p 2>/dev/null)"; done

echo
echo "===== 2. 容器内 ROS 栈状态（容器 Up 7h 但节点 0） ====="
docker exec turbopi zsh -c 'source ~/ros2_ws/.zshrc >/dev/null 2>&1; timeout 20 ros2 node list 2>&1 | head -8'
echo "--- 容器内进程 ---"
docker exec turbopi ps -eo pid,etime,cmd 2>/dev/null | grep -E '[r]os2|[m]ecanum|[b]ringup' | head -8 || echo "  (无 ROS 进程)"
echo "--- bringup 日志尾部 ---"
docker exec turbopi tail -15 /tmp/bringup.log 2>/dev/null || echo "  (无日志)"

echo
echo "===== 3. GPIO 14/15 真实状态（关键：UART 是否被占用） ====="
sudo pinctrl get 14,15 2>&1
echo "--- 是否有别的服务抢串口 ---"
systemctl list-units --type=service --state=running 2>/dev/null | grep -iE 'serial|uart|rrc|ros' || echo "  (无相关服务)"
echo "--- /boot/firmware/config.txt 里的串口配置 ---"
grep -iE 'uart|serial|enable_uart' /boot/firmware/config.txt 2>/dev/null || echo "  (无 uart 相关行)"
echo "--- cmdline.txt 串口重定向 ---"
cat /boot/firmware/cmdline.txt 2>/dev/null | tr ' ' '\n' | grep -i 'console' || echo "  (无 console 重定向)"

echo
echo "===== 4. 串口自测（回环验证，确认树莓派 UART 硬件本身好坏） ====="
echo "  说明：把 TX 和 RX 短接才需此测；先看发数据时 TX 电平是否变化"
sudo python3 - <<'PY' 2>&1 | tail -10
import serial, time
try:
    s = serial.Serial('/dev/ttyAMA0', 1000000, timeout=1)
    print("  打开成功")
    # 看 modem 状态行
    print("  modem lines:", s.getCTS(), s.getDSR())
    s.write(b'\xaa\x55'*8); s.flush()
    time.sleep(0.3)
    d = s.read(64)
    print(f"  自发自收 {len(d)} 字节 (通常 0，除非 TX-RX 短接)")
    s.close()
except Exception as e:
    print("  异常:", type(e).__name__, e)
PY

echo
echo "===== 5. 扩展板供电检测（能否通过其他方式感知） ====="
echo "--- I2C 总线上是否有设备（扩展板若走 I2C 会现身） ---"
sudo python3 -c "
import subprocess
try:
    import smbus2
    print('  smbus2 可用')
except ImportError:
    print('  smbus2 未装')
" 2>&1
echo "--- /dev/i2c-1 上扫描 ---"
sudo i2cdetect -y 1 2>/dev/null || sudo python3 -c "
import fcntl, struct
I2C_SLAVE=0x0703
try:
    f=open('/dev/i2c-1','rb',buffering=0)
    found=[]
    for a in range(0x03,0x78):
        try:
            fcntl.ioctl(f, I2C_SLAVE, a)
            if f.read(1) is not None: found.append(hex(a))
        except OSError: pass
    print('  发现的 I2C 设备:', found or '(无)')
except Exception as e: print('  ', e)
" 2>&1

echo
echo "===== 6. 结论 ====="
echo "  3a/3b 都无数据 + USB 假设排除 → 需确认扩展板是否通电"
