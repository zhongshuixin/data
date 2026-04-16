export type RosbridgePublish<TMsg = unknown> = {
  op: 'publish'
  topic: string
  msg: TMsg
}

// rosbridge 的订阅请求：由 Web 端发给 rosbridge_server
// - type：消息类型字符串（ROS2 常用写法：pkg/msg/Type）
// - id：订阅唯一标识（取消订阅时需要一致）
// - throttle_rate/queue_length：rosbridge 的“订阅侧限流/丢弃策略”（单位/语义取决于实现）
export type RosbridgeSubscribe = {
  op: 'subscribe'
  topic: string
  type: string
  id: string
  throttle_rate?: number
  queue_length?: number
}

export type RosbridgeUnsubscribe = {
  op: 'unsubscribe'
  topic: string
  id: string
}

export type RosbridgeSubscribeOptions = {
  id?: string
  throttle_rate?: number
  queue_length?: number
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

// rosbridge 协议里 subscribe/unsubscribe 都依赖 id，这里用 topic 派生一个稳定 id
function makeSubId(topic: string): string {
  const normalized = topic.replace(/^\//, '').replace(/\//g, '-')
  return `sub-${normalized}`
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// 一个极简 rosbridge 客户端：
// - connect(): 建立 WebSocket，并把 publish 消息按 topic 路由到回调
// - subscribe(): 发送 rosbridge subscribe 请求，并登记 handler
// - unsubscribe(): 发送 rosbridge unsubscribe 请求，并移除 handler
export class RosbridgeClient {
  private ws: WebSocket | null = null
  private readonly handlers = new Map<string, (msg: unknown) => void>()
  private readonly url: string

  constructor(url: string) {
    this.url = url
  }

  connect(): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) return
    if (this.ws && this.ws.readyState === WebSocket.CONNECTING) return

    this.ws = new WebSocket(this.url)

    this.ws.addEventListener('open', () => {
      console.log('[rosbridge] connected:', this.url)
    })

    // rosbridge 会推送形如：
    // { op: "publish", topic: "/xxx", msg: { ... } }
    this.ws.addEventListener('message', (ev) => {
      const raw = typeof ev.data === 'string' ? ev.data : ''
      if (!raw) return

      const data = safeJsonParse(raw)
      if (!data || typeof data !== 'object') return

      if (!('op' in data) || !('topic' in data) || !('msg' in data)) return
      const d = data as { op: unknown; topic: unknown; msg: unknown }

      if (d.op !== 'publish' || typeof d.topic !== 'string') return

      const handler = this.handlers.get(d.topic)
      if (!handler) return

      handler(d.msg)
    })

    this.ws.addEventListener('error', () => {
      console.error('[rosbridge] ws error')
    })

    this.ws.addEventListener('close', (ev) => {
      console.warn('[rosbridge] closed:', ev.code, ev.reason)
    })
  }

  async waitForOpen(timeoutMs = 5000): Promise<void> {
    const start = Date.now()
    while (true) {
      const state = this.ws?.readyState
      if (state === WebSocket.OPEN) return
      if (state === WebSocket.CLOSING || state === WebSocket.CLOSED) {
        throw new Error('WebSocket closed before OPEN')
      }
      if (Date.now() - start > timeoutMs) {
        throw new Error(`Timeout waiting for WebSocket OPEN (${timeoutMs}ms)`)
      }
      await sleep(50)
    }
  }

  disconnect(): void {
    if (!this.ws) return
    try {
      this.ws.close()
    } finally {
      this.ws = null
      this.handlers.clear()
    }
  }

  subscribe(topic: string, type: string, handler: (msg: unknown) => void, options?: RosbridgeSubscribeOptions): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      throw new Error('WebSocket is not OPEN. Call connect() and wait for open.')
    }

    const id = options?.id ?? makeSubId(topic)
    // 订阅请求本质是 JSON 文本，字段名必须严格匹配 rosbridge 协议
    // 常见联调坑：忘记 JSON.stringify / type 写错（std_msgs/String vs std_msgs/msg/String）
    const req: RosbridgeSubscribe = {
      op: 'subscribe',
      topic,
      type,
      id,
      throttle_rate: options?.throttle_rate,
      queue_length: options?.queue_length
    }
    this.ws.send(JSON.stringify(req))
    this.handlers.set(topic, handler)
    console.log('[rosbridge] subscribed:', req)
  }

  unsubscribe(topic: string): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return

    const id = makeSubId(topic)
    const req: RosbridgeUnsubscribe = { op: 'unsubscribe', topic, id }
    this.ws.send(JSON.stringify(req))
    this.handlers.delete(topic)
    console.log('[rosbridge] unsubscribed:', req)
  }
}
