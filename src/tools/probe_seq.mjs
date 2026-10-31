// 连续采样 hub 缓存里 turpi-01 各源的 seq，观察它是否跳号、怎么跳。
// 目的：解开 "front: 87% lost" 之谜。
//
// observe.ts 的定义：
//   if (msg.seq > lastSeq + 1) lost += msg.seq - lastSeq - 1
// 因此 lost 只可能来自 seq 跳号。
//
// 用法：node tools/probe_seq.mjs [采样次数] [间隔毫秒]

import { createRequire } from 'node:module'
const require = createRequire(import.meta.url)
const { WebSocket } = require('F:/AgnesHarness/node_modules/.pnpm/ws@8.21.3/node_modules/ws/index.js')

const N = Number(process.argv[2] ?? 15)
const GAP = Number(process.argv[3] ?? 1500)
const DEVICE = 'turpi-01'
const SOURCES = ['front', 'pose']

const sock = new WebSocket('ws://127.0.0.1:4180/ws/hub')
let id = 0
const pending = new Map()

function call(method, params) {
  const myId = String(++id)
  return new Promise((resolve, reject) => {
    pending.set(myId, { resolve, reject })
    sock.send(JSON.stringify({ jsonrpc: '2.0', id: myId, method, params }))
    setTimeout(() => {
      if (pending.has(myId)) {
        pending.delete(myId)
        reject(new Error(`\u8d85\u65f6: ${method}`))
      }
    }, 8000)
  })
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms))

sock.on('open', async () => {
  try {
    await call('hub/hello', { role: 'agent', client: { name: 'seq-probe' } })
    console.log(`\u91c7\u6837 ${N} \u6b21, \u95f4\u9694 ${GAP}ms\n`)
    console.log('\u65f6\u95f4      \u6e90      seq   age      \u8df3\u53f7  health')
    console.log('-'.repeat(58))

    const last = {}
    for (let i = 0; i < N; i++) {
      for (const src of SOURCES) {
        const r = await call('hub/read', { device: DEVICE, sources: [src] })
        const item = (r.items ?? [])[0]
        const health = (r.health?.reasons ?? []).join('; ') || r.health?.level || '-'
        if (!item) {
          console.log(`${String(i).padStart(4)}    ${src.padEnd(6)}  (no item)`)
          continue
        }
        if (item.error) {
          console.log(`${String(i).padStart(4)}    ${src.padEnd(6)}  ERROR ${item.error}`)
          continue
        }
        const seq = item.seq
        const prev = last[src]
        let jump = ''
        if (prev !== undefined) {
          const d = seq - prev
          if (d !== 1) jump = `  <== \u8df3\u53f7 delta=${d} (\u4e22\u4e86 ${d - 1})`
        }
        last[src] = seq
        console.log(
          `${String(i).padStart(4)}    ${src.padEnd(6)}  ${String(seq).padStart(4)}  ${String(
            item.age ?? '?',
          ).padStart(6)}${jump}   ${health}`,
        )
      }
      await sleep(GAP)
    }
    console.log('\n\u91c7\u6837\u7ed3\u675f')
  } catch (e) {
    console.error('\u67e5\u8be2\u5931\u8d25:', e.message)
  } finally {
    sock.close()
    process.exit(0)
  }
})

sock.on('error', (e) => {
  console.error('WebSocket \u9519\u8bef:', e.message)
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
