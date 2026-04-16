<template>
  <div class="wrap">
    <h2>rosbridge 话题订阅（最小示例）</h2>

    <div class="row">
      <label class="label" for="url">WebSocket URL</label>
      <input id="url" v-model="url" class="input" type="text" />
    </div>

    <div class="row">
      <div class="status">状态：{{ status }}</div>
      <button class="btn" type="button" :disabled="status === 'OPEN' || status === 'CONNECTING'" @click="connect">
        连接
      </button>
      <button class="btn" type="button" :disabled="status !== 'OPEN'" @click="disconnect">
        断开
      </button>
    </div>

    <div class="row">
      <div class="status">订阅：{{ topic }}（{{ type }}）</div>
    </div>

    <div class="row">
      <div class="status">最近一条 /chatter：{{ chatterText ?? '（暂无）' }}</div>
    </div>

    <div v-if="lastRaw" class="row">
      <details>
        <summary>最近一条原始 JSON</summary>
        <pre class="pre">{{ lastRaw }}</pre>
      </details>
    </div>

    <div v-if="lastError" class="row error">
      错误：{{ lastError }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { onUnmounted, ref } from 'vue'

type Status = 'IDLE' | 'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED'

const url = ref('ws://localhost:9090')
const status = ref<Status>('IDLE')

const topic = '/chatter'
const type = 'std_msgs/msg/String'
const id = 'sub-chatter'

const chatterText = ref<string | null>(null)
const lastRaw = ref<string>('')
const lastError = ref<string>('')

let ws: WebSocket | null = null

function setStatusFromReadyState(sock: WebSocket): void {
  status.value =
    sock.readyState === WebSocket.CONNECTING
      ? 'CONNECTING'
      : sock.readyState === WebSocket.OPEN
      ? 'OPEN'
      : sock.readyState === WebSocket.CLOSING
      ? 'CLOSING'
      : 'CLOSED'
}

function connect(): void {
  lastError.value = ''
  chatterText.value = null
  lastRaw.value = ''

  if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {
    setStatusFromReadyState(ws)
    return
  }

  ws = new WebSocket(url.value)
  setStatusFromReadyState(ws)

  ws.addEventListener('open', () => {
    if (!ws) return
    setStatusFromReadyState(ws)

    const subscribeMsg = { op: 'subscribe', topic, type, id }
    ws.send(JSON.stringify(subscribeMsg))
  })

  ws.addEventListener('message', (ev) => {
    const raw = typeof ev.data === 'string' ? ev.data : ''
    if (!raw) return

    lastRaw.value = raw

    let data: unknown
    try {
      data = JSON.parse(raw)
    } catch {
      return
    }

    if (!data || typeof data !== 'object') return
    if (!('op' in data) || !('topic' in data) || !('msg' in data)) return

    const d = data as { op: unknown; topic: unknown; msg: unknown }
    if (d.op !== 'publish' || d.topic !== topic) return

    const msg = d.msg as { data?: unknown }
    chatterText.value = typeof msg.data === 'string' ? msg.data : JSON.stringify(d.msg)
  })

  ws.addEventListener('error', () => {
    lastError.value = 'WebSocket error'
  })

  ws.addEventListener('close', (ev) => {
    status.value = 'CLOSED'
    lastError.value = lastError.value || `closed: ${ev.code} ${ev.reason || ''}`.trim()
  })
}

function disconnect(): void {
  if (!ws) return
  try {
    status.value = 'CLOSING'
    ws.close()
  } finally {
    ws = null
  }
}

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped>
.wrap {
  max-width: 860px;
  margin: 24px auto;
  padding: 16px;
  border: 1px solid #e5e7eb;
  border-radius: 12px;
}

.row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-top: 12px;
}

.label {
  width: 120px;
}

.input {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
}

.status {
  flex: 1;
}

.btn {
  padding: 8px 12px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
  background: #fff;
}

.pre {
  margin-top: 8px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: auto;
}

.error {
  color: #b91c1c;
}
</style>
