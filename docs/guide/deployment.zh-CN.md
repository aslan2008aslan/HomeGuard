> 本文档另有[英文版本](deployment.md)。

# HomeGuard 部署指南

本指南介绍如何在类生产环境中部署 HomeGuard。

## 先决条件

| 组件 | 要求 | 备注 |
|---|---|---|
| **主机操作系统** | Windows 10/11 或 Linux | 已在 Windows 11 上测试 |
| **Node.js** | ≥ 24.10 | [下载](https://nodejs.org/) |
| **pnpm** | 10.34.5 | `npm i -g pnpm@10.34.5` |
| **设备** | Hiwonder TurboPi（Raspberry Pi 5） | 预装 ROS2 Humble |
| **网络** | 主机与设备处于同一局域网 | 仅限受信网络 |

## 部署选项

### 选项 A：主机在 Windows，设备在 TurboPi

这是开发和演示的**推荐**配置。

```
┌──────────────────────┐         ┌──────────────────────────┐
│  Windows PC          │         │  TurboPi (Raspberry Pi 5) │
│  (Agnes Harness)     │◄────────┤  (Device Program)        │
│  :4180               │   WS    │                          │
└──────────────────────┘         └──────────────────────────┘
```

**步骤：**

1. 在 Windows 上构建 Agnes Harness（参见[快速入门](../docs/guide/quickstart.md)）
2. 在 TurboPi 上部署设备程序
3. 配置防火墙以允许端口 4180 的入站连接
4. 启动带 Hub 的 AGH
5. 启动设备程序

### 选项 B：主机和设备均在 TurboPi 上

此配置可避免 Windows 构建问题，但需要 TurboPi 同时承担主机和设备的角色。

```
┌─────────────────────────────────────────┐
│  TurboPi (Raspberry Pi 5)               │
│  ┌─────────────────┐  ┌──────────────┐ │
│  │ Agnes Harness   │  │ Device       │ │
│  │ :4180           │◄─┤ Program      │ │
│  │ (Host)          │  │ (Device)     │ │
│  └─────────────────┘  └──────────────┘ │
│         ↕ localhost                     │
└─────────────────────────────────────────┘
```

**步骤：**

1. 在 TurboPi（Linux）上构建 Agnes Harness
2. 在同一块板子上部署设备程序
3. 使用 `ws://127.0.0.1:4180` 作为 AgnesHub URL
4. 启动带 Hub 的 AGH
5. 启动设备程序

**权衡：**

- ✅ 避免 Windows 构建问题
- ✅ 只需管理一台设备
- ❌ TurboPi 必须同时承担主机和设备（资源占用更高）
- ❌ 可能需要优化 LLM API 调用（网络延迟）

## 网络配置

### 防火墙规则（Windows）

```powershell
# Allow AgnesHub inbound (trusted LAN only)
netsh advfirewall firewall add rule name="AgnesHub 4180" dir=in action=allow `
  protocol=TCP localport=4180 remoteip=LocalSubnet profile=any
```

> **注意：** 如果防火墙由组策略管理，本地规则可能不生效。可通过以下命令检查：
> ```powershell
> netsh advfirewall show allprofiles state
> ```

### 环境变量

| 变量 | 读取方 | 含义 | 推荐值 |
|---|---|---|---|
| `AGNES_HUB_LISTEN` | Daemon | Hub 监听地址 | `0.0.0.0:4180`（设备连接必需） |
| `AGNES_HUB_DATA` | Daemon | Hub 数据目录 | 默认值：`<AGH_HOME>/hub` |
| `AGNES_HUB_ORIGIN` | Web service | Hub HTTP 源（用于 CSP） | `http://127.0.0.1:4180` |

> **重要提示：** 环境变量在 daemon 启动时**仅读取一次**。如需更改，请停止 daemon 并重新启动。

## 安全注意事项

### 仅限受信局域网

AgnesHub **没有身份验证或加密**（这是设计如此）。它只能监听受信的本地网络。

**切勿将 AgnesHub 暴露到公共互联网。**

### 设备安全

- **紧急停止：** `halt` 工具必须始终可用
- **低压保护：** 每次演示前手动检查电压（≥ 7200 mV）
- **硬件限制：** 记录已知问题（例如云台扭矩）

### 凭据管理

- **LLM API 密钥：** 不要包含在源代码或文档中
- **SSH 密钥：** 使用 ed25519（而非 RSA）；安全存储
- **默认密码：** 修改默认密码（例如 `raspberrypi`）

## 监控与日志

### 设备日志

```bash
# View device logs in real-time
docker exec turbopi tail -f /tmp/turpi.log

# Check log size (should be growing)
docker exec turbopi wc -c < /tmp/turpi.log
```

### AGH 日志

AGH 通过 Web 界面提供执行追踪：

1. 打开 `http://127.0.0.1:4177`
2. 进入会话视图
3. 点击 "Trace" 选项卡
4. 查看工具调用、模型输出和审批记录

### 诊断导出

AGH 可以导出诊断包：

```bash
# In AGH session
/export-diagnostics
```

这将创建一个 ZIP 文件，包含：

- `system.json` — 环境快照（Node 版本、平台、配置文件）
- `sessions/` — 会话历史和工具调用
- `config/` — 配置文件（已脱敏的密钥）

## 故障排除

### 设备无法连接

**症状：** 设备在 AGH 中显示为 `offline`

**检查项：**

1. 确认处于同一局域网：从设备执行 `ping <host-ip>`
2. 检查防火墙：端口 4180 必须开放
3. 检查 AgnesHub URL：设备必须拨号到正确的地址
4. 检查设备日志：查找连接错误

### 电池电量低

**症状：** 机器人意外关机

**检查项：**

1. 运行 `tools/bat.sh` 检查电压
2. 电压必须 ≥ 7200 mV
3. 低压保护在硬件中已被禁用
4. 每次演示前需手动检查电压

### 云台无法移动

**症状：** `aim_camera` 始终失败

**根本原因：** 舵机缺乏扭矩

**临时方案：** 使用 `change_view`（旋转整个底盘）

### 里程计漂移

**症状：** `pose` 数据源报告的位置不准确

**根本原因：** 没有编码器；位置通过时间积分估算

**缓解措施：** `pose` 数据源已标记为 `ok: false`；请勿依赖其进行精确定位导航

## 生产环境检查清单

在生产环境部署 HomeGuard 之前：

- [ ] AgnesHub 仅监听受信局域网（非公共互联网）
- [ ] 防火墙规则已配置（端口 4180，仅限本地子网）
- [ ] 设备 `halt` 工具已测试且正常工作
- [ ] 电池电压已检查（≥ 7200 mV）
- [ ] 已知硬件限制已记录
- [ ] LLM API 密钥已安全存储（不在源代码中）
- [ ] SSH 密钥使用 ed25519（而非 RSA）
- [ ] 默认密码已修改
- [ ] 监控和日志已配置
- [ ] 诊断导出已测试

## 资源

- [快速入门指南](../docs/guide/quickstart.md)
- [架构指南](../docs/develop/architecture.md)
- [MHS 集成](../docs/develop/mhs-integration.md)
- [Agnes Harness 文档](https://github.com/AgnesAI-Labs/agnes-harness/tree/main/docs)
