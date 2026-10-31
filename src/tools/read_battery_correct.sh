#!/bin/bash
# 用正确的方式读电池：先彻底清空缓冲区，再同步到帧头，逐帧解析。
set -u
echo "===== 1. 清空积压 + 逐帧解析（自己解协议） ====="
sudo python3 - <<'PY'
import serial, time, struct

s = serial.Serial('/dev/ttyAMA0', 1000000, timeout=0.5)
# 关键：把积压的老数据彻底冲掉
s.reset_input_buffer(); time.sleep(0.5)
s.reset_input_buffer(); time.sleep(0.2)
print(f"  清空后缓冲区剩余: {s.in_waiting} 字节")

def read_frame(timeout=2.0):
    """同步到 aa55 帧头，读一整帧"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        b = s.read(1)
        if not b: continue
        if b[0] != 0xAA: continue
        nxt = s.read(1)
        if not nxt or nxt[0] != 0x55: continue
        # 读到帧头，读 功能码+长度
        hdr = s.read(2)
        if len(hdr) < 2: continue
        func, length = hdr[0], hdr[1]
        body = s.read(length + 1)   # 数据 + 校验
        if len(body) < length + 1: continue
        data, chk = body[:length], body[length]
        return func, data, chk
    return None

print()
print("  连续读 10 帧:")
ok = 0
for i in range(10):
    f = read_frame()
    if f is None:
        print(f"    第{i+1}帧: 超时")
        continue
    func, data, chk = f
    if func == 0x04 and len(data) >= 2:
        mv = struct.unpack('<H', data[:2])[0]
        print(f"    第{i+1}帧: 电池 = {mv} mV")
        ok += 1
    else:
        print(f"    第{i+1}帧: func=0x{func:02x} data={data.hex()}")

print()
print(f"  成功读到电池 {ok}/10 次")
s.close()
PY

echo
echo "===== 2. 用 SDK 读（先清缓冲再 enable） ====="
sudo pkill -f ros_robot_controller 2>/dev/null; sleep 2
PYTHONPATH=/home/pi/demo python3 - <<'PY'
import serial, time
# 先独占清空缓冲区
try:
    s = serial.Serial('/dev/ttyAMA0', 1000000, timeout=0.3)
    for _ in range(5):
        s.reset_input_buffer(); time.sleep(0.2)
    print(f"  预清空完成，剩余 {s.in_waiting} 字节")
    s.close()
except Exception as e:
    print("  预清空失败:", e)

import ros_robot_controller_sdk as rrc
b = rrc.Board()
b.enable_reception()
time.sleep(1.5)
vs = [b.get_battery() for _ in range(10)]
print("  SDK 采样:", vs)
ok = [v for v in vs if v is not None]
print("  结论:", (f"**成功** {ok[0]} mV" if ok else "仍为 None"))
PY

echo
echo "===== 3. 恢复 ROS 栈 ====="
docker exec -d -u ubuntu -w /home/ubuntu turbopi /bin/zsh -c \
  'source ~/.zshrc >/dev/null 2>&1; exec ros2 launch bringup bringup.launch.py > /tmp/bringup.log 2>&1'
sleep 15
echo "  已重启，节点数: $(docker exec turbopi zsh -ic 'ros2 node list 2>/dev/null | wc -l' 2>/dev/null)"
