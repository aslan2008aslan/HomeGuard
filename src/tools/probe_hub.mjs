// 查询 AgnesHub 的 north 接口，对比 hub 缓存与车侧发出的 seq。
// 目的：区分「车没发帧」还是「hub 收到但丢了」。
//
// 用法（在开发机，F:\turbopi-AGH2 下）：
//   node tools/probe_hub.mjs
//
// 协议要点（来自 packages/mhs/server/north.ts）：
//   - 第一条消息必须是 hub/hello，role 只能是 'ui' 或 'agent'
//   - 设备列表方法是 hub/devices（不是 hub/list）
//   - 读数据是 hub/read，带 sources

import { createRequire } from 'node:module'

// ws 在 pnpm 的隔离目录里，顶层 node_modules 没有它，所以用绝对路径加载。
const require = createRequire(import.meta.url)
const { WebSocket } = require('F:/AgnesHarness/node_modules/.pnpm/ws@8.21.3/node_modules/ws/index.js')

const WS_URL = 'ws://127.0.0.1:4180/ws/hub'
const DEVICE = 'turpi-01'

const sock = new WebSocket(WS_URL)
let seq = 0
const pending = new Map()

function call(method, params) {
  const id = String(++seq)
  return new Promise((resolve, reject) => {
    pending.set(id, { resolve, reject })
    sock.send(JSON.stringify({ jsonrpc: '2.0', id, method, params }))
    setTimeout(() => {
      if (pending.has(id)) {
        pending.delete(id)
        reject(new Error(`超时: ${method}`))
      }
    }, 8000)
  })
}

function strip(item) {
  const c = { ...item }
  if (typeof c.b64 === 'string') c.b64 = `<${c.b64.length} 字符 base64>`
  return c
}

sock.on('open', async () => {
  console.log(`已连接 ${WS_URL}\n`)
  try {
    await call('hub/hello', { role: 'agent', client: { name: 'probe' } })
    console.log('hub/hello OK (role=agent)\n')

    const devs = await call('hub/devices', {})
    const list = Array.isArray(devs) ? devs : (devs.devices ?? [])
    console.log('=== 设备列表 ===')
    for (const d of list) {
      console.log(`  ${d.id}  kind=${d.kind ?? '?'}  present=${d.present ?? '?'}  ${d.text ?? ''}`)
    }

    console.log(`\n=== ${DEVICE} 基础状态 ===`)
    const base = await call('hub/read', { device: DEVICE })
    console.log(JSON.stringify(base, null, 2))

    console.log(`\n=== ${DEVICE} front 源 ===`)
    const front = await call('hub/read', { device: DEVICE, sources: ['front'] })
    const f2 = JSON.parse(JSON.stringify(front))
    if (Array.isArray(f2.items)) f2.items = f2.items.map(strip)
    console.log(JSON.stringify(f2, null, 2))

    console.log(`\n=== ${DEVICE} pose 源 ===`)
    const pose = await call('hub/read', { device: DEVICE, sources: ['pose'] })
    console.log(JSON.stringify(pose, null, 2))

    console.log(`\n=== ${DEVICE} mic 源 ===`)
    const mic = await call('hub/read', { device: DEVICE, sources: ['mic'] })
    const m2 = JSON.parse(JSON.stringify(mic))
    if (Array.isArray(m2.items)) m2.items = m2.items.map(strip)
    console.log(JSON.stringify(m2, null, 2))
  } catch (e) {
    console.error('查询失败:', e.message)
  } finally {
    sock.close()
    process.exit(0)
  }
})

sock.on('error', (e) => {
  console.error('WebSocket 错误:', e.message)
  process.exit(1)
})

sock.on('message', (raw) => {
  let msg
  try {
    msg = JSON.parse(raw.toString())
  } catch {
    return
  }
  if (msg.id !== undefined && msg.id !== null && pending.has(String(msg.id))) {
    const { resolve, reject } = pending.get(String(msg.id))
    pending.delete(String(msg.id))
    if (msg.error) reject(new Error(JSON.stringify(msg.error)))
    else resolve(msg.result)
  }
})
