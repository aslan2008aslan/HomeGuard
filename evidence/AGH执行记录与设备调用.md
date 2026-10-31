# AGH 执行记录与设备调用过程

> 本文件对应提交材料第 4 项「运行与验证证据」中的
> **AGH 执行记录**与**工具/设备调用过程**部分。
> 要求：上传**可供人工核查**的 AGH 执行记录与工具或设备调用过程。
>
> **2026-10-11 更新**：本目录已放入 4 份 **AGH 官方诊断导出包**（`agh-diagnostics-*.zip`），
> 第四节原先标注为「⚠ 待导出」的 **P0 缺口已补齐**。新增第 2.6 节为本次
> 「找绿萝 → 靠近 → 读湿度计」任务的完整实测调用链。

---

## 一、本文档的证据性质说明

本文档汇总的**全部内容均来自实际执行**，来源标注如下：

| 标记 | 含义 |
|---|---|
| ✅ **实测** | 已在真机上执行并观察到结果，原始输出记录在源文档中 |
| ✅ **已导出** | 已由 AGH 官方诊断导出，原始文件随本包提交，可解压核查 |
| ⚠ **待补** | 需要补充文件或导出记录才能作为完整证据 |

**本文档不包含任何未经执行的预期结果。**
未能提供的内容一律列入「待补」，不做填充。

---

## 二、已完成的调用记录（实测）

### 2.1 设备接入验证

| 项 | 内容 |
|---|---|
| 调用 | `list_devices` |
| 预期 | 可见 `turpi-01` |
| **实测结果** | ✅ `turpi-01` 出现且状态为 `available`，7 个工具 + 3 个数据源 |
| 意义 | 证明 MHS 协议层已打通，设备成功向 AgnesHub 注册 |

**旁证（设备侧）**：

```
容器 turbopi 内进程：python3 -u /tmp/turpi_device.py ws://192.168.3.149:4180
PPID: 0
与 hub 的连接：192.168.3.187:xxxxx → 192.168.3.149:4180  ESTABLISHED
```

> ⚠ 注意：**`ESTABLISHED` 不等于「能调用」**。实测多次出现半死会话：
> TCP 连接在，但 MHS 数据不流。真正的判据是 **AGH 侧源时间戳为秒级**。

---

### 2.2 前进 + 拍照闭环（本项目最核心的已验证链路）

**完整命令序列**（按实际执行顺序）：

```python
# 步骤 1 —— 确认设备在线且源在推进（时间戳必须是秒级）
read_device(device="turpi-01", sources=["pose"])

# 步骤 2 —— 前进：最低速、指定距离（带进度报告，阻塞直到完成）
call_device(device="turpi-01", tool="drive", args={"distance": 0.5, "speed": 0.1})

# 步骤 3 —— 取图（图像直接进模型上下文）
read_device(device="turpi-01", sources=["front"])
```

**步骤 2 实测返回原文**：

```
turpi-01: drove 0.50 m forward. Now at (1, 0.5) facing 0 degrees,
         position not trusted. Took 5 s.
```

| 观察项 | 实测值 |
|---|---|
| 位移 | 0.50 m 前进 |
| 位置变化 | (0.5, 0.5) → **(1, 0.5)** |
| 朝向 | 0° |
| 耗时 | 5 秒 |
| 定位可信度 | **`position not trusted`**（设备主动标注） |

**步骤 3 实测结果**：✅ 640×480 JPEG 成功进入模型上下文，模型可描述画面内容。

**本链路的证据价值**：

1. 证明了**模型 → AgnesHub → 真机**的完整调用路径可用；
2. 证明了**摄像头图像真的进了模型上下文**（视觉推理的技术前提）；
3. 返回中**自带诚实的定位可信度标注**。

**诚实的保留**（必须一并提交，不得省略）：

- 位移数据来自**航位推算**（无编码器），设备自己标 `position not trusted`；
- 照片与出发前构图接近，**无法从图像内容独立确认位移**；
- `front` 源有 **41% 丢帧**（`Attention: front: 41 % lost`），取图偶有延迟。

