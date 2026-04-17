import { computed, onBeforeUnmount, ref } from 'vue'
import { buildMessage } from '../utils/ws'
import type { Message, MsgType } from '../utils/ws'

export type WsConnState =
  // 仅表示“业务连接状态”（用于 UI 驱动），不要与原生 readyState 混用
  // 原生 readyState 只能表达 CONNECTING/OPEN/CLOSING/CLOSED，但无法表达 OFFLINE/RECONNECTING/ERROR 等工程状态
  | 'IDLE'
  | 'CONNECTING'
  | 'OPEN'
  | 'RECONNECTING'
  | 'OFFLINE'
  | 'CLOSED'
  | 'ERROR'

export type ReconnectPolicy = {
  // 第一次重连延迟基准（毫秒）
  baseDelayMs: number
  // 最大重连间隔上限（毫秒）
  maxDelayMs: number
  // 指数退避系数（>1 逐步变慢）
  backoffFactor: number
  // 抖动比例（0~1）：让大量客户端错峰重连，避免“同一时刻一起冲”
  jitterRatio: number
  // 最大重试次数；infinite 表示无限重试（课堂更直观）
  maxRetries: number | 'infinite'
}

export type HeartbeatOptions = {
  // 是否启用心跳
  enabled: boolean
  // 心跳发送间隔（毫秒）
  intervalMs: number
  // 超时阈值（毫秒）：超过该时间未收到任何消息，则判定“假在线”并主动 close 触发重连
  timeoutMs: number
}

export type UseReconnectingWebSocketOptions = {
  url: string | (() => string)
  protocols?: string | string[]
  autoConnect?: boolean
  policy?: Partial<ReconnectPolicy>
  heartbeat?: Partial<HeartbeatOptions>
  // 日志上限：防止 logs 无限增长造成内存压力
  logLimit?: number
}

export type CloseSnapshot = { code: number; reason: string; wasClean: boolean; at: number }

function clamp(n: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, n))
}

function computeDelayMs(attempt: number, p: ReconnectPolicy): number {
  // 指数退避 + 抖动：
  // delay = min(maxDelay, baseDelay * backoffFactor^(attempt-1)) * random(1-jitter, 1+jitter)
  const n = Math.max(1, attempt)
  const pure = Math.min(p.maxDelayMs, p.baseDelayMs * Math.pow(p.backoffFactor, n - 1))
  const jr = clamp(p.jitterRatio, 0, 1)
  const factor = 1 - jr + Math.random() * (2 * jr)
  return Math.max(0, Math.round(pure * factor))
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text) as unknown
  } catch {
    return text
  }
}

