<template>
  <section class="panel">
    <header class="panel__header">
      <h2 class="panel__title">WebSocket 自动重连 + 状态提示</h2>
      <div class="panel__meta">
        <span class="badge" :data-state="state">{{ state }}</span>
        <span class="kv">online: {{ isOnline }}</span>
        <span class="kv">attempt: {{ attempt }}</span>
      </div>
    </header>

    <div class="grid">
      <div class="card">
        <h3 class="card__title">连接信息</h3>
        <div class="kv">canSend: {{ canSend }}</div>
        <div class="kv">lastMessageAt: {{ lastMessageAtText }}</div>
        <div class="kv">lastErrorAt: {{ lastErrorAtText }}</div>
        <div class="kv" v-if="lastClose">
          lastClose: code={{ lastClose.code }} wasClean={{ lastClose.wasClean }} reason={{ lastClose.reason || '-' }}
        </div>
      </div>

      <div class="card">
        <h3 class="card__title">操作</h3>
        <div class="row">
          <button type="button" class="btn" @click="connect">连接</button>
          <button type="button" class="btn" @click="disconnect">断开</button>
          <button type="button" class="btn" @click="sendPing">ping</button>
        </div>
        <div class="row">
          <input v-model="msg" class="input" type="text" placeholder="输入 chat 文本" />
          <button type="button" class="btn btn--primary" @click="sendChat">发送</button>
        </div>
        <div class="hint">
          建议测试：停止服务端 / DevTools 切 Offline / 再恢复，看状态与日志变化。
        </div>
      </div>
    </div>

    <div class="card">
      <h3 class="card__title">日志（最近 {{ logLimit }} 条）</h3>
      <pre class="logs">{{ logs.join('\n') }}</pre>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useReconnectingWebSocket } from '../composables/useReconnectingWebSocket'

// 该组件只负责“状态展示 + 交互触发”，核心连接逻辑全部在 useReconnectingWebSocket 中
const logLimit = 200
const msg = ref('')

const {
  state,
  attempt,
  lastClose,
  lastErrorAt,
  lastMessageAt,
  isOnline,
  canSend,
  logs,
  connect,
  disconnect,
  sendEnvelope
} = useReconnectingWebSocket({
  // 课堂默认对齐 FastAPI 服务端的 ws 端点
  url: 'ws://localhost:8000/ws',
  // 页面加载即连接：更容易观察重连、离线、心跳等过程
  autoConnect: true,
  logLimit,
  // 退避策略：指数退避 + 抖动 + 上限，避免重连风暴
  policy: { baseDelayMs: 500, maxDelayMs: 15_000, backoffFactor: 1.8, jitterRatio: 0.2, maxRetries: 'infinite' },
  // 心跳：用于“假在线”检测（timeout 后主动 close 触发重连）
  heartbeat: { enabled: true, intervalMs: 10_000, timeoutMs: 25_000 }
})

function toTimeText(ms: number | null) {
  return ms ? new Date(ms).toLocaleTimeString() : '-'
}

const lastMessageAtText = computed(() => toTimeText(lastMessageAt.value))
const lastErrorAtText = computed(() => toTimeText(lastErrorAt.value))

function sendChat() {
  const text = msg.value.trim()
  if (!text) return
  // 发送一条 type=chat 的 Envelope；服务端会 echo，便于验证“断线恢复后仍能收发”
  if (sendEnvelope('chat', { text })) msg.value = ''
}

function sendPing() {
  // 手动触发一次 ping：用于观察服务端 pong 与 lastMessageAt 更新
  sendEnvelope('ping', { ts: Date.now() })
}
</script>

<style scoped>
.panel {
  max-width: 980px;
  margin: 0 auto;
  padding: 24px;
}

.panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.panel__title {
  margin: 0;
  font-size: 18px;
  line-height: 1.3;
}

.panel__meta {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
  justify-content: flex-end;
}

.kv {
  font-size: 12px;
  opacity: 0.85;
}

.badge {
  font-size: 12px;
  padding: 3px 10px;
  border-radius: 999px;
  background: #2b2b2b;
  border: 1px solid rgba(255, 255, 255, 0.12);
}

.badge[data-state='OPEN'] {
  background: rgba(16, 185, 129, 0.16);
  border-color: rgba(16, 185, 129, 0.35);
}

.badge[data-state='RECONNECTING'] {
  background: rgba(245, 158, 11, 0.16);
  border-color: rgba(245, 158, 11, 0.35);
}

.badge[data-state='OFFLINE'] {
  background: rgba(239, 68, 68, 0.16);
  border-color: rgba(239, 68, 68, 0.35);
}

.grid {
  margin-top: 16px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 12px;
}

.card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.08);
  border-radius: 12px;
  padding: 14px;
}

.card__title {
  margin: 0 0 10px;
  font-size: 14px;
  opacity: 0.95;
}

.row {
  display: flex;
  gap: 10px;
  align-items: center;
  margin-bottom: 10px;
}

.input {
  flex: 1;
  height: 34px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.25);
  padding: 0 10px;
  color: inherit;
}

.btn {
  height: 34px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(0, 0, 0, 0.25);
  padding: 0 12px;
  color: inherit;
  cursor: pointer;
}

.btn--primary {
  background: rgba(59, 130, 246, 0.2);
  border-color: rgba(59, 130, 246, 0.35);
}

.hint {
  font-size: 12px;
  opacity: 0.85;
  line-height: 1.4;
}

.logs {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
  font-size: 12px;
  line-height: 1.45;
  max-height: 320px;
  overflow: auto;
}

@media (max-width: 860px) {
  .grid {
    grid-template-columns: 1fr;
  }
}
</style>
