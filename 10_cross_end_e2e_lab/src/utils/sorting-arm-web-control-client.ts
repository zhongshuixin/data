import type { ArmCommand, ArmStatus, Role } from './sorting-arm-protocol'
import { makeEnvelope, makeTraceId, unwrapMaybeEnvelope } from '../protocol/envelope'

type Pending = {
  // 收到匹配 cmd_id 的 status 后 resolve
  resolve: (status: ArmStatus) => void
  // 超时/断开连接时 reject
  reject: (err: Error) => void
  // 超时计时器 id（用于清理）
  timer: number
}

// rosbridge 协议层消息（我们只用 publish/subscribe 两种 op）
type RosbridgePublish = { op: 'publish'; topic: string; msg: { data: string } }
type RosbridgeSubscribe = { op: 'subscribe'; topic: string; type: 'std_msgs/msg/String'; id: string }
type RosbridgeIncoming = { op: 'publish'; topic: string; msg: { data?: unknown } }

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

function isObject(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null && !Array.isArray(x)
}

function tryParseArmStatus(input: unknown): ArmStatus | null {
  if (!isObject(input)) return null

  const last_cmd_id = input.last_cmd_id
  const ok = input.ok
  const code = input.code
  const message = input.message

  if (typeof last_cmd_id !== 'string' || last_cmd_id === '') return null
  if (typeof ok !== 'boolean') return null
  if (typeof code !== 'string' || code === '') return null
  if (typeof message !== 'string') return null

  return input as ArmStatus
}

function tryParseArmStatusText(text: string): ArmStatus | null {
  // 统一口径：status 回执使用 Envelope 包裹业务体
  const root = safeJsonParse(text)
  const r = unwrapMaybeEnvelope(root)
  if (r.kind !== 'envelope') return null
  return tryParseArmStatus(r.envelope.payload)
}

// Web 侧 rosbridge 客户端：负责
// 1) 连接 WebSocket（ws://...:9090 或端口映射后的 ws://...:19090）
// 2) 订阅 /sorting_arm/status，并按 last_cmd_id 将回执匹配到 pending
// 3) 向 /sorting_arm/cmd 发布 ArmCommand（JSON 字符串放在 std_msgs/msg/String.data）
export class SortingArmWebControlClient {
  private ws: WebSocket | null = null
  private readonly cmdTopic: string
  private readonly statusTopic: string
  // key=cmd_id：确保一条指令只会被一个回执 resolve（最小闭环）
  private readonly pending: Map<string, Pending> = new Map()

  constructor(options: { cmdTopic?: string; statusTopic?: string } = {}) {
    this.cmdTopic = options.cmdTopic ?? '/sorting_arm/cmd'
    this.statusTopic = options.statusTopic ?? '/sorting_arm/status'
  }

  connect(url: string): void {
    // 避免重复连接（热更新/重复点击）
    if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) return
    this.ws = new WebSocket(url)

    this.ws.addEventListener('open', () => {
      if (!this.ws) return
      const sub: RosbridgeSubscribe = {
        op: 'subscribe',
        topic: this.statusTopic,
        type: 'std_msgs/msg/String',
        id: 'sub-sorting-arm-status'
      }
      // 先订阅 status，避免“回得太快还没订阅到”
      this.ws.send(JSON.stringify(sub))
    })

    this.ws.addEventListener('message', (ev) => {
      const raw = typeof ev.data === 'string' ? ev.data : ''
      if (!raw) return

      // 第 1 层：rosbridge 协议层 JSON（op/topic/msg）
      // 只有识别到 topic=/sorting_arm/status 的 publish，我们才进入第 2 层解析
      const data = safeJsonParse(raw)

      if (!data || typeof data !== 'object') return
      if (!('op' in data) || !('topic' in data) || !('msg' in data)) return

      const d = data as RosbridgeIncoming
      if (d.op !== 'publish' || d.topic !== this.statusTopic) return

      const msgData = d.msg?.data
      if (typeof msgData !== 'string') return

      // 第 2 层：应用层 JSON（ArmStatus 或 Envelope<ArmStatus>）
      // 这里不使用强类型解码库，原因：课堂联调更需要“容错 + 可定位”，而不是一处失败全链路挂掉
      const s = tryParseArmStatusText(msgData)
      if (!s) return
      // 用 last_cmd_id 找到对应请求
      const p = this.pending.get(s.last_cmd_id)
      if (!p) return

      window.clearTimeout(p.timer)
      this.pending.delete(s.last_cmd_id)
      p.resolve(s)
    })

