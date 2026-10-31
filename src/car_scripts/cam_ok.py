#!/usr/bin/env python3
# encoding: utf-8
"""Camera-only MHS device for the TurboPi, correctly sending image payloads.

The MHS device library signature is:
    source.send(data: dict, binary: bytes | None = None, ...)
The metadata goes in the FIRST argument and the image bytes in the SECOND.
Passing the JPEG as the first argument (as an earlier version did) means the
hub never sees a binary frame, so nothing is delivered.

Usage (inside the turbopi container):
    PYTHONPATH=/opt/agh_mhs/python/src python3 cam_ok.py ws://<HUB>:4180
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
WIDTH, HEIGHT = 640, 480


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


log(f"hub={HUB_URL}")
log(f"camera={CAM_URL}")

dev = Device("turpi-cam", "camera", name="TurPi camera", localization="none")
view = dev.source(
    "front",
    "image",
    "TurPi USB camera, 640x480",
    hz=1,
    mime="image/jpeg",
    encoding="rgb",
    size=[WIDTH, HEIGHT],
    default=True,
)


def grab():
    try:
        with urllib.request.urlopen(CAM_URL, timeout=5) as r:
            data = r.read()
        if len(data) > 4 and data[0] == 0xFF and data[1] == 0xD8:
            return data
        log(f"not a JPEG: {data[:4]!r}")
    except Exception as exc:  # noqa: BLE001
        log(f"grab failed: {exc}")
    return None


async def loop():
    log("stream loop started")
    sent = 0
    while True:
        try:
            if view.wants():
                jpeg = await asyncio.get_event_loop().run_in_executor(None, grab)
                if jpeg:
                    # metadata first, JPEG bytes second
                    ok = view.send({"w": WIDTH, "h": HEIGHT}, jpeg)
                    sent += 1
                    if sent <= 3 or sent % 10 == 0:
                        log(f"sent #{sent} ({len(jpeg)} bytes, send={ok})")
        except Exception as exc:  # noqa: BLE001
            log(f"loop error: {exc!r}")
        await asyncio.sleep(0.2)


async def main():
    t = asyncio.create_task(loop())
    try:
        await dev.run(HUB_URL)
        log("dev.run returned")
    except Exception as exc:  # noqa: BLE001
        log(f"dev.run raised {exc!r}")
    finally:
        t.cancel()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    log("exited")
