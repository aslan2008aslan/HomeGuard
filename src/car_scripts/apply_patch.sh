#!/bin/bash
# TurboPi 设备程序补丁应用器
#
# 作用：把宿主上持久保存的补丁版设备程序同步进容器 /tmp，
#       让「容器重建 / 断电重开」后不必手工再打补丁。
#
# 为什么需要它：
#   设备程序跑在容器内的 /tmp/turpi_device_patched.py，而容器内 /tmp
#   不是数据卷（docker inspect 的 Mounts 里没有它）。所以：
#     · docker restart turbopi  -> /tmp 保留，补丁还在
#     · 容器被删除/重建          -> /tmp 清空，补丁丢失
#   断电重开若导致容器重建，车就退回「电池字段为空」的老路。
#
# 用法：
#   bash apply_patch.sh          # 同步补丁进容器（幂等，可反复跑）
#
# 判据：容器内 /tmp/turpi_device_patched.py 的 md5 是否等于宿主副本。
#       不一致或不存在就重新拷入。
set -u

SRC=/home/pi/turbopi_agh/turpi_device_patched.py
DST=/tmp/turpi_device_patched.py
CONT=turbopi

say(){ echo "[$(date '+%m-%d %H:%M:%S')] $*"; }

[ -f "$SRC" ] || { say "错误：找不到宿主补丁 $SRC"; exit 1; }

# 等容器就绪（最多 60s）
for i in $(seq 1 30); do
  docker inspect "$CONT" >/dev/null 2>&1 && break
  sleep 2
done
docker inspect "$CONT" >/dev/null 2>&1 || { say "错误：容器 $CONT 不存在"; exit 1; }

WANT=$(md5sum "$SRC" | cut -d' ' -f1)
HAVE=$(docker exec "$CONT" md5sum "$DST" 2>/dev/null | cut -d' ' -f1)

if [ "$WANT" = "$HAVE" ]; then
  say "补丁已在容器内且一致（md5 $WANT），无需操作"
  exit 0
fi

say "容器内补丁缺失或不一致（期望 $WANT / 实际 ${HAVE:-无}）→ 拷入"
docker cp "$SRC" "$CONT:$DST" || { say "错误：docker cp 失败"; exit 1; }
chmod 644 "$SRC" 2>/dev/null || true

NOW=$(docker exec "$CONT" md5sum "$DST" | cut -d' ' -f1)
if [ "$NOW" = "$WANT" ]; then
  say "已同步，校验通过（md5 $NOW）"
else
  say "警告：同步后 md5 仍不匹配（$NOW）"
  exit 1
fi

# 顺带确认两处类型修复都在
N=$(docker exec "$CONT" grep -c UInt16 "$DST" 2>/dev/null || echo 0)
say "  UInt16 出现次数：$N（应为 2）"
