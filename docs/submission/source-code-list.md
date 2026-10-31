# 团队源码清单与交付范围（src/ 交付说明）

> 本文件对应提交材料第 2 项「可运行作品」中的**源码交付**部分。
> 目标：明确**哪些文件是团队原创、哪些来自厂商**，并给出可执行的取出与自查步骤。
>
> **状态：目录与清单已就绪；设备主程序仍在小车上，待取出。**
> 最后更新：2026-10-11

---

## 一、当前事实（以真实文件系统为准）

### 1.1 本工作区**已有**的团队原创文件（27 个工具脚本 + 5 篇文档）

`F:\turbopi-AGH2\tools\` 实测内容：

| 类别 | 文件 |
|---|---|
| **设备与链路恢复** | `start_device.sh`、`clean_restart.sh`、`reconnect_device2.sh`、`recover_stack.sh`、`start_patched.sh` |
| **保活服务** | `keeper.sh`、`install_keeper_service.sh`、`restart_keeper.sh`、`turpi-keeper.service` |
| **断线重连补丁** | `add_reconnect.py` |
| **上电与诊断** | `post_power_on.sh`、`full_check.sh`、`verify_all.sh`、`log_growth.sh`、`why_drop.sh` |
| **串口与电池** | `bat.sh`、`read_battery_correct.sh`、 `loopback_test.sh`、`trace_serial.sh` |
| **摄像头修复** | `fix_camera.sh`、`fix_snapshot.sh`、`check_topics.sh` |
| **安全与清理** | `emergency_stop.sh`、`clean_junk.sh`、`clean_workspace.ps1` |
| **协议探测** | `probe_hub.mjs`、`probe_seq.mjs` |

`F:\turbopi-AGH2\docs\` 实测内容（5 篇）：

`小车接入实测记录.md`、`恢复后待办与验证清单.md`、`成功关键因素全记录.md`、`保活服务与乱动事故记录.md`、`设备掉线根因与重连方案.md`

> ⚠ **修正**：本文件早期版本称「当前工作区实际只有 13 个文件」，
> 且 `README.md` 的目录表称存在 `tools/openssh_to_ppk.mjs`。
> **两者均与实际不符** —— 实测 `tools/` 下有 **27 个**脚本，且**没有** `openssh_to_ppk.mjs`。

### 1.2 仍**不在**本工作区、必须从车上取出的文件

| 文件 | 推断位置 | 说明 |
|---|---|---|
| **`turpi_device.py`** | 容器内 `/tmp/turpi_device.py`；补丁版为 `/tmp/turpi_device_patched.py` | **★ 团队原创主程序**，最重要 |
| `recover.sh` | 树莓派 `~/turbopi_agh/recover.sh` | 恢复脚本（注意：该脚本已知有 bug，见 §四） |
| `turpi_device.py` 的宿主副本 | 树莓派 `~/turbopi_agh/` | 打补丁用的宿主版本 |

以下文件在现有文档中**被提及但从未证实存在**，需在车上逐一核实：

`cam_ok.py`、`direct_gimbal.py`、`turn_cal.py`、`openssh_to_ppk.mjs`

---

## 二、取出步骤（车在线后执行）

> ⚠ 当前 `turpi-01` **offline**。执行前先给车开机、等 60 秒、确认 `ping 192.168.3.187` 无丢包。

### 2.1 先列清单，不急着下载

```powershell
$KEY = "$env:USERPROFILE\.ssh\turpi_ed25519.ppk"

# 宿主目录
plink -ssh -batch -i $KEY pi@192.168.3.187 "ls -la ~/turbopi_agh/ 2>/dev/null"

# 容器内 /tmp 下的 py 文件
plink -ssh -batch -i $KEY pi@192.168.3.187 "docker exec turbopi ls -la /tmp/*.py 2>/dev/null"
```

### 2.2 下载设备主程序

```powershell
$PSCP = "C:\Program Files\PuTTY\pscp.exe"

# 先从容器复制到宿主（/tmp 在 overlayfs 只读下层，直接 pscp 取不到）
plink -ssh -batch -i $KEY pi@192.168.3.187 "docker cp turbopi:/tmp/turpi_device.py /tmp/_get_turpi.py"

# 再从宿主下载
& $PSCP -batch -i $KEY pi@192.168.3.187:/tmp/_get_turpi.py ".\02_可运行作品\src\turpi_device.py"

# 若有补丁版，一并取出（两者 md5 不同，需注明）
plink -ssh -batch -i $KEY pi@192.168.3.187 "docker cp turbopi:/tmp/turpi_device_patched.py /tmp/_get_patched.py 2>/dev/null; true"
& $PSCP -batch -i $KEY pi@192.168.3.187:/tmp/_get_patched.py ".\02_可运行作品\src\turpi_device_patched.py"
```

> **必须核对版本**：实际在跑的是哪一份？用
> `docker exec turbopi ps -eo cmd | grep turpi_device` 看命令行指向 `/tmp/turpi_device.py` 还是
> `_patched.py`。**交付的必须是实际在跑的那份**，否则复现说明会与实际不符。

---

## 三、src/ 目标结构

```
02_可运行作品/
├─ 复现运行说明.md            ✅ 已有
├─ 源码位置说明.md            ✅ 已有
├─ 团队源码清单与交付范围.md    ✅ 本文件
└─ src/                       ✅ **已交付**（2026-10-13 扩充，共 72 文件）
   ├─ turpi_device.py         ✅ 设备主程序（与实际运行版一致）
   ├─ car_scripts/            ✅ 25 个车内运维/标定脚本
   ├─ car_config/             ✅ 2 个配置（systemd unit + 厂商 yaml）
   ├─ car_evidence/           ✅ 19 张实拍 JPEG
   ├─ tools/                  ✅ 27 个（工作站）
   ├─ docs/                   ✅ 5 篇（工作站）
   ├─ 来源说明.md              ✅ 逐文件来源标注
   └─ 小车拉取清单.md          ✅ 拉取项说明与合规扫描
