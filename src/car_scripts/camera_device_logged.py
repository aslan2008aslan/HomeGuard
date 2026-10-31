#!/usr/bin/env python3
# encoding: utf-8
"""Camera-only MHS device with logging, so streaming problems are visible.

Sends the TurboPi camera as an MHS image source. No motors, no gimbal:
read-only and safe to leave running.

Usage (inside the turbopi container):
    PYTHONPATH=... python3 camera_device_logged.py ws://<HUB_HOST>:4180
"""
import asyncio
import os
import sys
import time
import urllib.request

from agnes_mhs import Device

HUB_URL = sys.argv[1] if len(sys.argv) > 1 else "ws://192.168.3.149:4180"
CAM_URL = os.environ.get(
    "TURPI_CAMERA_URL", "http://127.0.0.1:8080/snapshot?topic=/image_raw"
)


def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


log(f"starting, hub={HUB_URL}")
log(f"camera={CAM_URL}")

dev = Device("turpi-cam", "camera", name="TurPi camera", localization="none")
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
log(f"device declared; source on={view.on} hz={view.hz}")


def grab():
    try:
        with urllib.request.urlopen(CAM_URL, timeout=5) as r:
            data = r.read()
        if len(data) > 4 and data[0] == 0xFF and data[1] == 0xD8:
            return data
        log(f"not a JPEG: first bytes {data[:4]!r}")
    except Exception as exc:  # noqa: BLE001
        log(f"grab failed: {exc}")
    return None


async def loop():
    log("stream loop started")
    sent = 0
    skipped = 0
    while True:
        try:
            if view.wants():
                data = await asyncio.get_event_loop().run_in_executor(None, grab)
                if data:
                    ok = view.send(data)
                    sent += 1
                    if sent <= 3 or sent % 10 == 0:
                        log(f"sent #{sent} ({len(data)} bytes, send()={ok})")
                else:
                    log("grab returned nothing")
            else:
                skipped += 1
                if skipped % 40 == 1:
                    log(f"not wanted yet (on={view.on} hz={view.hz} skipped={skipped})")
        except Exception as exc:  # noqa: BLE001
            log(f"loop error: {exc!r}")
        await asyncio.sleep(0.2)


async def main():
    task = asyncio.create_task(loop())
    try:
        await dev.run(HUB_URL)
        log("dev.run() returned")
    except Exception as exc:  # noqa: BLE001
        log(f"dev.run() raised: {exc!r}")
    finally:
        task.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    log("exited")
