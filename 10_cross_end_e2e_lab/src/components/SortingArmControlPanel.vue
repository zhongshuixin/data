<template>
  <div class="wrap">
    <h2>Web → ROS2 指令下发（/sorting_arm/cmd）</h2>

    <div class="row">
      <label class="label" for="url">WebSocket URL</label>
      <input id="url" v-model="url" class="input" type="text" />
    </div>

    <div class="row">
      <label class="label" for="deviceId">device_id</label>
      <input id="deviceId" v-model="deviceId" class="input" type="text" />
    </div>

    <div class="row">
      <div class="status">连接状态：{{ connStatus }}</div>
      <button class="btn" type="button" :disabled="connStatus === 'OPEN' || connStatus === 'CONNECTING'" @click="connect">
        连接
      </button>
      <button class="btn" type="button" :disabled="connStatus !== 'OPEN'" @click="disconnect">
        断开
      </button>
    </div>

    <div class="row">
      <div class="status">当前角色：{{ role }}</div>
      <select v-model="role" class="select">
        <option value="viewer">viewer（只读）</option>
        <option value="operator">operator（可控）</option>
        <option value="admin">admin（高权限）</option>
      </select>
    </div>

    <div class="row">
      <button class="btn primary" type="button" :disabled="!canSend('home') || sending" @click="send('home')">
        {{ sending && currentAction === 'home' ? '下发中...' : '回零（home）' }}
      </button>
      <button class="btn primary" type="button" :disabled="!canSend('stop') || sending" @click="send('stop')">
        {{ sending && currentAction === 'stop' ? '下发中...' : '停止（stop）' }}
      </button>
      <button class="btn danger" type="button" :disabled="!canSend('e_stop') || sending" @click="send('e_stop')">
        {{ sending && currentAction === 'e_stop' ? '下发中...' : '急停（e_stop）' }}
      </button>
    </div>

    <div class="row">
      <div class="status">最近一次 cmd_id：{{ lastCmdId || '（暂无）' }}</div>
    </div>

    <div class="row">
      <div class="status">最近一次 trace_id：{{ lastTraceId || '（暂无）' }}</div>
    </div>

    <div class="row">
      <div class="status">最近一次结果：{{ lastResultText || '（暂无）' }}</div>
    </div>

    <div v-if="lastRawStatus" class="row">
      <details>
        <summary>最近一条 /sorting_arm/status 原始 JSON</summary>
        <pre class="pre">{{ lastRawStatus }}</pre>
      </details>
    </div>

    <div v-if="lastError" class="row error">错误：{{ lastError }}</div>
  </div>
</template>

<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { useRosbridgeUrl } from '../composables/useRosbridgeUrl'
import type { ArmAction, ArmStatus, Role } from '../utils/sorting-arm-protocol'
import { SortingArmWebControlClient } from '../utils/sorting-arm-web-control-client'

type ConnStatus = 'IDLE' | 'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED'

const { url } = useRosbridgeUrl('ws://localhost:9090')
const deviceId = ref('arm_01')

const connStatus = ref<ConnStatus>('IDLE')
// role 只用于前端按钮权限演示；真正安全边界必须在 ROS2 执行侧再次校验
const role = ref<Role>('operator')

const lastCmdId = ref('')
const lastTraceId = ref('')
const lastResultText = ref('')
const lastRawStatus = ref('')
const lastError = ref('')

const sending = ref(false)
const currentAction = ref<ArmAction | null>(null)

// WebSocket/rosbridge 交互都收敛在 client 内部：组件只负责 UI + 调用
const client = new SortingArmWebControlClient()

// 最小权限模型（课堂用）：viewer 不可控，operator 可 home/stop，admin 额外可 e_stop
const actionPermission: Record<Role, ArmAction[]> = {
  viewer: [],
  operator: ['home', 'stop'],
  admin: ['home', 'stop', 'e_stop', 'pick_place']
}

function canSend(action: ArmAction): boolean {
  // 只有连接已打开 + 当前角色允许该动作时才可下发
  return connStatus.value === 'OPEN' && actionPermission[role.value].includes(action)
}

function setConnStatusFromReadyState(sock: WebSocket): void {
  // 用 readyState 推导 UI 状态（避免手写状态机）
  connStatus.value =
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
  lastResultText.value = ''
  lastRawStatus.value = ''

  try {
    // 建立连接后，client 会在 open 时订阅 /sorting_arm/status
    client.connect(url.value)
    const ws = client.getSocket()
    if (!ws) return
    setConnStatusFromReadyState(ws)
    ws.addEventListener('open', () => setConnStatusFromReadyState(ws))
    ws.addEventListener('close', () => setConnStatusFromReadyState(ws))
    ws.addEventListener('error', () => {
      lastError.value = 'WebSocket error'
    })
  } catch (e) {
    lastError.value = e instanceof Error ? e.message : 'connect failed'
  }
}

function disconnect(): void {
  try {
    connStatus.value = 'CLOSING'
    client.disconnect()
  } finally {
    connStatus.value = 'CLOSED'
  }
}

function formatStatusText(status: ArmStatus): string {
  // 将 ArmStatus 映射成一行 UI 文案
  const okText = status.ok ? '成功' : '失败'
  const codeText = status.code ? `（${status.code}）` : ''
  const msgText = status.message || ''
  const stateText = status.state ? ` state=${status.state}` : ''
  return `${okText}${codeText} ${msgText}${stateText}`.trim()
}

async function send(action: ArmAction): Promise<void> {
  if (!canSend(action)) return
  lastError.value = ''
  lastResultText.value = ''
  sending.value = true
  currentAction.value = action

  // 不同动作的参数示例（真实项目可按 action 拆分表单/参数校验）
  const params =
    action === 'home'
      ? {}
      : action === 'stop'
      ? { reason: 'user_click' }
      : action === 'e_stop'
      ? { reason: 'user_click' }
      : {}

  try {
    // sendCommand 内部会：
    // 1) 生成 cmd_id
    // 2) publish 到 /sorting_arm/cmd
    // 3) 等待 /sorting_arm/status 回传，并用 last_cmd_id 匹配 cmd_id
    const { cmdId, traceId, status } = await client.sendCommand({
      user: 'stu01',
      role: role.value,
      deviceId: deviceId.value,
      action,
      params,
      timeoutMs: 3000
    })
    lastCmdId.value = cmdId
    lastTraceId.value = traceId
    lastResultText.value = formatStatusText(status)
    // 便于课堂验收与排错：展示原始 JSON（对应 status 回执体）
    lastRawStatus.value = JSON.stringify(status, null, 2)
  } catch (e) {
    lastError.value = e instanceof Error ? e.message : 'send failed'
  } finally {
    sending.value = false
    currentAction.value = null
  }
}

onUnmounted(() => {
  // 避免热更新/切页导致后台残留连接
  disconnect()
})
</script>

<style scoped>
.wrap {
  max-width: 960px;
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
  width: 140px;
}

.input {
  flex: 1;
  padding: 8px 10px;
  border: 1px solid #d1d5db;
  border-radius: 8px;
}

.select {
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

.primary {
  border-color: #2563eb;
  color: #1d4ed8;
}

.danger {
  border-color: #dc2626;
  color: #b91c1c;
}

.pre {
  margin-top: 8px;
  padding: 12px;
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  overflow: auto;
  width: 100%;
}

.error {
  color: #b91c1c;
}
</style>
