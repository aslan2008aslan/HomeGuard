#!/bin/bash
# 判定：64 字节回读是「物理回环」还是「扩展板在响应」
# 关键测试：发不同的字节，看回读的内容是否与我发的完全一致。
#   完全一致 → TX/RX 被短接（回环），串口线上没接扩展板，或扩展板未通电
#   不一致   → 扩展板真的在回应
set -u
echo "===== 回环判定测试 ====="
sudo python3 - <<'PY'
import serial, time

s = serial.Serial('/dev/ttyAMA0', 1000000, timeout=1.5)
time.sleep(0.3)

tests = [
    ("模式A (递增)",  bytes(range(1, 33))),
    ("模式B (全0x5A)", bytes([0x5a]*32)),
    ("模式C (随机)",  bytes([0x13,0x37,0xde,0xad,0xbe,0xef]*4)),
]
for name, payload in tests:
    s.reset_input_buffer()
    s.write(payload); s.flush()
    time.sleep(0.8)
    rx = s.read(128)
    same = (rx == payload)
    print(f"  {name}: 发 {len(payload)}B  收 {len(rx)}B  "
          f"{'【完全相同 → 回环】' if same else '【不同 → 有人回应】'}")
    print(f"     TX: {payload[:16].hex()}")
    print(f"     RX: {rx[:16].hex() if rx else '(空)'}")

# 再测：完全不发，静置看有没有主动上报（扩展板应主动发心跳/电池）
print()
print("  静置 3 秒（不发任何数据），看是否有人主动上报：")
s.reset_input_buffer()
t0 = time.time(); total = b""
while time.time() - t0 < 3:
    d = s.read(64)
    if d: total += d
print(f"     收到 {len(total)}B: {total[:24].hex() if total else '(空)'}")
print("     → 有数据 = 扩展板在主动上报（说明它是通的，只是协议不匹配）")
print("     → 无数据 = 线上真的没有东西在发")

s.close()
PY

echo
echo "===== 补充：直接看 TX 引脚在发数据时的电平跳变 ====="
echo "  (若 TX 始终不动，说明根本没发出去)"
sudo python3 - <<'PY'
import serial, time, subprocess
def pins():
    r = subprocess.run(['pinctrl','get','14,15'], capture_output=True, text=True).stdout
    return r.replace('\n',' | ').strip()
s = serial.Serial('/dev/ttyAMA0', 1000000, timeout=1)
print("  发数据前:", pins())
s.write(bytes([0xff]*2000)); s.flush()
print("  发数据后:", pins())
s.close()
PY

echo
echo "===== 结论 ====="
echo "  若三个模式 RX == TX 完全相同 → TX/RX 短接回环，说明："
echo "    · 树莓派 UART 硬件正常"
echo "    · 但串口线上没有扩展板在通信（未接/未通电/接线错）"
echo "  若 RX 与 TX 不同 → 扩展板在回应，问题在协议层"
