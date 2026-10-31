#!/usr/bin/env python3
# encoding: utf-8
"""Camera device that reports the internal Nerve channel state.

send() returns True even when the Nerve channel is down (the message is
dropped in _queue), so this version inspects the private _nerve attribute
to tell whether the data path is actually up.
"""
import asyncio
import logging
import os
import sys
import time
import urllib.request

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    stream=sys.stdout,
)

from agnes_mhs import Device

HUB_URL = sys.argv[1] if len(sys.argv) > 1 else "ws://192.168.3.149:4180"
CAM_URL = os.environ.get(
    "TURPI_CAMERA_URL", "http://127.0.0.1:8080/snapshot?topic=/image_raw"
)


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


log(f"hub={HUB_URL}")
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
    except Exception as exc:  # noqa: BLE001
        log(f"grab err {exc}")
    return None


async def loop():
    n = 0
    while True:
        n += 1
        try:
            nerve_up = getattr(dev, "_nerve", None) is not None
            cmd_up = getattr(dev, "_cmd", None) is not None
            if view.wants():
                data = await asyncio.get_event_loop().run_in_executor(None, grab)
                if data:
                    ok = view.send(data)
                    log(
                        f"send#{n} {len(data)}B ok={ok} "
                        f"nerve={'UP' if nerve_up else 'DOWN'} "
                        f"cmd={'UP' if cmd_up else 'DOWN'} "
                        f"on={view.on}"
                    )
            else:
                if n % 25 == 1:
                    log(
                        f"idle n={n} nerve={'UP' if nerve_up else 'DOWN'} "
                        f"cmd={'UP' if cmd_up else 'DOWN'} on={view.on}"
                    )
        except Exception as exc:  # noqa: BLE001
            log(f"loop err {exc!r}")
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
    asyncio.run(main())
