#!/usr/bin/env python3
# encoding: utf-8
"""Print the exact JSON+binary the device sends for one image message.

Compares it against what the hub expects, so a payload mismatch is visible
instead of silent. Uses the installed agnes_mhs library's own send path.
"""
import asyncio
import json
import os
import sys
import time
import urllib.request

from agnes_mhs import Device

HUB_URL = sys.argv[1] if len(sys.argv) > 1 else "ws://192.168.3.149:4180"
CAM_URL = "http://127.0.0.1:8080/snapshot?topic=/image_raw"


def log(m):
    print(f"[{time.strftime('%H:%M:%S')}] {m}", flush=True)


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

log("declaration the device will send:")
log(json.dumps(dev.description(), indent=2, ensure_ascii=False)[:1500])

# Show what send() actually queues, by intercepting the outbox.
original_queue = dev._queue
captured = {}


def spy_queue(source, msg, binary):
    captured["msg"] = msg
    captured["bin_len"] = len(binary) if binary else 0
    return original_queue(source, msg, binary)


dev._queue = spy_queue


def grab():
    try:
        with urllib.request.urlopen(CAM_URL, timeout=5) as r:
            return r.read()
    except Exception as exc:  # noqa: BLE001
        log(f"grab err {exc}")
    return None


async def loop():
    while True:
        if view.wants():
            data = await asyncio.get_event_loop().run_in_executor(None, grab)
            if data:
                view.send(data)
                log("queued one image message")
                if captured:
                    msg = dict(captured["msg"])
                    log(f"JSON payload: {json.dumps(msg, ensure_ascii=False)}")
                    log(f"binary bytes: {captured['bin_len']}")
                break
        await asyncio.sleep(0.2)


async def main():
    t = asyncio.create_task(loop())
    try:
        await asyncio.wait_for(dev.run(HUB_URL), timeout=25)
    except asyncio.TimeoutError:
        pass
    except Exception as exc:  # noqa: BLE001
        log(f"run raised {exc!r}")
    finally:
        t.cancel()


asyncio.run(main())
log("done")
