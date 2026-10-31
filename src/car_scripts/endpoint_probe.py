#!/usr/bin/env python3
# encoding: utf-8
"""Check the two MHS endpoints a device needs, from inside the container.

Command channel : /ws/mhs
Nerve (data)    : /ws/nerve
Hub API         : /ws/hub
"""
import asyncio
import sys

HOST = sys.argv[1] if len(sys.argv) > 1 else "192.168.3.149"
PORT = sys.argv[2] if len(sys.argv) > 2 else "4180"


async def probe(path, subprotocols=None):
    try:
        import websockets
    except ImportError:
        print("websockets not installed")
        return

    url = f"ws://{HOST}:{PORT}{path}"
    try:
        async with websockets.connect(
            url, subprotocols=subprotocols, open_timeout=8, ping_interval=None
        ) as ws:
            print(f"  {path}: CONNECTED  subprotocol={ws.subprotocol!r}")
            return True
    except Exception as exc:  # noqa: BLE001
        print(f"  {path}: FAILED  {type(exc).__name__}: {exc}")
        return False


async def main():
    print(f"probing ws://{HOST}:{PORT}")
    await probe("/ws/hub")
    await probe("/ws/mhs", subprotocols=["mhs/v1"])
    await probe("/ws/nerve", subprotocols=["mhs/v1"])
    # also try without the subprotocol in case the server is stricter
    await probe("/ws/nerve")


asyncio.run(main())
print("PROBE_DONE")
