#!/usr/bin/env python3
"""
给 turpi_device.py 加断线自动重连。

原理：
  当前的 __main__ 只调用一次 asyncio.run(main())，WebSocket 一旦
  keepalive 超时抛异常，程序就停在 finally 里不再重连。
  改为在 __main__ 外层套一个重连循环，捕获连接类异常并退避重试。

安全性：
  · 改前自动备份 .bak.<时间戳>
  · 精确文本匹配，匹配失败就整体退出，绝不半改
  · 幂等：已有 MHS-RECONNECT 标记则跳过
  · 只动 __main__ 块，不碰任何业务逻辑
"""
import re
import shutil
import sys
import time
from pathlib import Path

TARGET = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/turpi_device.py")
MARKER = "MHS-RECONNECT"

OLD = '''if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    finally:
        try:
            bridge.stop_chassis()
            bridge.centre_gimbal()
        except Exception:  # noqa: BLE001
            pass
'''

NEW = '''# ==== MHS-RECONNECT: 断线自动重连 ====
def _is_connection_error(exc):
    """判断是否为可重试的连接类异常。"""
    name = type(exc).__module__ + "." + type(exc).__name__
    text = f"{name} {exc}".lower()
    for key in (
        "connectionclosed",     # websockets 断连
        "keepalive",
        "timeout",
        "connectionreset",
        "connectionerror",
        "brokenpipe",
        "eof",
        "1011",
    ):
        if key in text:
            return True
    return False


def _run_with_reconnect():
    """反复运行 main()，连接断了就退避重连。"""
    attempt = 0
    while True:
        try:
            asyncio.run(main())
            # main() 正常返回也视为断开，继续重连
            print("[reconnect] main() returned; reconnecting", flush=True)
            attempt = 0
        except KeyboardInterrupt:
            print("[reconnect] interrupted by user; exiting", flush=True)
            raise
        except Exception as exc:  # noqa: BLE001
            if not _is_connection_error(exc):
                # 非连接类错误：不吞掉，打印后仍然重试（机器人要能自愈）
                print(f"[reconnect] unexpected error: {type(exc).__name__}: {exc}",
                      flush=True)
            else:
                print(f"[reconnect] connection lost: {type(exc).__name__}: {exc}",
                      flush=True)

        # 退避：2s, 4s, 8s, 16s, 30s 封顶
        attempt += 1
        delay = min(2 ** min(attempt, 5), 30)
        print(f"[reconnect] retrying in {delay}s (attempt {attempt})", flush=True)

        # 重连前确保底盘停止（安全）
        try:
            bridge.stop_chassis()
            bridge.centre_gimbal()
        except Exception:  # noqa: BLE001
            pass

        time.sleep(delay)


if __name__ == "__main__":
    try:
        _run_with_reconnect()
    except KeyboardInterrupt:
        pass
    finally:
        try:
            bridge.stop_chassis()
            bridge.centre_gimbal()
        except Exception:  # noqa: BLE001
            pass
'''


def main():
    if not TARGET.exists():
        print(f"FAIL: 找不到 {TARGET}")
        return 1

    src = TARGET.read_text(encoding="utf-8")

    if MARKER in src:
        print("SKIP: 已经打过重连补丁（找到标记 %s）" % MARKER)
        return 0

    if OLD not in src:
        print("FAIL: 未匹配到 __main__ 块。文件可能已改动。")
        print("--- 期望匹配 ---")
        print(OLD)
        return 1

    backup = TARGET.with_suffix(
        TARGET.suffix + ".bak." + time.strftime("%Y%m%d-%H%M%S")
    )
    shutil.copy2(TARGET, backup)
    print(f"备份: {backup}")

    out = src.replace(OLD, NEW, 1)
    TARGET.write_text(out, encoding="utf-8")
    print(f"已写入: {TARGET}")

    # 语法自检
    import py_compile

    try:
        py_compile.compile(str(TARGET), doraise=True)
        print("SYNTAX_OK")
    except py_compile.PyCompileError as exc:
        print("SYNTAX_FAIL:", exc)
        shutil.copy2(backup, TARGET)
        print("已回滚")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
