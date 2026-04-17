export type MsgType = 'chat' | 'ping' | 'pong' | 'system' | 'error'

export type Message<T = unknown> = {
  // 消息类型：决定服务端/客户端如何分支处理
  type: MsgType
  // 消息唯一 id：用于日志追踪、去重、定位某一次交互
  id: string
  // 毫秒时间戳：用于排序、排错与“最近活跃时间”展示
  ts: number
  // 业务载荷：不同 type 对应不同结构
  payload: T
  // 元信息：可选，用于标记来源/链路追踪（课堂只做最小字段）
  meta?: { from?: 'client' | 'server'; traceId?: string }
}

export function buildMessage<T>(type: MsgType, payload: T): Message<T> {
  // randomUUID：现代浏览器可用；不支持时回退为随机字符串（课堂足够）
  const uuid = globalThis.crypto?.randomUUID?.()
  return {
    type,
    id: uuid ?? Math.random().toString(36).slice(2),
    ts: Date.now(),
    payload,
    meta: { from: 'client' }
  }
}

export type ReadyStateText = 'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED'

export function mapReadyState(ws?: WebSocket): ReadyStateText {
  // readyState：0 CONNECTING, 1 OPEN, 2 CLOSING, 3 CLOSED
  // 这里把数字映射成可读文本，便于 UI 展示与状态判断统一
  const s = ws?.readyState
  return s === WebSocket.CONNECTING
    ? 'CONNECTING'
    : s === WebSocket.OPEN
    ? 'OPEN'
    : s === WebSocket.CLOSING
    ? 'CLOSING'
    : 'CLOSED'
}
