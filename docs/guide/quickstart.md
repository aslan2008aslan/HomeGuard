# HomeGuard Quickstart Guide

> 本文档另有[中文版本](quickstart.zh-CN.md)。

This guide walks you through deploying HomeGuard on your local machine.

## Prerequisites

| Component | Requirement | Notes |
|---|---|---|
| **Host OS** | Windows 10/11 or Linux | Tested on Windows 11 |
| **Node.js** | ≥ 24.10 | [Download](https://nodejs.org/) |
| **pnpm** | 10.34.5 | `npm i -g pnpm@10.34.5` |
| **Device** | Hiwonder TurboPi (Raspberry Pi 5) | With ROS2 Humble pre-installed |
| **Network** | Same LAN for host and device | Trusted network only |

## Step 1: Build Agnes Harness (Host)

```bash
git clone https://github.com/AgnesAI-Labs/agnes-harness.git
cd agnes-harness
pnpm install --frozen-lockfile
pnpm --filter @agnes/cli build:local
node packages/cli/dist/local/agnes.mjs --help
```

> **Windows Note:** Windows builds are not officially validated by AGH team. If build fails, consider deploying AGH on the Raspberry Pi itself (Linux).

## Step 2: Install MHS Plugin

```bash
# Install MHS plugin
pnpm --filter @agnes/mhs plugin:install

# Start AGH with Hub
export AGNES_HUB_LISTEN='0.0.0.0:4180'
export AGNES_HUB_ORIGIN='http://127.0.0.1:4180'
node packages/cli/dist/local/agnes.mjs serve --port 4177 --profile local-dev
```

Open browser to `http://127.0.0.1:4177` → Settings → Plugin Management → Enable `@agnes/mhs`.

## Step 3: Deploy Device Program (TurboPi)

```bash
# SSH into TurboPi
ssh pi@192.168.3.187

# Start ROS2 stack (if not running)
bash ~/turbopi_agh/recover.sh

# Check battery voltage
bash ~/tools/bat.sh
# Must be ≥ 7200 mV before proceeding

# Start device program
bash ~/tools/clean_restart.sh
```

Verify device is online:

```python
# In AGH session
read_device(device="turpi-01", sources=["pose"])
# Expected: available, timestamp in seconds
```

## Step 4: Run Task

In AGH web interface, input natural language command:

```
Find the plant, approach it, check the green humidity meter, determine if it needs watering, without relying on localization. Reply in Chinese.
```

Observe autonomous execution:

1. Robot confirms device online
2. Navigates toward target
3. Captures camera image
4. Reasons about plant state
5. Outputs structured conclusion

## Troubleshooting

### Device not connecting

- Check firewall: AgnesHub must listen on `0.0.0.0:4180`
- Verify same LAN: host and device must be on same subnet
- Check device logs: `docker exec turbopi tail -f /tmp/turpi.log`

### Low battery

- Voltage must be ≥ 7200 mV before running demos
- Low-voltage protection is disabled in hardware
- Manual voltage check required before each demo

### Gimbal not moving

- `aim_camera` fails due to insufficient torque (hardware limitation)
- Use `change_view` as fallback (rotates entire chassis)

## Next Steps

- [Architecture Guide](../docs/develop/architecture.md) — Understand system design
- [MHS Integration](../docs/develop/mhs-integration.md) — Integrate new devices
- [Deployment Guide](../docs/guide/deployment.md) — Production deployment