---

### 2.3 底盘运动真实性验证

| 验证项 | 方法 | 结果 |
|---|---|---|
| 前进/后退 | 轮子实测转动（25% 占空比） | ✅ 确认 |
| 原地转向 | `angular.z=2.0` 实测转动 | ✅ 确认 |
| `halt` 急停 | 与运动指令同一通道 | ✅ 可用 |

> **转向换算缺陷**：厂商用 `max_linear_speed` 换算角速度，导致占空比只有线速度的 1/7；
> 需 `angular.z≈2.0` 才能驱动轮子。

---

### 2.4 电池读数验证（双路径对照）

| 路径 | 结果 | 状态 |
|---|---|---|
| AGH 侧 `battery` 状态字段 | **恒为空** | ❌ 失效 |
| 串口 SDK 直读（宿主侧） | **7306 mV**（12 次采样 7303–7308 mV，±5 mV） | ✅ 有效 |

**直读命令（实测可用）**：

```bash
PYTHONPATH=/home/pi/demo python3 - <<'PY'
import time, ros_robot_controller_sdk as rrc
b = rrc.Board()
b.enable_reception()          # 必须先开！默认 enable_recv = False
time.sleep(1.0)
for i in range(5):
    print("battery =", b.get_battery(), "mV")
    time.sleep(0.3)
PY
```

**两个必须知道的点**：

1. **必须先 `enable_reception()`**，否则所有读取返回 `None`；
2. **SDK 只在宿主可用**（容器内报 `ModuleNotFoundError`）；
   且会与 ROS 节点争 `/dev/ttyAMA0`，**演示时不要这么做**。

---

### 2.5 音频链路验证

| 项 | 内容 |
|---|---|
| 硬件 | 麦克风与喇叭共用同一 USB 声卡（JMTek，ALSA card 2 / `plughw:2,0`） |
| 实测回环 | 播放 1 kHz 时麦克风 RMS 从 **0.016 → 0.792**（**48×** 跃升） |
| 工具 | `say` / `listen` 均已真机实测 |

---

### 2.6 【新增】本次任务「寻找绿萝 → 靠近 → 读湿度计」的完整调用链

**任务输入（原文）**：

```
寻找绿萝，靠近它，查看绿萝上面插的绿色的湿度计显示的刻度，看看是否缺水，不依赖定位。
过程回复使用中文
```

**证据来源**：`agh-diagnostics-8f055bc6-20261011-033532-*.zip` 内的 `events.jsonl`
（导出序列号 1407 行，会话时间 `2026-10-11T01:19:01Z` 起）。

**调用统计**：设备工具调用共 **60 次**，其中 `call_device` 30 次、`read_device` 28 次、
`list_devices` 1 次。以下为关键节点（序号为 `events.jsonl` 中的 seq）：

| seq | 时间（UTC） | 调用 | 关键返回（原文节选） |
|---|---|---|---|
| 27 | 01:26:32 | `list_devices` | `turpi-01 (TurPi patrol car, robot): available; ... tools: drive, turn, change_view, aim_camera, halt, say, listen; sources: front (image), pose (pose), mic (audio)` |
| 30 | 01:26:32 | `read_device` | `turpi-01 is available. Position uncertain: (-6.36, -9.14) facing 235° on map home, the device does not trust its fix.` |
| 50 | 01:26:33 | `read_device front` | `turpi-01 front: picture 640x480, 0.92 s old.` |
| 71 | 01:26:35 | `call_device drive {1.5, 0.2}` | `turpi-01: drove 0.60 m forward. ... position not trusted. Took 3 s.` |
| 141 | 01:26:54 | `call_device turn {12}` | `turned 12.0 deg left. Now at (-6.99, -10.04) facing 247 degrees` |
| 193 | 01:26:57 | `call_device turn {-25}` | `turned 25.0 deg right. Now at (-7.18, -10.5) facing 224 degrees` |
| 262 | 01:27:21 | `call_device drive {0.3, 0.1}` | `drove 0.30 m forward. ... Took 3 s.` |
| 314 | 01:27:35 | `read_device front` | `turpi-01 front: picture 640x480, 0.82 s old.` |
| 647 | 01:27:48 | `read_device` | **`turpi-01 is offline. Bad: not available; front: newest 10 s old; front: 0/1 per second.`** |
| 723 | 01:27:48 | `read_device` | 设备自行恢复：`turpi-01 is available. Position uncertain: (-8.05, -11.65) ...` |
| 811 | 01:27:54 | `call_device drive {1.5, 0.2}` | `drove 1.50 m forward. Now at (-9.48, -13.95) facing 238 degrees. Took 8 s.` |
| 846 | 01:28:01 | `call_device turn {-35}` | `turned 35.0 deg right.` |
| 1004 | — | `call_device aim_camera {tilt:1700}` | **`aim_camera error (x_gimbal_unavailable): the pan-tilt gimbal does not move the camera on this robot (servo accepts the position but has no torque under load); use change_view to turn the chassis instead.`** |

