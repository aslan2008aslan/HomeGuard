> 本文档另有[英文版本](architecture.md)。

# HomeGuard 架构

本文档描述 HomeGuard 的系统架构。

## 概述

HomeGuard 采用**主机-设备**架构，其中：

- **主机（Windows PC）**：运行 Agnes Harness + AgnesHub + LLM；负责任务规划与编排
- **设备（TurboPi）**：运行设备程序；声明能力；接受调用
- **网络**：设备通过出站 WebSocket（MHS 协议）拨号连接主机

## 系统图

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

## 关键设计决策：调用方向

设备**主动拨号**连接主机的 AgnesHub——而非相反方向。这带来三个好处：

1. **设备无需开放入站端口** —— 仅需一个出站 WebSocket（最小化攻击面）
2. **协议层由 AGH 处理** —— 主机端无需编写胶水代码来"与机器人通信"
3. **每次调用均根据设备声明进行验证** —— 设备声明其能力；AGH 负责强制执行

## 核心模块

### 1. 任务规划（LLM + AGH）

LLM 接收自然语言输入并规划执行步骤：

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

### 2. 设备能力声明（MHS）

设备向 AgnesHub 声明其能力：

| 工具/数据源 | 类型 | 描述 | 状态 |
|---|---|---|---|
| `drive` | tool | 按指定距离（米）前进/后退 | ✅ 已验证 |
| `turn` | tool | 原地旋转指定角度（度） | ✅ 已验证 |
| `change_view` | tool | 改变摄像头角度（turn 的语义封装） | ✅ 已验证 |
| `aim_camera` | tool | 云台控制（硬件扭矩不足；**始终失败**） | ⚠ 有意为之 |
| `halt` | tool | 紧急停止 | ✅ 已验证 |
| `say` | tool | 语音播报文本（无 TTS 时回退为蜂鸣） | ✅ 已验证 |
| `listen` | tool | 监听 N 秒并报告音量 | ✅ 已验证 |
| `front` | source | 摄像头图像（640×480 JPEG） | ✅ 已验证 |
| `pose` | source | 里程计位姿（x, y, yaw, ok）—— **`ok: false`（无编码器）** | ✅ 如实上报 |
| `mic` | source | 麦克风音频（按需录制） | ✅ 已验证 |

### 3. 视觉推理（LLM + 摄像头）

摄像头图像通过 `read_device(front)` 以 `returnsImages` 能力进入模型上下文：

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

当置信度较低时，系统自动调整摄像头角度并重试：

```python
# Low confidence → retry
change_view(angle=15)  # Rotate 15 degrees
read_device(sources=["front"])  # Re-capture
# → Second judgment with improved confidence
```

### 4. 执行反馈循环（AGH）

每次设备调用都会向模型返回结构化反馈：

```python
# Successful drive
call_device(device="turpi-01", tool="drive", args={"distance": 0.5, "speed": 0.1})
# → "drove 0.50 m forward. Now at (1, 0.5) facing 0 degrees. Took 5 s."

# Failed gimbal call
call_device(device="turpi-01", tool="aim_camera", args={"pan": 45})
# → Error: "gimbal torque insufficient. Suggestion: use change_view instead."
```

模型读取这些结果并相应调整策略——实现**闭环执行**。

## 部署架构

| 层级 | 组件 | 部署方式 |
|---|---|---|
| **主机** | Agnes Harness + AgnesHub | Windows PC，Node.js ≥ 24.10 |
| **主机** | LLM API | DeepSeek V4.1 Flash（1M 上下文） |
| **网络** | WebSocket | 设备 → 主机 :4180（从设备出站） |
| **设备** | turpi_device.py | Raspberry Pi 5 上的 Docker 容器 |
| **设备** | ROS2 栈 | mecanum_chassis、usb_cam、web_video_server |

**安全说明：** AgnesHub **无认证和加密**（设计如此）。它必须仅在受信任的本地网络上监听——**切勿暴露到公共互联网**。

## 数据流

1. **用户输入** → AGH Web 界面中的自然语言指令
2. **任务规划** → LLM 解析输入并生成执行计划
3. **设备发现** → 模型调用 `list_devices` 查找可用设备
4. **状态检查** → 模型调用 `read_device(pose)` 确认设备在线并检查电量
5. **导航** → 模型调用 `drive` / `turn` / `change_view` 移动机器人
6. **观测** → 模型调用 `read_device(front)` 捕获摄像头图像
7. **视觉推理** → LLM 分析图像并输出结构化判断
8. **不确定性处理** → 若置信度低，模型调整角度并重试
9. **结果报告** → 模型输出最终结论及依据
10. **执行日志** → AGH 记录所有调用以供审计和验证

## 安全模型

- **设备拨号主机** —— 设备无入站端口
- **能力验证** —— AGH 根据设备声明验证每次调用
- **紧急停止** —— `halt` 工具始终可用
- **无认证/加密** —— 仅可在受信任的局域网内运行
- **如实上报故障** —— 硬件限制如实记录，不做隐瞒

## 可扩展性

### 添加新设备

1. 使用 `agnes_mhs` 库实现设备程序
2. 通过 `dev.tool()` / `dev.source()` 声明工具和数据源
3. 设备拨号连接 AgnesHub URL
4. 模型现在可通过相同的 7 个固定工具调用新设备

### 添加新任务

1. 在 AGH 中输入自然语言描述
2. LLM 规划执行步骤
3. 无需修改代码（前提是设备能力充足）

## 已知限制

1. **云台不可用** —— 舵机扭矩不足
2. **无编码器** —— 位姿随时间漂移
3. **低压保护已禁用** —— 需手动检查
4. **无认证机制** —— 仅限受信任的局域网
5. **Windows 构建未验证** —— 推荐使用 Linux