```

---

## 四、交付前自查（12 项）

| # | 检查项 | 状态 |
|---|---|---|
| 1 | `turpi_device.py` 已取出并放入 `src/` | ✅ **已完成**（2026-10-12） |
| 2 | 已确认交付的是**实际在跑**的那一份（原版/补丁版） | ✅ 含 `MHS-RECONNECT` 标记，与运行版本一致 |
| 3 | `turpi_device.py` 头部加**来源与用途**注释 | ✅ 文件自带 docstring |
| 4 | `recover.sh` 已取出，并**注明其已知 bug** | ⚠ **仍在车上** |
| 5 | `tools/` 下 27 个脚本已复制进 `src/` | ✅ **已完成** |
| 6 | `docs/` 下 5 篇文档已复制进 `src/` | ✅ **已完成** |
| 7 | **源码中不含密钥、密码、token** | ✅ **已扫描**（主程序与 tools） |
| 8 | **不含默认密码 `raspberrypi`** | ✅ `tools/` 已扫描无密码字面值 |
| 9 | **内网 IP 已脱敏或参数化** | ⚠ **9 个脚本写死 `192.168.3.149`**（主程序无） |
| 10 | 路径描述与 `复现运行说明.md` 一致 | ✅ |
| 11 | 已确认哪些是团队原创、哪些来自厂商 | ✅ 见 §六 与 `src/来源说明.md` |
| 12 | 与 `06_第三方素材说明/` 的表述一致 | ✅ |

---

## 五、⚠ 已实测的两项合规风险（开源前必处理）

### 5.1 内网 IP —— ✅ 已定：**不处理**

实测以下位置写死了开发机 IP `192.168.3.149`：

| 位置 | 文件 |
|---|---|
| `src/tools/` | `clean_restart.sh`、`keeper.sh`、`start_device.sh`、`recover_stack.sh`、`restart_keeper.sh`、`reconnect_device2.sh`、`start_patched.sh`、`install_keeper_service.sh`、`turpi-keeper.service`（9 个） |
| `src/car_scripts/` | `cam_diag.py`、`cam_ok.py`、`camera_device_diag.py`、`camera_device_logged.py`、`endpoint_probe.py`、`inspect_payload.py`、`keeper.sh`（7 个） |
| `src/car_config/` | `turpi-keeper.service`（1 个） |

**队伍决定（2026-10-13）**：**内网 IP 信息不属于秘密，保留原样、不做参数化**。

> 理由：该地址为局域网内网地址（RFC1918），不暴露公网服务，亦不含个人信息。
> 指南第十二节要求的「个人信息」与本项无关。

### 5.2 默认密码 `raspberrypi`

`免密登录配置.md` 与 `上电前检查清单.md` 中出现过该默认密码，且 `START_HERE.md` 记录了
备用密码。**开源前必须改掉车上的实际密码**，并从文档中删除该字面值。

> 注：`tools/` 目录下**未发现**密码字面值（已实测检索）。

---

## 六、团队原创 vs 厂商组件（交付边界）

### ✅ 团队原创（可提交）

| 内容 | 说明 |
|---|---|
| `turpi_device.py` | MHS 设备程序：底盘运动、图像源、位姿源、音频、钩子 |
| `tools/` 全部 27 个脚本 | 恢复、诊断、保活、重连补丁等 |
| `docs/` 全部 5 篇文档 | 实测记录、恢复指南、复盘 |
| `submission/` 全部材料 | 提交材料本身 |

### ❌ 非团队原创（**不得**作为本队作品提交）

| 组件 | 归属 | 位置 |
|---|---|---|
| TurboPi SDK / 例程 | Hiwonder（厂商） | `~/board_demo`、`~/turbopi`、`/home/pi/demo` |
| ROS2 工作区与厂商节点 | 厂商预装 | `~/ros2_ws`、`~/ros2_ws/src/driver/` |
| `ros_robot_controller_node.py` | 厂商 | `~/ros2_ws/src/driver/ros_robot_controller/` |
| `agnes_mhs` 库 | Agnes（Apache-2.0） | 容器内 `/opt/agh_mhs/python/src` |
| ROS2 Humble / picamera2 / PyAV | 第三方开源 | 系统与容器预装 |

> **取源码时最容易误交付的是 `turpi_device.py` 中 import 的厂商模块**。
> 该文件**本身是团队原创**，但**不得把厂商 SDK 源码一并复制进 `src/`**。
> 交付时应只放团队写的代码，并说明依赖的厂商组件如何获取（见
> `06_第三方素材说明/第三方素材来源与授权.md`）。

---

## 七、待补

| # | 项 | 依赖 |
|---|---|---|
| 1 | ~~`turpi_device.py`（原版 + 补丁版）取出到 `src/`~~ | ✅ **已完成** |
| 2 | `recover.sh` 取出并注明已知 bug | 车在线 |
| 3 | 核实 `cam_ok.py` / `direct_gimbal.py` / `turn_cal.py` 是否存在 | 车在线 |
| 4 | ~~`tools/` 与 `docs/` 复制进 `src/`~~ | ✅ **已完成** |
| 5 | 内网 IP 参数化（9 个文件） | 队伍决定 |
| 6 | 车端默认密码更改 + 文档脱敏 | 队伍执行 |
| 7 | ~~逐文件来源标注~~ | ✅ **已完成**（`src/来源说明.md`） |
| 8 | ~~确认最终交付的是实际在跑的那一份~~ | ✅ **已完成** |
