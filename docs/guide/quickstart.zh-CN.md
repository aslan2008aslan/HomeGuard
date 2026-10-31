> 本文档另有[英文版本](quickstart.md)。

# HomeGuard 快速入门指南

本指南将引导你在本地机器上部署 HomeGuard。

## 前置条件

| 组件 | 要求 | 备注 |
|---|---|---|
| **主机操作系统** | Windows 10/11 或 Linux | 已在 Windows 11 上测试 |
| **Node.js** | ≥ 24.10 | [下载](https://nodejs.org/) |
| **pnpm** | 10.34.5 | `npm i -g pnpm@10.34.5` |
| **设备** | Hiwonder TurboPi（Raspberry Pi 5） | 需预装 ROS2 Humble |
| **网络** | 主机与设备处于同一局域网 | 仅限可信网络 |

## 第 1 步：构建 Agnes Harness（主机端）

```bash
git clone https://github.com/AgnesAI-Labs/agnes-harness.git
cd agnes-harness
pnpm install --frozen-lockfile
pnpm --filter @agnes/cli build:local
node packages/cli/dist/local/agnes.mjs --help
```

> **Windows 说明：** Windows 构建未经 AGH 团队正式验证。如果构建失败，请考虑在 Raspberry Pi 本身（Linux）上部署 AGH。

## 第 2 步：安装 MHS 插件

```bash
# 安装 MHS 插件
pnpm --filter @agnes/mhs plugin:install

# 启动 AGH 及 Hub
export AGNES_HUB_LISTEN='0.0.0.0:4180'
export AGNES_HUB_ORIGIN='http://127.0.0.1:4180'
node packages/cli/dist/local/agnes.mjs serve --port 4177 --profile local-dev
```

在浏览器中打开 `http://127.0.0.1:4177` → 设置 → 插件管理 → 启用 `@agnes/mhs`。

## 第 3 步：部署设备程序（TurboPi）

```bash
# 通过 SSH 登录 TurboPi
ssh pi@192.168.3.187

# 启动 ROS2 服务栈（如未运行）
bash ~/turbopi_agh/recover.sh

# 检查电池电压
bash ~/tools/bat.sh
# 继续操作前电压必须 ≥ 7200 mV

# 启动设备程序
bash ~/tools/clean_restart.sh
```

验证设备是否在线：

```python
# 在 AGH 会话中
read_device(device="turpi-01", sources=["pose"])
# 预期输出：available，时间戳（秒）
```

## 第 4 步：运行任务

在 AGH Web 界面中，输入自然语言指令：

```
找到植物，靠近它，检查绿色湿度计，判断是否需要浇水，不要依赖定位。用中文回复。
```

观察自主执行过程：

1. 机器人确认设备在线
2. 向目标导航
3. 拍摄摄像头图像
4. 对植物状态进行推理
5. 输出结构化结论

## 故障排查

### 设备无法连接

- 检查防火墙：AgnesHub 必须监听 `0.0.0.0:4180`
- 确认同一局域网：主机与设备必须处于同一子网
- 检查设备日志：`docker exec turbopi tail -f /tmp/turpi.log`

### 电池电量过低

- 运行演示前电压必须 ≥ 7200 mV
- 硬件层面的低压保护已被禁用
- 每次演示前需手动检查电压

### 云台无法移动

- `aim_camera` 因扭矩不足而失败（硬件限制）
- 可使用 `change_view` 作为替代方案（旋转整个底盘）

## 后续步骤

- [架构指南](../docs/develop/architecture.md) — 了解系统设计
- [MHS 集成](../docs/develop/mhs-integration.md) — 集成新设备
- [部署指南](../docs/guide/deployment.md) — 生产环境部署
