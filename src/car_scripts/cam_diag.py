#!/usr/bin/env python3
# encoding: utf-8
"""Diagnostic version: trace exactly where startup stops.

Prints progress markers and captures any exception, including the case where
dev.run() returns immediately.
"""
import asyncio
import os
import sys
import traceback
import urllib.request

print("START", flush=True)

HUB_URL = sys.argv[1] if len(sys.argv) > 1 else "ws://192.168.3.149:4180"
CAM_URL = "http://127.0.0.1:8080/snapshot?topic=/image_raw"
print(f"HUB_URL = {HUB_URL}", flush=True)

try:
    from agnes_mhs import Device
    print("import agnes_mhs OK", flush=True)
except Exception:
    traceback.print_exc()
    sys.exit(3)

print("creating device...", flush=True)
try:
    dev = Device("turpi-cam", "camera", name="TurPi camera", localization="none")
    print("device created", flush=True)
except Exception:
    traceback.print_exc()
    sys.exit(4)

print("declaring source...", flush=True)
try:
    view = dev.source(
        "front",
        "image",
        "TurPi USB camera, 640x480",
        hz=1,
        mime="image/jpeg",
        encoding="rgb",
        size=[640, 480],
        default=True,
    )
    print("source declared", flush=True)
except Exception:
    traceback.print_exc()
    sys.exit(5)


def grab():
    try:
        with urllib.request.urlopen(CAM_URL, timeout=5) as r:
            data = r.read()
        if len(data) > 4 and data[0] == 0xFF and data[1] == 0xD8:
            return data
    except Exception as exc:  # noqa: BLE001
        print(f"grab failed: {exc}", flush=True)
    return None


async def loop():
    print("stream loop started", flush=True)
    while True:
        try:
            if view.wants():
                data = await asyncio.get_event_loop().run_in_executor(None, grab)
                if data:
                    view.send(data)
                    print(f"sent frame {len(data)} bytes", flush=True)
        except Exception as exc:  # noqa: BLE001
            print(f"loop error: {exc}", flush=True)
        await asyncio.sleep(0.5)


async def main():
    task = asyncio.create_task(loop())
    print("calling dev.run()...", flush=True)
    try:
        await dev.run(HUB_URL)
        print("dev.run() RETURNED (connection ended)", flush=True)
    except Exception:
        print("dev.run() RAISED:", flush=True)
        traceback.print_exc()
    finally:
        task.cancel()


print("entering asyncio.run(main())", flush=True)
try:
    asyncio.run(main())
except Exception:
    traceback.print_exc()
print("EXITED", flush=True)
