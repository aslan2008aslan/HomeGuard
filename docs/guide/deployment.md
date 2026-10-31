# HomeGuard Deployment Guide

> 本文档另有[中文版本](deployment.zh-CN.md)。

This guide covers deploying HomeGuard in a production-like environment.

## Prerequisites

| Component | Requirement | Notes |
|---|---|---|
| **Host OS** | Windows 10/11 or Linux | Tested on Windows 11 |
| **Node.js** | ≥ 24.10 | [Download](https://nodejs.org/) |
| **pnpm** | 10.34.5 | `npm i -g pnpm@10.34.5` |
| **Device** | Hiwonder TurboPi (Raspberry Pi 5) | With ROS2 Humble pre-installed |
| **Network** | Same LAN for host and device | Trusted network only |

## Deployment Options

### Option A: Host on Windows, Device on TurboPi

This is the **recommended** setup for development and demos.

```
┌──────────────────────┐         ┌──────────────────────────┐
│  Windows PC          │         │  TurboPi (Raspberry Pi 5) │
│  (Agnes Harness)     │◄────────┤  (Device Program)        │
│  :4180               │   WS    │                          │
└──────────────────────┘         └──────────────────────────┘
```

**Steps:**

1. Build Agnes Harness on Windows (see [Quickstart](../docs/guide/quickstart.md))
2. Deploy device program on TurboPi
3. Configure firewall to allow inbound on port 4180
4. Start AGH with Hub
5. Start device program

### Option B: Host on TurboPi, Device on Same Board

This setup avoids Windows build issues but requires TurboPi to handle both host and device.

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

**Steps:**

1. Build Agnes Harness on TurboPi (Linux)
2. Deploy device program on same board
3. Use `ws://127.0.0.1:4180` as AgnesHub URL
4. Start AGH with Hub
5. Start device program

**Trade-offs:**

- ✅ Avoids Windows build issues
- ✅ Single device to manage
- ❌ TurboPi must handle both host and device (higher resource usage)
- ❌ May need to optimize LLM API calls (network latency)

## Network Configuration

### Firewall Rules (Windows)

```powershell
# Allow AgnesHub inbound (trusted LAN only)
netsh advfirewall firewall add rule name="AgnesHub 4180" dir=in action=allow `
  protocol=TCP localport=4180 remoteip=LocalSubnet profile=any
```

> **Note:** If firewall is managed by Group Policy, local rules may not apply. Check with:
> ```powershell
> netsh advfirewall show allprofiles state
> ```

### Environment Variables

| Variable | Who Reads | Meaning | Recommended Value |
|---|---|---|---|
| `AGNES_HUB_LISTEN` | Daemon | Hub listen address | `0.0.0.0:4180` (required for device connection) |
| `AGNES_HUB_DATA` | Daemon | Hub data directory | Default: `<AGH_HOME>/hub` |
| `AGNES_HUB_ORIGIN` | Web service | Hub HTTP origin for CSP | `http://127.0.0.1:4180` |

> **Important:** Environment variables are read **once** at daemon startup. To change, stop daemon and restart.

## Security Considerations

### Trusted LAN Only

AgnesHub has **no authentication or encryption** (by design). It must only listen on trusted local networks.

**Never expose AgnesHub to the public internet.**

### Device Safety

- **Emergency stop:** `halt` tool must always be available
- **Low-voltage protection:** Check voltage manually before each demo (≥ 7200 mV)
- **Hardware limitations:** Document known issues (e.g., gimbal torque)

### Credential Management

- **LLM API keys:** Do not include in source code or documentation
- **SSH keys:** Use ed25519 (not RSA); store securely
- **Default passwords:** Change from defaults (e.g., `raspberrypi`)

## Monitoring and Logging

### Device Logs

```bash
# View device logs in real-time
docker exec turbopi tail -f /tmp/turpi.log

# Check log size (should be growing)
docker exec turbopi wc -c < /tmp/turpi.log
```

### AGH Logs

AGH provides execution traces via the web interface:

1. Open `http://127.0.0.1:4177`
2. Go to session view
3. Click "Trace" tab
4. Review tool calls, model outputs, and approvals

### Diagnostic Exports

AGH can export diagnostic bundles:

```bash
# In AGH session
/export-diagnostics
```

This creates a ZIP file with:

- `system.json` — environment snapshot (Node version, platform, profile)
- `sessions/` — session history and tool calls
- `config/` — configuration files (redacted secrets)

## Troubleshooting

### Device Not Connecting

**Symptoms:** Device shows as `offline` in AGH

**Checks:**

1. Verify same LAN: `ping <host-ip>` from device
2. Check firewall: port 4180 must be open
3. Check AgnesHub URL: device must dial correct address
4. Check device logs: look for connection errors

### Low Battery

**Symptoms:** Robot shuts down unexpectedly

**Checks:**

1. Run `tools/bat.sh` to check voltage
2. Voltage must be ≥ 7200 mV
3. Low-voltage protection is disabled in hardware
4. Manual voltage check required before each demo

### Gimbal Not Moving

**Symptoms:** `aim_camera` always fails

**Root cause:** Servo lacks torque

**Workaround:** Use `change_view` (rotates entire chassis)

### Odometry Drift

**Symptoms:** `pose` source reports inaccurate position

**Root cause:** No encoders; position estimated via time integration

**Mitigation:** `pose` source marked `ok: false`; don't rely on for precise navigation

## Production Checklist

Before deploying HomeGuard in a production environment:

- [ ] AgnesHub listens on trusted LAN only (not public internet)
- [ ] Firewall rules configured (port 4180, local subnet only)
- [ ] Device `halt` tool tested and working
- [ ] Battery voltage checked (≥ 7200 mV)
- [ ] Known hardware limitations documented
- [ ] LLM API keys stored securely (not in source code)
- [ ] SSH keys use ed25519 (not RSA)
- [ ] Default passwords changed
- [ ] Monitoring and logging configured
- [ ] Diagnostic export tested

## Resources

- [Quickstart Guide](../docs/guide/quickstart.md)
- [Architecture Guide](../docs/develop/architecture.md)
- [MHS Integration](../docs/develop/mhs-integration.md)
- [Agnes Harness Documentation](https://github.com/AgnesAI-Labs/agnes-harness/tree/main/docs)
