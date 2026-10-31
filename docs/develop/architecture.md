# HomeGuard Architecture

> 本文档另有[中文版本](architecture.zh-CN.md)。

This document describes the system architecture of HomeGuard.

## Overview

HomeGuard follows a **host-device** architecture where:

- **Host (Windows PC)**: Runs Agnes Harness + AgnesHub + LLM; performs task planning and orchestration
- **Device (TurboPi)**: Runs device program; declares capabilities; accepts calls
- **Network**: Device dials host via outbound WebSocket (MHS protocol)

## System Diagram

```
┌──────────────────────┐         ┌──────────────────────────┐
│  Host (Windows)      │         │  TurboPi (Raspberry Pi 5) │
│                      │         │                          │
│  AGH + LLM           │         │  Docker container        │
│   ├ AgnesHub Plugin  │◄────────┤   ├ turpi_device.py      │
│   │  :4180           │ Outbound│   │  (agnes_mhs library) │
│   └ Devices Panel    │   WS    │   ├ ROS2 Humble          │
│                      │         │   │  ├ mecanum_chassis   │
└──────────────────────┘         │   │  ├ usb_cam           │
                                 │   │  └ web_video_server  │
                                 └──────────────────────────┘
```

## Key Design Decision: Call Direction

The device **actively dials** the host's AgnesHub—not the other way around. This brings three benefits:

1. **Device opens no inbound ports** — only one outbound WebSocket (minimal attack surface)
2. **Protocol layer handled by AGH** — no glue code needed on the host to "talk to the robot"
3. **Every call validated against device declarations** — device declares capabilities; AGH enforces them

## Core Modules

### 1. Task Planning (LLM + AGH)

The LLM receives natural language input and plans execution steps:

```
Input: "Check if the balcony plants need watering"
↓
Plan:
  1. list_devices → confirm turpi-01 online
  2. read_device(pose) → check location and battery
  3. call_device(drive, distance=2.0, speed=0.1) → move toward plant
  4. read_device(front) → capture image
  5. Visual reasoning → judge plant state
  6. If confidence < 0.7 → change_view + retry
  7. Output structured conclusion
```

### 2. Device Capability Declaration (MHS)

The device declares its capabilities to AgnesHub:

| Tool/Source | Type | Description | Status |
|---|---|---|---|
| `drive` | tool | Move forward/backward specified distance (meters) | ✅ Verified |
| `turn` | tool | Rotate in place specified angle (degrees) | ✅ Verified |
| `change_view` | tool | Change camera angle (semantic wrapper for turn) | ✅ Verified |
| `aim_camera` | tool | Gimbal control (hardware lacks torque; **always fails**) | ⚠ Intentional |
| `halt` | tool | Emergency stop | ✅ Verified |
| `say` | tool | Speak text (falls back to beep if no TTS) | ✅ Verified |
| `listen` | tool | Listen for N seconds and report volume | ✅ Verified |
| `front` | source | Camera image (640×480 JPEG) | ✅ Verified |
| `pose` | source | Odometry pose (x, y, yaw, ok) — **`ok: false` (no encoders)** | ✅ Honest |
| `mic` | source | Microphone audio (on-demand recording) | ✅ Verified |

### 3. Visual Reasoning (LLM + Camera)

Camera images enter the model context via `read_device(front)` with `returnsImages` capability:

```python
# Image capture
read_device(device="turpi-01", sources=["front"])
# → Returns 640×480 JPEG directly in model context

# Model outputs structured judgment
{
  "conclusion": "needs watering",
  "confidence": 0.82,
  "evidence": ["leaves appear slightly wilted", "soil surface looks dry"],
  "retry_recommended": false
}
```

When confidence is low, the system automatically adjusts camera angle and retries:

```python
# Low confidence → retry
change_view(angle=15)  # Rotate 15 degrees
read_device(sources=["front"])  # Re-capture
# → Second judgment with improved confidence
```

### 4. Execution Feedback Loop (AGH)

Every device call returns structured feedback to the model:

```python
# Successful drive
call_device(device="turpi-01", tool="drive", args={"distance": 0.5, "speed": 0.1})
# → "drove 0.50 m forward. Now at (1, 0.5) facing 0 degrees. Took 5 s."

# Failed gimbal call
call_device(device="turpi-01", tool="aim_camera", args={"pan": 45})
# → Error: "gimbal torque insufficient. Suggestion: use change_view instead."
```

The model reads these results and adjusts strategy accordingly—enabling **closed-loop execution**.

## Deployment Architecture

| Layer | Component | Deployment |
|---|---|---|
| **Host** | Agnes Harness + AgnesHub | Windows PC, Node.js ≥ 24.10 |
| **Host** | LLM API | DeepSeek V4.1 Flash (1M context) |
| **Network** | WebSocket | Device → Host :4180 (outbound from device) |
| **Device** | turpi_device.py | Docker container on Raspberry Pi 5 |
| **Device** | ROS2 stack | mecanum_chassis, usb_cam, web_video_server |

**Security Note:** AgnesHub has **no authentication or encryption** (by design). It must only listen on trusted local networks—**never expose to the public internet**.

## Data Flow

1. **User Input** → Natural language command in AGH web interface
2. **Task Planning** → LLM parses input and generates execution plan
3. **Device Discovery** → Model calls `list_devices` to find available devices
4. **State Check** → Model calls `read_device(pose)` to confirm device online and check battery
5. **Navigation** → Model calls `drive` / `turn` / `change_view` to move robot
6. **Observation** → Model calls `read_device(front)` to capture camera image
7. **Visual Reasoning** → LLM analyzes image and outputs structured judgment
8. **Uncertainty Handling** → If confidence low, model adjusts angle and retries
9. **Result Reporting** → Model outputs final conclusion with evidence
10. **Execution Logging** → AGH records all calls for audit and verification

## Security Model

- **Device dials host** — no inbound ports on device
- **Capability validation** — AGH validates every call against device declarations
- **Emergency stop** — `halt` tool always allowed
- **No auth/encryption** — must run on trusted LAN only
- **Honest failure reporting** — hardware limitations documented, not hidden

## Extensibility

### Adding New Devices

1. Implement device program using `agnes_mhs` library
2. Declare tools and sources via `dev.tool()` / `dev.source()`
3. Device dials AgnesHub URL
4. Model can now call new device via same 7 fixed tools

### Adding New Tasks

1. Input natural language description in AGH
2. LLM plans execution steps
3. No code changes needed (if device capabilities sufficient)

## Known Limitations

1. **Gimbal unavailable** — servo lacks torque
2. **No encoders** — position drifts over time
3. **Low-voltage protection disabled** — manual check required
4. **No authentication** — trusted LAN only
5. **Windows build unvalidated** — Linux recommended