    this.ws.addEventListener('close', () => {
      // 连接断开：让所有未完成请求失败，避免界面一直 loading
      for (const [cmdId, p] of this.pending.entries()) {
        window.clearTimeout(p.timer)
        p.reject(new Error(`connection closed, cmd_id=${cmdId}`))
      }
      this.pending.clear()
    })
  }

  getSocket(): WebSocket | null {
    // UI 层可拿到 socket 做 readyState 展示，但不要在 UI 层直接 send
    return this.ws
  }

  disconnect(): void {
    if (!this.ws) return
    this.ws.close()
    this.ws = null
  }

  publishCommandText(text: string): void {
    const ws = this.ws
    if (!ws || ws.readyState !== WebSocket.OPEN) throw new Error('WebSocket not open')
    // 注意：rosbridge 的 publish 仍然要包一层协议外壳（op/topic/msg）
    // 本项目选择 std_msgs/msg/String 承载业务 JSON：msg.data = "<json string>"
    const msg: RosbridgePublish = { op: 'publish', topic: this.cmdTopic, msg: { data: text } }
    ws.send(JSON.stringify(msg))
  }

  async sendCommand<TParams extends Record<string, unknown>>(input: {
    user: string
    role: Role
    deviceId: string
    action: ArmCommand['action']
    params: TParams
    safety?: ArmCommand['safety']
    timeoutMs?: number
  }): Promise<{ cmdId: string; traceId: string; status: ArmStatus }> {
    // cmd_id 是前后端/设备联调的“追踪主键”
    // trace_id 是“整条链路追踪主键”（本讲统一协议字段），可贯穿请求→执行→回执
    const cmdId = makeCmdId()
    const traceId = makeTraceId()
    const cmd: ArmCommand<TParams> = {
      cmd_id: cmdId,
      scene: 'sorting',
      device_type: 'arm',
      device_id: input.deviceId,
      action: input.action,
      params: input.params,
      safety: input.safety ?? { require_enable: true, require_guard_closed: true },
      meta: { user: input.user, role: input.role },
      ts_ms: Date.now()
    }

    const env = makeEnvelope({
      trace_id: traceId,
      source: 'web',
      target: 'ros2',
      topic: this.cmdTopic,
      event: 'arm.command.request',
      content_type: 'application/json',
      payload: cmd as unknown as Record<string, unknown>
    })
    this.publishCommandText(JSON.stringify(env))

    const timeoutMs = input.timeoutMs ?? 3000
    // 将“等待回执”抽象成 Promise：收到匹配 last_cmd_id 的 status 时 resolve
    const status = await new Promise<ArmStatus>((resolve, reject) => {
      const timer = window.setTimeout(() => {
        this.pending.delete(cmdId)
        reject(new Error(`status timeout, cmd_id=${cmdId}`))
      }, timeoutMs)

      // pending 的关键意义：
      // - 一次点击对应一个 cmd_id
      // - 回执到来时用 last_cmd_id 反查并 resolve
      // - 超时/断开连接时必须 reject，否则 UI 会卡在 loading
      this.pending.set(cmdId, { resolve, reject, timer })
    })

    return { cmdId, traceId, status }
  }
}

export function makeCmdId(): string {
  // 生成课堂可读的 cmd_id：C-YYYYMMDD-xxxxxx
  const ts = Date.now()
  const rand = Math.random().toString(16).slice(2, 8)
  const day = new Date(ts)
  const y = String(day.getFullYear())
  const m = String(day.getMonth() + 1).padStart(2, '0')
  const d = String(day.getDate()).padStart(2, '0')
  return `C-${y}${m}${d}-${rand}`
}