export function useReconnectingWebSocket(options: UseReconnectingWebSocketOptions) {
  const policy: ReconnectPolicy = {
    baseDelayMs: 500,
    maxDelayMs: 15_000,
    backoffFactor: 1.8,
    jitterRatio: 0.2,
    maxRetries: 'infinite',
    ...options.policy
  }
  const heartbeat: HeartbeatOptions = {
    enabled: true,
    intervalMs: 10_000,
    timeoutMs: 25_000,
    ...options.heartbeat
  }

  const logLimit = options.logLimit ?? 200

  // 核心可观察状态：用于 UI 展示与验收
  const state = ref<WsConnState>('IDLE')
  const attempt = ref(0)
  const lastErrorAt = ref<number | null>(null)
  const lastClose = ref<CloseSnapshot | null>(null)
  const lastMessageAt = ref<number | null>(null)
  const logs = ref<string[]>([])

  // manualClose：区分“用户主动断开”和“异常断开”
  // 只有异常断开才会触发自动重连
  const manualClose = ref(false)
  const wsRef = ref<WebSocket | null>(null)

  let reconnectTimer: number | null = null
  let heartbeatTimer: number | null = null

  // navigator.onLine 是“网络层提示”，不等价于“WebSocket 连接一定可用”
  const isOnline = ref<boolean>(navigator.onLine)
  const canSend = computed(() => wsRef.value?.readyState === WebSocket.OPEN)

  function pushLog(line: string) {
    logs.value.push(line)
    if (logs.value.length > logLimit) {
      logs.value.splice(0, logs.value.length - logLimit)
    }
  }

  function clearTimers() {
    if (reconnectTimer !== null) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (heartbeatTimer !== null) {
      window.clearInterval(heartbeatTimer)
      heartbeatTimer = null
    }
  }

  function markMessageArrived() {
    // 任何 message 都视为“连接仍活着”的证据（课堂实现用“最近活跃时间”驱动断线检测）
    lastMessageAt.value = Date.now()
  }

  function closeNow(code?: number, reason?: string) {
    const ws = wsRef.value
    if (!ws) return
    try {
      ws.close(code, reason)
    } catch {
      ws.close()
    }
  }

  function shouldRetry(nextAttempt: number) {
    return policy.maxRetries === 'infinite' ? true : nextAttempt <= policy.maxRetries
  }

  function scheduleReconnect() {
    if (manualClose.value) return
    if (!isOnline.value) {
      state.value = 'OFFLINE'
      pushLog(`[offline] waiting for online`)
      return
    }

    const nextAttempt = attempt.value + 1
    if (!shouldRetry(nextAttempt)) {
      state.value = 'CLOSED'
      pushLog(`[reconnect] give up: maxRetries reached`)
      return
    }

    attempt.value = nextAttempt
    state.value = 'RECONNECTING'

    const delay = computeDelayMs(nextAttempt, policy)
    pushLog(`[reconnect] attempt=${nextAttempt} delayMs=${delay}`)
    reconnectTimer = window.setTimeout(() => {
      connectInternal()
    }, delay)
  }

  function startHeartbeat() {
    if (!heartbeat.enabled) return
    if (heartbeatTimer !== null) window.clearInterval(heartbeatTimer)

    heartbeatTimer = window.setInterval(() => {
      const ws = wsRef.value
      if (!ws || ws.readyState !== WebSocket.OPEN) return

      const now = Date.now()
      const last = lastMessageAt.value
      if (last && now - last > heartbeat.timeoutMs) {
        // 超时：把“假在线”转换为“明确 close”，后续由 onclose 统一进入重连流程
        pushLog(`[heartbeat] timeoutMs=${heartbeat.timeoutMs}`)
        closeNow(4000, 'heartbeat timeout')
        return
      }

      try {
        // 心跳包本身也用 Envelope，便于服务端按 type 分支处理
        const ping = buildMessage('ping', { ts: now })
        ws.send(JSON.stringify(ping))
        pushLog(`[heartbeat] ping`)
      } catch {
        // send 抛异常时也主动 close，让流程收敛到 onclose 统一处理
        closeNow(4001, 'heartbeat send failed')
      }
    }, heartbeat.intervalMs)
  }

  function connectInternal() {
    clearTimers()
    manualClose.value = false

    const existing = wsRef.value
    if (existing && existing.readyState !== WebSocket.CLOSED) {
      // 连接尚未完全关闭时不要重复 new WebSocket，避免重复连接导致状态混乱
      state.value =
        existing.readyState === WebSocket.OPEN
          ? 'OPEN'
          : existing.readyState === WebSocket.CONNECTING
          ? 'CONNECTING'
          : 'RECONNECTING'
      return
    }

    state.value = attempt.value > 0 ? 'RECONNECTING' : 'CONNECTING'

    const url = typeof options.url === 'function' ? options.url() : options.url
    const ws = new WebSocket(url, options.protocols)
    wsRef.value = ws
    pushLog(`[connect] url=${url}`)

    ws.onopen = () => {
      state.value = 'OPEN'
      attempt.value = 0
      lastClose.value = null
      markMessageArrived()
      pushLog(`[open]`)
      startHeartbeat()
    }

    ws.onmessage = (e) => {
      markMessageArrived()
      const raw = typeof e.data === 'string' ? e.data : String(e.data)
      const parsed = typeof e.data === 'string' ? safeJsonParse(e.data) : raw
      pushLog(`[message] ${typeof parsed === 'string' ? parsed : JSON.stringify(parsed)}`)
    }

    ws.onerror = () => {
      // 浏览器的 onerror 通常缺少细节：只记录“发生过错误”和时间戳即可
      // 真正的重连触发点在 onclose（更可靠）
      lastErrorAt.value = Date.now()
      state.value = 'ERROR'
      pushLog(`[error]`)
    }

    ws.onclose = (e) => {
      clearTimers()
      wsRef.value = null
      lastClose.value = { code: e.code, reason: e.reason, wasClean: e.wasClean, at: Date.now() }
      pushLog(`[close] code=${e.code} reason=${e.reason} wasClean=${e.wasClean}`)

      if (manualClose.value) {
        state.value = 'CLOSED'
        return
      }

      scheduleReconnect()
    }
  }

  function connect() {
    if (state.value === 'OPEN' || state.value === 'CONNECTING' || state.value === 'RECONNECTING') return
    connectInternal()
  }

  function disconnect() {
    // 手动断开：必须设置 manualClose，阻止 close 触发自动重连
    manualClose.value = true
    clearTimers()
    closeNow(1000, 'manual close')
    wsRef.value = null
    state.value = 'CLOSED'
  }

  function sendText(text: string): boolean {
    const ws = wsRef.value
    if (!ws || ws.readyState !== WebSocket.OPEN) return false
    ws.send(text)
    pushLog(`[send] ${text}`)
    return true
  }

  function sendEnvelope<TPayload>(type: MsgType, payload: TPayload): boolean {
    const m: Message<TPayload> = buildMessage(type, payload)
    return sendText(JSON.stringify(m))
  }

  function onOnline() {
    isOnline.value = true
    pushLog(`[network] online`)
    // 网络恢复时：如果不是手动断开且处于不可用状态，就立即尝试连接一次
    if (!manualClose.value && (state.value === 'OFFLINE' || state.value === 'CLOSED' || state.value === 'ERROR')) {
      attempt.value = 0
      connectInternal()
    }
  }

  function onOffline() {
    isOnline.value = false
    pushLog(`[network] offline`)
    clearTimers()
    if (!manualClose.value) {
      // 离线时不做“狂重连”，直接进入 OFFLINE，等待 online 事件再恢复
      state.value = 'OFFLINE'
      closeNow(1001, 'offline')
    }
  }

  window.addEventListener('online', onOnline)
  window.addEventListener('offline', onOffline)

  onBeforeUnmount(() => {
    window.removeEventListener('online', onOnline)
    window.removeEventListener('offline', onOffline)
    disconnect()
  })

  if (options.autoConnect ?? true) connect()

  return {
    state,
    attempt,
    lastErrorAt,
    lastClose,
    lastMessageAt,
    isOnline,
    canSend,
    logs,
    connect,
    disconnect,
    sendText,
    sendEnvelope
  }
}