**两个可直接核查的关键点**：

1. **全程未使用定位坐标导航** —— 任务要求「不依赖定位」。设备返回每次都带
   `position not trusted` / `the device does not trust its fix`，而模型仍完成靠近，
   说明它与任务约束一致：**只用摄像头画面判断朝向与距离**。
2. **`aim_camera` 的真实失败被完整记录** —— 这是 F3 从「已知限制」升级为
   **「有 AGH 侧调用记录佐证的真实失败样例」**的依据（见 `测试样例_失败.md` F3）。

**诚实的保留**：第 647 行出现一次设备 `offline`，随后自行恢复；该中断是真实的，
未从记录中删除。

---

## 三、设备调用过程的核查路径

评委可按以下方式**人工核查**上述调用：

| 核查目标 | 核查方法 |
|---|---|
| 设备是否真的接入了 AGH | `list_devices` 可见 `turpi-01` |
| 设备进程是否健康 | `docker exec turbopi ps -o pid,ppid,cmd \| grep turpi_device` → **恰好 1 个，PPID 0** |
| 设备是否在推数据 | `read_device(turpi-01, sources=["pose"])` → 时间戳**秒级** |
| 图像是否真的来自摄像头 | `read_device(turpi-01, sources=["front"])` → 640×480 JPEG；可与 `http://192.168.3.187:8080/snapshot?topic=/image_raw` 对照 |
| 调用是否被校验 | 越界调用会被 AgnesHub 按设备申报拒绝 |

---

## 四、AGH 执行记录导出（⚠ 部分已补齐）

### 4.0 【新增】已随包提交的 4 份 AGH 诊断导出包

以下文件已放入 `submission/` 根目录，**可直接解压核查**：

| 文件 | 大小 | 会话时长 | 设备工具调用 | 内容摘要 |
|---|---|---|---|---|
| `agh-diagnostics-08b66b49-20261011-022353-成功的.zip` | 0.11 MB | 01:26:31 → 02:23:28 | 42 次 | 「找绿萝→读湿度计」任务闭环（一个版本） |
| `agh-diagnostics-8f055bc6-20261011-033532-失败的.zip` | 0.21 MB | 01:19:01 → 03:34:49 | **60 次** | **同一任务的另一轮完整执行（含设备 offline 与 aim_camera 失败）** |
| `agh-diagnostics-08b66b49-20261011-135445-失败的.zip` | 0.11 MB | 01:26:31 → 13:53:58 | 42 次 | 同上任务导出，但会话尾部时间跨度异常大（见下） |
| `agh-diagnostics-b2351679-20261011-035240-调试会话.zip` | 1.38 MB | 10-10 13:31 → 10-11 03:51 | 74 次 | 环境搭建/事故记录等开发过程会话 |

**每包内容**：`system.json`（环境与模型信息）、`events.jsonl`（完整事件流）、
`trace.json`、`logs/host.jsonl`、`logs/daemon.jsonl`、`index.html`（可视化查看页）。

