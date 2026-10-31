# MHS Integration Guide

This guide explains how to integrate new devices with HomeGuard using the Model Hardware Standard (MHS) protocol.

## Overview

MHS (Model Hardware Standard) is Agnes Harness's device communication protocol. It enables:

- **Device capability declaration** — devices declare their tools, sources, and state
- **Call validation** — AgnesHub validates every call against device declarations
- **Outbound-only connection** — device dials AgnesHub (no inbound ports needed)
- **Structured feedback** — every call returns success/failure with reason

## MHS Protocol Compliance

HomeGuard integrates with Agnes Harness via MHS:

| Standard | Description | Implementation |
|---|---|---|
| **Device Declaration** | Device declares tools, sources, and state to AgnesHub | `turpi_device.py` uses `agnes_mhs` library |
| **Capability Validation** | AgnesHub validates every call against device declarations | Built into AGH runtime |
| **Call Direction** | Device dials AgnesHub (outbound WebSocket) | No inbound ports on device |
| **Tool Interface** | 7 fixed device tools: `list_devices`, `read_device`, `call_device`, `set_device`, `stop_device`, `watch_device`, `unwatch_device` | Model calls via these tools |
| **Source Streaming** | Data sources (camera, pose, mic) stream via `read_device` | `returnsImages` capability for camera |

## Integration Checklist

For integrating new devices with HomeGuard:

- [ ] Device program uses `agnes_mhs` library
- [ ] Device declares all tools and sources via `dev.tool()` / `dev.source()`
- [ ] Device dials AgnesHub URL (outbound WebSocket)
- [ ] Device handles `halt` tool (safety requirement)
- [ ] Device declares safety constraints (e.g., low-voltage protection)
- [ ] Device returns structured feedback (success/failure + reason)
- [ ] Camera sources declare `returnsImages` capability (if applicable)

## Device Program Structure

### Basic Template

```python
from agnes_mhs import Device

# Create device
dev = Device(id="my-device-01", name="My Device")

# Declare a tool
@dev.tool("move", args={"distance": float, "speed": float})
async def move(distance: float, speed: float) -> str:
    # Implement movement logic
    return f"moved {distance}m at {speed}m/s"

# Declare a source
@dev.source("camera", returns_images=True)
async def camera() -> bytes:
    # Return JPEG image
    return jpeg_bytes

# Run device (dials AgnesHub)
await dev.run("ws://192.168.1.100:4180")
```

### Declaring Tools

Tools are actions the device can perform:

```python
@dev.tool("drive", args={"distance": float, "speed": float})
async def drive(distance: float, speed: float) -> str:
    """Move forward/backward specified distance."""
    # Implementation
    return f"drove {distance}m forward"

@dev.tool("turn", args={"angle": float})
async def turn(angle: float) -> str:
    """Rotate in place specified angle."""
    # Implementation
    return f"turned {angle} degrees"
```

### Declaring Sources

Sources are data streams the device provides:

```python
@dev.source("front", returns_images=True)
async def front() -> bytes:
    """Camera image (640×480 JPEG)."""
    # Capture and return image
    return capture_image()

@dev.source("pose")
async def pose() -> dict:
    """Odometry pose."""
    return {
        "map": "home",
        "x": 1.0,
        "y": 0.5,
        "yaw": 0.0,
        "ok": False  # Mark as unreliable if no encoders
    }
```

### Safety Tools

Every device **must** implement `halt`:

```python
@dev.tool("halt")
async def halt() -> str:
    """Emergency stop. Always allowed."""
    # Stop all motors
    stop_motors()
    return "halted"
```

## API Standards

### Device Tools (Model-Side)

The model interacts with devices through 7 fixed tools:

```python
# List available devices
list_devices()
# → ["turpi-01", "my-device-01"]

# Read device state/sources
read_device(device="my-device-01", sources=["pose", "front"])
# → {pose: {x, y, yaw, ok}, front: <image>}

# Call device tool
call_device(device="my-device-01", tool="drive", args={"distance": 0.5, "speed": 0.1})
# → "drove 0.50 m forward..."

# Stop device (always allowed)
stop_device(device="my-device-01")
# → "halted"
```

### Device-Side Tools (Hardware-Specific)

The device declares its own tools (passed as parameters to `call_device`):

```python
# Movement
drive(distance: float, speed: float) → str
turn(angle: float) → str

# Camera
change_view(angle: float) → str
aim_camera(pan: float, tilt: float) → str

# Safety
halt() → str

# Audio
say(text: str) → str
listen(duration: float) → {peak: float, rms: float}
```

## Technical Standards

| Standard | Version | Notes |
|---|---|---|
| **Node.js** | ≥ 24.10 | Required for Agnes Harness |
| **Python** | ≥ 3.10 | Required for `agnes_mhs` |
| **WebSocket** | RFC 6455 | Device ↔ AgnesHub communication |
| **JSON** | RFC 8259 | Tool arguments and responses |

## Example: Integrating a New Robot

### Step 1: Install Dependencies

```bash
pip install agnes-mhs jsonschema websockets
```

### Step 2: Write Device Program

```python
# my_robot.py
from agnes_mhs import Device

dev = Device(id="my-robot-01", name="My Robot")

@dev.tool("move", args={"x": float, "y": float})
async def move(x: float, y: float) -> str:
    # Move to (x, y)
    return f"moved to ({x}, {y})"

@dev.tool("halt")
async def halt() -> str:
    # Emergency stop
    return "halted"

@dev.source("camera", returns_images=True)
async def camera() -> bytes:
    # Return camera image
    return capture_image()

# Dial AgnesHub
await dev.run("ws://192.168.1.100:4180")
```

### Step 3: Run Device Program

```bash
python my_robot.py
```

### Step 4: Verify in AGH

```python
# In AGH session
list_devices()
# → ["turpi-01", "my-robot-01"]

read_device(device="my-robot-01", sources=["camera"])
# → {camera: <image>}
```

## Troubleshooting

### Device not connecting

- Check AgnesHub URL: must be reachable from device
- Check firewall: AgnesHub must listen on `0.0.0.0:4180`
- Check device logs: look for connection errors

### Tool calls failing

- Verify tool is declared in device program
- Check argument types match declaration
- Read error message: AGH returns structured feedback

### Images not appearing

- Ensure source declares `returns_images=True`
- Verify image format is JPEG
- Check image size (640×480 recommended)

## Resources

- [MHS Protocol Specification](https://github.com/AgnesAI-Labs/agnes-harness/tree/main/packages/mhs)
- [Agnes Harness Documentation](https://github.com/AgnesAI-Labs/agnes-harness/tree/main/docs)
- [HomeGuard Architecture](../docs/develop/architecture.md)
