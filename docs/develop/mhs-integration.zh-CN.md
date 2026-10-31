> 本文档另有[英文版本](mhs-integration.md)。

# MHS 集成指南

本指南介绍如何使用模型硬件标准（Model Hardware Standard, MHS）协议将新设备集成到 HomeGuard 中。

## 概述

MHS（Model Hardware Standard）是 Agnes Harness 的设备通信协议。它实现了：

- **设备能力声明** — 设备声明其工具、数据源和状态
- **调用验证** — AgnesHub 根据设备声明验证每次调用
- **仅出站连接** — 设备主动拨号连接 AgnesHub（无需入站端口）
- **结构化反馈** — 每次调用返回成功/失败及原因

## MHS 协议合规性

HomeGuard 通过 MHS 与 Agnes Harness 集成：

| 标准 | 描述 | 实现方式 |
|---|---|---|
| **设备声明** | 设备向 AgnesHub 声明工具、数据源和状态 | `turpi_device.py` 使用 `agnes_mhs` 库 |
| **能力验证** | AgnesHub 根据设备声明验证每次调用 | 内置于 AGH 运行时 |
| **调用方向** | 设备拨号连接 AgnesHub（出站 WebSocket） | 设备无需入站端口 |
| **工具接口** | 7 个固定设备工具：`list_devices`、`read_device`、`call_device`、`set_device`、`stop_device`、`watch_device`、`unwatch_device` | 模型通过这些工具进行调用 |
| **数据源流式传输** | 数据源（摄像头、姿态、麦克风）通过 `read_device` 流式传输 | 摄像头使用 `returnsImages` 能力 |

## 集成清单

用于将新设备集成到 HomeGuard：

- [ ] 设备程序使用 `agnes_mhs` 库
- [ ] 设备通过 `dev.tool()` / `dev.source()` 声明所有工具和数据源
- [ ] 设备拨号连接 AgnesHub URL（出站 WebSocket）
- [ ] 设备处理 `halt` 工具（安全要求）
- [ ] 设备声明安全约束（例如低压保护）
- [ ] 设备返回结构化反馈（成功/失败 + 原因）
- [ ] 摄像头数据源声明 `returnsImages` 能力（如适用）

## 设备程序结构

### 基本模板

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

### 声明工具

工具是设备可以执行的操作：

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

### 声明数据源

数据源是设备提供的数据流：

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

### 安全工具

每个设备**必须**实现 `halt`：

```python
@dev.tool("halt")
async def halt() -> str:
    """Emergency stop. Always allowed."""
    # Stop all motors
    stop_motors()
    return "halted"
```

## API 标准

### 设备工具（模型侧）

模型通过 7 个固定工具与设备交互：

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

### 设备端工具（硬件特定）

设备声明自己的工具（作为参数传递给 `call_device`）：

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

## 技术标准

| 标准 | 版本 | 说明 |
|---|---|---|
| **Node.js** | ≥ 24.10 | Agnes Harness 所需 |
| **Python** | ≥ 3.10 | `agnes_mhs` 所需 |
| **WebSocket** | RFC 6455 | 设备 ↔ AgnesHub 通信 |
| **JSON** | RFC 8259 | 工具参数和响应 |

## 示例：集成新机器人

### 步骤 1：安装依赖

```bash
pip install agnes-mhs jsonschema websockets
```

### 步骤 2：编写设备程序

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

### 步骤 3：运行设备程序

```bash
python my_robot.py
```

### 步骤 4：在 AGH 中验证

```python
# In AGH session
list_devices()
# → ["turpi-01", "my-robot-01"]

read_device(device="my-robot-01", sources=["camera"])
# → {camera: <image>}
```

## 故障排除

### 设备无法连接

- 检查 AgnesHub URL：必须从设备可达
- 检查防火墙：AgnesHub 必须监听 `0.0.0.0:4180`
- 检查设备日志：查找连接错误

### 工具调用失败

- 验证工具已在设备程序中声明
- 检查参数类型是否与声明匹配
- 阅读错误信息：AGH 返回结构化反馈

### 图像未显示

- 确保数据源声明了 `returns_images=True`
- 验证图像格式为 JPEG
- 检查图像尺寸（建议 640×480）

## 资源

- [MHS 协议规范](https://github.com/AgnesAI-Labs/agnes-harness/tree/main/packages/mhs)
- [Agnes Harness 文档](https://github.com/AgnesAI-Labs/agnes-harness/tree/main/docs)
- [HomeGuard 架构](../docs/develop/architecture.md)
