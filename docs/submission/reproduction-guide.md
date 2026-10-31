# 复现运行说明

> 本文件对应提交材料第 2 项「可运行作品」
> 要求：提供可访问应用、安装包或**可复现运行方式**，并说明环境、依赖、模型、数据、
> 专业工具、仿真环境或设备接口。

---

## 一、运行方式概述

本项目**不提供安装包**，采用「源码 + 可复现运行步骤」的方式交付。

运行需要**两端**：

| 端 | 硬件/环境 | 承担的工作 |
|---|---|---|
| **上位机** | Windows PC | 运行 Agnes Harness + AgnesHub + 模型，做任务编排与决策 |
| **设备端** | Hiwonder TurboPi（树莓派 5） | 运行设备程序，申报能力，接受调用 |

两端通过**一条出站 WebSocket**（设备 → 上位机 `:4180`）连接。

> **调用方向**：**设备主动 dial 上位机的 AgnesHub**，不是上位机去连设备。
> 设备侧不开任何入站端口。

---

## 二、环境要求

| 组件 | 版本 | 说明 |
|---|---|---|
| **上位机 Node.js** | ≥ 24.10 | 运行 Agnes Harness CLI |
| **AGH** | 源码构建 | 官方目前无正式安装包 |
| 树莓派系统 | Debian 12 (bookworm), aarch64 | 64 位，可直接用官方 wheel |
| 树莓派 Python | 3.11.2（宿主）/ 3.10（容器内） | 满足 `agnes_mhs` 要求的 3.10+ |
| 容器 | ROS2 Humble（厂商镜像 `turbopi`） | 厂商预装 |
| `agnes_mhs` 依赖 | `jsonschema`, `websockets` | Python 包 |
| 网络 | 上位机与树莓派**同局域网** | 需为可信网络 |

> ⚠ **AgnesHub 无鉴权、无加密**（设计如此）。只能在可信局域网内监听网络地址，
> **禁止暴露到公网**。

---

## 三、步骤 0：构建 Agnes Harness（上位机）

> 官方目前**没有安装包，只能用源码构建**（安装文档原文：
> 「当前分发方式为源码构建，尚无正式公共安装包」）。
> 构建产物在 `packages/cli/dist/local/`，搬运时要**整个目录一起搬**，不能只复制入口文件。

```powershell
git clone https://github.com/AgnesAI-Labs/agnes-harness.git
cd agnes-harness
# Node >= 24.10；pnpm 10.34.5
# （Node 24 自带 corepack；Node 25+ 需 npm i -g pnpm@10.34.5）
pnpm install --frozen-lockfile
pnpm --filter @agnes/cli build:local
node packages/cli/dist/local/agnes.mjs --help
```

**Windows 构建的风险（官方原文，三句话，描述要精确）**：

- 「文档中的 PowerShell 示例**尚未在 Windows 实机执行**」——
  未验证的是文档里那几段命令本身，不是 Windows 构建能力；
- 「Windows 已有构建与部分验收代码」—— 该路径有代码支持，不是空白；
- 「符号链接、受限 token、网络沙箱、安装升级及签名仍需分别验证」。

旁证：限制页写「Recorded local process checks used macOS/Node 24. Linux/Windows ...
need separate acceptance」，且 2026-09-24 的验证记录环境是 macOS arm64 + Node 24.20.0。
**结论：Windows 属官方未背书路径。**

> **方案 B（若 Windows 构建失败）**：树莓派本身就是 Linux，
> 直接在树莓派上构建 AGH 并跑 hub，设备与 hub 同机（走回环）。
> 这样避开 Windows 原生构建的坑。代价是小车算力要同时承担 hub。
> 即使走方案 B，**调用方向不变**，只是设备程序里的 URL 换成回环地址。

---

## 四、步骤 1：安装 MHS 插件

```powershell
# 1) 构建并安装插件（走正常 package 流程，需确认预览）；装完默认是 disabled
pnpm --filter @agnes/mhs plugin:install

# 2) 起 Web，并告知 hub 的 origin（不加这个 CSP 会拦住面板连接）
$env:AGNES_HUB_LISTEN = '0.0.0.0:4180'
$env:AGNES_HUB_ORIGIN = 'http://127.0.0.1:4180'
node packages/cli/dist/local/agnes.mjs serve --port 4177 --profile local-dev

# 3) 浏览器里：Settings → Plugin management → Installed 里
#    打开 @agnes/mhs → Confirm enable
```

