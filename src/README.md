# HomeGuard 源码说明

> 本目录包含 HomeGuard 家庭服务机器人自主巡检框架的全部源码。
> 最后更新：2026-10-31

## 目录结构

```
src/
├── turpi_device.py              # 设备端主程序（运行在树莓派）
├── tools/                       # 工作站工具脚本（运行在 Windows 主机）
├── car_scripts/                 # 设备端运维脚本（运行在树莓派）
├── car_config/                  # 设备端配置文件
├── car_evidence/                # 设备实拍照片（调试证据）
└── docs/                        # 技术文档
```

## 部署位置总览

| 文件/目录 | 部署位置 | 作用 |
|-----------|----------|------|
| `turpi_device.py` | **树莓派**（Docker 容器内） | 设备端主程序，连接 AgnesHub，申报能力，接受调用 |
| `tools/*` | **Windows 主机** | 运维工具脚本，用于部署、调试、监控 |
| `car_scripts/*` | **树莓派** | 设备端运维脚本，用于诊断、修复、保活 |
| `car_config/*` | **树莓派** | 系统配置文件（systemd 服务、舵机参数） |
| `car_evidence/*` | 仅用于文档 | 设备实拍照片，证明摄像头出图能力 |
| `docs/*` | 仅用于文档 | 技术文档，记录调试过程和解决方案 |

---

## 1. 设备端主程序

### `turpi_device.py`

**部署位置**：树莓派 Docker 容器 `turbopi` 内（`/tmp/turpi_device.py`）

**作用**：
- 主动连接上位机 AgnesHub（WebSocket 出站连接）
- 申报设备能力（7 个工具 + 3 个数据源）
- 接受模型调用，执行移动、转向、拍照等操作
- 推送摄像头图像、位姿数据
- 实现断线重连机制（`MHS-RECONNECT` 补丁）

**申报的能力**：
- **工具**：`drive`（前进后退）、`turn`（转向）、`change_view`（换视角）、`aim_camera`（云台控制，硬件故障）、`halt`（急停）、`say`（语音播报）、`listen`（监听）
- **数据源**：`front`（摄像头图像）、`pose`（位姿）、`mic`（麦克风）

**安全设计**：
- 急停时清零底盘并居中云台
- 运动工具在 `finally` 块中清零底盘
- 运动循环调用 `checkpoint()`，支持暂停/停止
- 低电量时拒绝运动（注：当前因 ROS 话题无发布者，此功能未生效）

---

## 2. 工作站工具脚本（`tools/`）

**部署位置**：Windows 主机（通过 SSH 远程操作树莓派）

**作用**：在开发机上运行，通过 SSH 连接树莓派，执行部署、调试、监控任务。

### 2.1 设备与链路恢复

| 脚本 | 作用 |
|------|------|
| `start_device.sh` | 启动设备程序（单次） |
| `clean_restart.sh` | 清理残留进程并重启设备程序 |
| `reconnect_device2.sh` | 重连设备（第二代方案） |
| `recover_stack.sh` | 恢复 ROS2 栈（重启容器） |
| `start_patched.sh` | 启动打补丁后的设备程序 |

### 2.2 保活服务

| 脚本 | 作用 |
|------|------|
| `keeper.sh` | 保活脚本，检测设备进程并自动重启 |
| `install_keeper_service.sh` | 安装保活服务为 systemd 服务 |
| `restart_keeper.sh` | 重启保活服务 |
| `turpi-keeper.service` | systemd 服务定义文件 |

### 2.3 断线重连补丁

| 脚本 | 作用 |
|------|------|
| `add_reconnect.py` | 为设备程序添加断线重连逻辑 |

### 2.4 上电与诊断

| 脚本 | 作用 |
|------|------|
| `post_power_on.sh` | 上电后检查清单 |
| `full_check.sh` | 全面检查（进程、日志、socket、源） |
| `verify_all.sh` | 验证所有判据 |
| `log_growth.sh` | 检查日志是否在增长 |
| `why_drop.sh` | 诊断掉线原因 |

### 2.5 串口与电池

| 脚本 | 作用 |
|------|------|
| `bat.sh` | 读取电池电压 |
| `read_battery_correct.sh` | 正确读取电池（绕过 ROS 话题） |
| `loopback_test.sh` | 串口回环测试 |
| `trace_serial.sh` | 追踪串口通信 |

### 2.6 摄像头修复

| 脚本 | 作用 |
|------|------|
| `fix_camera.sh` | 修复摄像头（重启 usb_cam 节点） |
| `fix_snapshot.sh` | 修复快照（重启 web_video_server） |
| `check_topics.sh` | 检查 ROS 话题发布者 |

### 2.7 安全与清理

