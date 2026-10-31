#!/usr/bin/env python3
# encoding: utf-8
"""Minimal MHS device that only exposes the camera.

Its single purpose is to get a real frame from the TurboPi camera into the
model's context through the standard MHS image path, so the picture can be
described. No motors, no gimbal: read-only and safe to run.

Usage (inside the turbopi container):
    python3 camera_only_device.py ws://<HUB_HOST>:4180
"""
import asyncio
import os
import sys
import urllib.request

from agnes_mhs import Device

HUB_URL = sys.argv[1] if len(sys.argv) > 1 else "ws://127.0.0.1:4180"
CAM_URL = os.environ.get(
    "TURPI_CAMERA_URL", "http://127.0.0.1:8080/snapshot?topic=/image_raw"
)

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


def grab():
    try:
        with urllib.request.urlopen(CAM_URL, timeout=5) as r:
            data = r.read()
        if len(data) > 4 and data[0] == 0xFF and data[1] == 0xD8:
            return data
    except Exception:  # noqa: BLE001
        pass
    return None


async def loop():
    while True:
        try:
            if view.wants():
                data = await asyncio.get_event_loop().run_in_executor(None, grab)
                if data:
                    view.send(data)
        except Exception:  # noqa: BLE001
            pass
        await asyncio.sleep(0.2)


async def main():
    task = asyncio.create_task(loop())
    try:
        await dev.run(HUB_URL)
    finally:
        task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