### 环境变量（daemon 只在启动时读一次）

| 变量 | 谁读 | 含义 | 本项目值 |
|---|---|---|---|
| `AGNES_HUB_LISTEN` | daemon（跑插件） | hub 监听地址 | **`0.0.0.0:4180`**（必须，否则小车连不上） |
| `AGNES_HUB_DATA` | daemon | hub 数据目录，存 `maps.json` | 默认 `<AGH_HOME>/hub` |
| `AGNES_HUB_ORIGIN` | Web 服务 | hub 的 http origin，加进 workbench 的 CSP | `http://127.0.0.1:4180` |

**验证装好了的标志**：workbench 右侧出现 Devices 面板；
`http://127.0.0.1:4180/` 能单独打开设备页。

### 入站放行（限本地子网，需管理员）

```powershell
netsh advfirewall firewall add rule name="AgnesHub 4180" dir=in action=allow `
  protocol=TCP localport=4180 remoteip=LocalSubnet profile=any
```

> ⚠ 开发机实测 `LocalFirewallRules: N/A (GPO-store only)` —— 策略由**组策略托管**，
> 本地开关未必生效。确认办法：`netsh advfirewall show allprofiles state`。

---

## 五、步骤 2：部署设备程序（TurboPi 侧）

> ✅ **2026-10-12：团队源码已交付。** 本节路径现以 `src/` 为准。
> 交付内容见 `src/来源说明.md`。

### 5.1 连接小车

```powershell
$KEY = "$env:USERPROFILE\.ssh\turpi_ed25519.ppk"
plink -ssh -batch -i $KEY pi@192.168.3.187 "hostname"
# 期望输出：raspberrypi
```

| 项 | 值 |
|---|---|
| 主机 | `192.168.3.187`（静态 IP）· 用户 `pi` |
| 私钥 | `~/.ssh/turpi_ed25519.ppk`（**ed25519**） |

> ⚠ **不要用 RSA 密钥**：Debian 12 的 sshd 已移除 `ssh-rsa`（SHA-1），会被拒。
> ⚠ **不要用 `ssh.exe`**：本机 OpenSSH 客户端在自动化 shell 中被拦截、零输出。

### 5.2 拉起 ROS2 栈（容器重启后不自启！）

```powershell
plink -ssh -batch -i $KEY pi@192.168.3.187 "bash ~/turbopi_agh/recover.sh"
```

**判据**：容器 `turbopi` 是 Up，且以下四个进程都在 ——
`mecanum_chassis_node`、`usb_cam`、`web_video_server`、`ros_robot_controller`。
缺任何一个都先修，别急着启动设备程序。

### 5.3 【先测电量】

```powershell
# 脚本见仓库 tools/bat.sh
& "C:\Program Files\PuTTY\pscp.exe" -batch -i $KEY tools\bat.sh pi@192.168.3.187:/tmp/bat.sh
plink -ssh -batch -i $KEY pi@192.168.3.187 "bash /tmp/bat.sh"
```

| 电压 | 含义 | 建议 |
|---|---|---|
| ≥ 7600 mV | 充满 | 可长时间跑演示 |
| 7200–7600 mV | 充足 | 可跑 |
| 7000–7200 mV | 偏低 | **只做短测试** |
| < 6900 mV | 危险 | **别跑运动**，先充电 |

> ⚠ **低电量保护是失效的**（根因见 `../04_运行与验证证据/测试样例_失败.md` F2）。
> **演示前必须人工看电压，不能指望车自己保护自己。**
> 上次就是因为没看电量直接跑，最后电池耗尽硬关机。

### 5.4 启动设备程序（必须先清残留）

```powershell
# 脚本见仓库 tools/clean_restart.sh
& "C:\Program Files\PuTTY\pscp.exe" -batch -i $KEY tools\clean_restart.sh pi@192.168.3.187:/tmp/clean_restart.sh
plink -ssh -batch -i $KEY pi@192.168.3.187 "sed -i 's/\r$//' /tmp/clean_restart.sh; bash /tmp/clean_restart.sh"
```

脚本会：清除**容器内与宿主**全部同脚本进程 → 验证 socket 清空 → **只启一个** → 验证日志增长。

**铁判**：启动前进程数必须为 **0**；启动后必须为 **1**。不是 1 就别往下跑。

> ⚠ **`192.168.3.149` 是开发机自己的局域网 IP**，写死在脚本里。
> 换网络环境后该地址改变，小车将连不上。**每次恢复前先确认本机 IP**：
> ```powershell
> Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.IPAddress -like "192.168.*"}
> ```

### 5.5 三个必须遵守的约束（都踩过坑）

| 约束 | 原因 |
|---|---|
| **必须 `source ~/ros2_ws/.zshrc`** | 否则 `ModuleNotFoundError: No module named 'rclpy'` |
| **重定向要放在 `-c` 引号之内** | 放外面会重定向 docker 自己的 stdout（空的），日志永远是 0 字节 |
| **预检用 python，不用 `bash /dev/tcp`** | 该容器里 `/dev/tcp` 会**假报 FAIL**，曾拦住本该成功的启动 |

---

## 六、步骤 3：确认可用（六条判据）

```python
read_device(device="turpi-01", sources=["pose"])
# 期望：available，且源时间戳为秒级
read_device(device="turpi-01", sources=["front"])
# 期望：返回 640×480 JPEG
```

完整六条判据见 `../01_项目说明/项目说明.md` 第 6.1 节。

---

## 七、外部能力与接口说明

对应提交要求中的「说明环境、依赖、模型、数据、专业工具、仿真环境或设备接口」：

| 类别 | 本项目的具体内容 |
|---|---|
| **环境** | 上位机 Windows + 设备端 Debian 12 aarch64，同一局域网 |
| **依赖** | Node ≥ 24.10、AGH（源码构建）、`agnes_mhs`（`jsonschema`、`websockets`） |
| **模型** | ✅ **已填**：**DeepSeek V4.1 Flash**（上下文 **1M**；内部 id `deepseek-flash`，provider `deepseek`）。使用环节：任务规划 + 视觉推理。调用方式：经 Agnes Harness 调用 |
| **数据** | 设备实时产生的图像（640×480 JPEG）与位姿；无外部数据集 |
| **专业工具** | ROS2 Humble（厂商容器）、`picamera2`、PyAV、`ros_robot_controller_sdk` |
| **仿真环境** | **无** —— 本项目使用**真实硬件**，不使用仿真 |
| **设备接口** | **MHS 协议层**：设备主动 dial AgnesHub，申报工具/数据源/状态；模型经 7 个设备工具间接调用 |

### 设备接口明细

| 接口 | 类型 | 说明 |
|---|---|---|
| `drive` | tool | 前进/后退指定距离（米），带进度与暂停 |
| `turn` | tool | 原地转指定角度（度） |
| `change_view` | tool | 换视角 |
| `aim_camera` | tool | 云台（硬件无扭矩，**总是报错，设计如此**） |
| `halt` | tool | 急停 |
| `say` | tool | 朗读（无 TTS 时回退提示音） |
| `listen` | tool | 听几秒并报告响度 |
| `front` | source image | 摄像头 JPEG |
| `pose` | source pose | `{map, x, y, yaw, ok}`，**`ok: false` 表示定位不可信** |
| `mic` | source audio | 麦克风（按需录音） |

---

## 八、复现性说明与限制

| 项 | 说明 |
|---|---|
| **可复现程度** | 上位机侧与设备侧步骤均可按本文复现；**依赖团队源码**（待取出） |
| **厂商依赖** | TurboPi SDK 与 ROS2 工作区为厂商预装，**不随本仓库分发**；需使用同型号硬件 |
| **硬件先例** | 官方 MHS 验收**不含物理设备**，本项目为首个真实硬件接入案例，真机问题局限于设备程序内部 |
| **已知不稳定** | nerve 通道 send-Q 偶有积压（遗留未定位）；`front` 41% 丢帧 |
| **安全边界** | AgnesHub 无鉴权无加密，**仅限可信局域网**，禁止暴露公网 |

---

## 九、待补

| # | 项 | 说明 |
|---|---|---|
| 1 | ~~团队原创源码~~ | ✅ **已交付**到 `src/`（2026-10-12） |
| 2 | `recover.sh` 与其余候选源码 | 仍在车上，待取出 |
| 3 | ~~模型名称、版本、调用方式~~ | ✅ **已填**（**DeepSeek V4.1 Flash**，1M 上下文） |
| 4 | 确切的构建命令输出 | 建议附一次实际构建成功的记录 |