| 脚本 | 作用 |
|------|------|
| `emergency_stop.sh` | 紧急停止（发送 halt 命令） |
| `clean_junk.sh` | 清理临时文件 |
| `clean_workspace.ps1` | 清理工作区（PowerShell） |

### 2.8 协议探测

| 脚本 | 作用 |
|------|------|
| `probe_hub.mjs` | 探测 AgnesHub 连接 |
| `probe_seq.mjs` | 探测连接序列 |

---

## 3. 设备端运维脚本（`car_scripts/`）

**部署位置**：树莓派（`~/turbopi_agh/` 或容器内 `/tmp/`）

**作用**：直接在树莓派上运行，用于诊断、修复、标定。

### 3.1 运维

| 脚本 | 作用 |
|------|------|
| `recover.sh` | 恢复脚本（拉起 ROS2 栈） |
| `keeper.sh` | 保活脚本（树莓派版本） |
| `apply_patch.sh` | 应用补丁（断线重连） |

### 3.2 串口排查

| 脚本 | 作用 |
|------|------|
| `serial_check.py` | 串口检查 |
| `serial_motor.py` | 串口电机测试 |
| `full_serial_test.py` | 完整串口测试 |

### 3.3 云台排查

| 脚本 | 作用 |
|------|------|
| `servo_probe.py` | 舵机探测 |
| `servo_readback.py` | 舵机回读 |
| `servo_type_probe.py` | 舵机类型探测 |
| `gimbal_test.py` | 云台测试 |
| `direct_gimbal.py` | 直接控制云台 |
| `hold_tilt.py` | 保持俯仰角度 |
| `sweep_tilt.py` | 俯仰扫描 |

### 3.4 摄像头排查

| 脚本 | 作用 |
|------|------|
| `cam_diag.py` | 摄像头诊断 |
| `cam_ok.py` | 摄像头检查 |
| `camera_only_device.py` | 仅摄像头设备程序 |
| `camera_device_diag.py` | 摄像头设备诊断 |
| `camera_device_logged.py` | 登录版摄像头设备 |

### 3.5 底盘测试

| 脚本 | 作用 |
|------|------|
| `chassis_test.py` | 底盘测试 |
| `motion_probe.py` | 运动探测 |
| `speed_test.py` | 速度测试 |
| `speed_watch.py` | 速度监控 |

### 3.6 其他探针

| 脚本 | 作用 |
|------|------|
| `duration_sweep.py` | 时长扫描 |
| `endpoint_probe.py` | 端点探测 |
| `inspect_payload.py` | 载荷检查 |

---

## 4. 设备端配置文件（`car_config/`）

**部署位置**：树莓派

| 文件 | 部署位置 | 作用 |
|------|----------|------|
| `turpi-keeper.service` | `/etc/systemd/system/` | 保活服务 systemd 配置 |
| `servo_controller.yaml` | ROS2 工作区 | 舵机控制器参数（厂商预装） |

---

## 5. 设备实拍照片（`car_evidence/`）

**用途**：仅用于文档和调试证据，不部署到设备。

包含 19 张 JPEG 照片，证明摄像头出图能力：
- `baseline_*.jpg`：基准照片
- `tilt1200_*.jpg`、`tilt1850_*.jpg`：云台不同角度照片
- `sweep_*.jpg`：角度扫描照片

---

## 6. 技术文档（`docs/`）

**用途**：记录调试过程和解决方案，供参考学习。

| 文档 | 内容 |
|------|------|
| `小车接入实测记录.md` | 记录设备接入过程中的问题和解决方案 |
| `恢复后待办与验证清单.md` | 恢复后的待办事项和验证清单 |
| `成功关键因素全记录.md` | 总结成功的关键因素 |
| `保活服务与乱动事故记录.md` | 记录保活服务设计和乱动事故 |
| `设备掉线根因与重连方案.md` | 分析掉线根因，提出重连方案 |

---

## 第三方依赖说明

以下组件**不包含在本仓库**，但运行时需要：

| 组件 | 来源 | 用途 |
|------|------|------|
| Agnes Harness | [GitHub](https://github.com/AgnesAI-Labs/agnes-harness) | 智能体执行框架 |
| `agnes_mhs` | Agnes Harness 内置 | 设备端 MHS 协议库 |
| ROS2 Humble | 厂商预装 | 机器人操作系统 |
| TurboPi SDK | 厂商预装 | 底盘、舵机、摄像头驱动 |
| `picamera2` | 系统预装 | 摄像头控制 |
| `PyAV` | pip 安装 | 视频处理 |

---

## 开源许可

本仓库源码采用 Apache License 2.0 许可。

第三方组件遵循各自许可协议。