> ✅ **`system.json` 解决了「模型名称与版本」这个必填项**（原先只能标「待补」）：
> `model: "deepseek-flash"`（显示名 **DeepSeek V4.1 Flash**，provider `deepseek`）；
> `agh.version: "0.0.0"`；`node: 24.15.0`；`platform: win32 / x64 / 10.0.26100`。
> 另有备选账号 `agnes-3.0-flash`。此项信息为**官方导出实测值，非推测**。

**⚠ 两点必须自行核实后再提交**：

1. 两份标注「失败的」导出，其 `events.jsonl` 中助手最终结论实际是
   **已完成任务并给出湿度计指针方位**（详见 `测试样例_正常.md`）。文件名中的
   「失败」与内容不一致，**命名需由队伍确认含义**（可能指当次录制或链路状态）。
2. `-135445-失败的` 包的会话时间跨度跨越约 12 小时，疑似包含空闲等待段落，
   **内容需抽查后再引用**。

### 4.1 仍未补的证据

| # | 证据 | 获取方式 | 状态 |
|---|---|---|---|
| 1 | ~~AGH 执行记录导出~~ | ~~从 AGH 导出~~ | ✅ **已补齐**（见 4.0） |
| 2 | **session jsonl** | `pnpm --filter @agnes/mhs dev <host:port> --record session.jsonl` | ⚠ 待录制 |
| 3 | **schema 逐条校验** | `python -m agnes_mhs.validate` 对 jsonl 逐条校验 | ⚠ 待运行 |
| 4 | **`mhs-check` 一致性报告** | `uv run python -m agnes_mhs.check --report report.json` | ⚠ **阻塞已解除，未跑**（见下） |
| 5 | Activity 标签页调用卡截图 | 浏览器截图 | ⚠ 待截 |
| 6 | 设备侧进程/日志证据 | `ps`、`wc -c`、`tail` 输出存档 | ⚠ 待存档 |

### 4.2 `mhs-check` 说明

> **2026-10-13 更新：阻塞原因已查明并解除，但队伍选择暂不运行。**
>
> **原因**：容器内原本缺少 `jsonschema` 模块，导致 `agnes_mhs` 库无法导入，
> 检查工具无法启动。**该依赖已装上**（`jsonschema 4.26.0`），
> 现在 `agnes_mhs` 导入与 `mhs-check` 命令**均正常可用**。
>
> **为何仍未跑**：`mhs-check` 要求设备断开 AgnesHub、连接测试台（端口 8800），
> 且需先停 keeper，**会中断当前正在使用的 AGH 会话**。
> 队伍于 2026-10-13 决定：**待视频重录完成后随时补跑**。
> 补跑要点见 `../02_可运行作品/src/小车拉取清单.md` §7.3。

会按注册信息自动判定适用 profile，并输出 `pass` / `fail` / `warn` / `skip` / `manual`
五种结果（**有 fail 时退出码非零**）：

| Profile | 适用条件 |
|---|---|
| Core | 必测 |
| Motion | 有 motion 工具 |
| Pause | 可暂停 |
| Perception / Streaming | 有数据源 |
| Maps | 有地图或 placement |
| Video | 有视频源 |

```bash
# 终端 1：测试台
uv run python -m agnes_mhs.check --report report.json
# 终端 2：被测设备（不带地址即默认连 8800）
uv run python turpi_device.py
```

> `manual` 类别需要人工判断（如「真的停下了吗」），带 `--interactive` 做物理项。

### 4.3 关于执行记录的重要性

指南把「**无法提供执行记录、测试材料、专业验证或可复现运行说明**」
明确列为**不进入评审**的情形之一。

同时，评分维度「Agnes Harness 与模型执行闭环」占本科生组 **20%** ——
执行记录是这一项的直接证据。**目前已随包提供 4 份真实导出，此项缺口已补齐。**

---

## 五、下游文件

| 文件 | 内容 |
|---|---|
| `测试样例_正常.md` | 正常流程样例 |
| `测试样例_边界.md` | 边界条件样例 |
| `测试样例_失败.md` | 失败与异常处理样例（**含已实测的可写实案例**） |
