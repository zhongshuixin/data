<template>
  <div class="wrap">
    <h2>项目工坊：多话题订阅与格式转换</h2>

    <div class="row">
      <label class="label" for="url">WebSocket URL</label>
      <input id="url" v-model="url" class="input" type="text" />
    </div>

    <div class="row">
      <div class="status">连接状态：{{ status }}</div>
      <button class="btn" type="button" :disabled="status === 'OPEN' || status === 'CONNECTING'" @click="connect">
        连接
      </button>
      <button class="btn" type="button" :disabled="status !== 'OPEN'" @click="disconnect">
        断开
      </button>
    </div>

    <div class="row">
      <div class="status">/chatter：{{ chatterText ?? '（暂无）' }}</div>
      <button class="btn" type="button" :disabled="status !== 'OPEN'" @click="toggleChatter">
        {{ chatterSubscribed ? '取消订阅' : '订阅' }}
      </button>
    </div>

    <div class="row">
      <div class="status">
        /scan（LaserScan）统计：min={{ scanView?.minRange ?? '—' }} max={{ scanView?.maxRange ?? '—' }}
        count={{ scanView?.validCount ?? '—' }}
      </div>
      <button class="btn" type="button" :disabled="status !== 'OPEN'" @click="toggleScan">
        {{ scanSubscribed ? '取消订阅' : '订阅' }}
      </button>
    </div>

    <div v-if="lastError" class="row error">
      错误：{{ lastError }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { onUnmounted, ref } from 'vue'
import { RosbridgeClient } from '../utils/rosbridge'
import { toLaserScanMsg, toLaserScanView, toStdStringMsg, type LaserScanView } from '../utils/ros-msg-convert'

type Status = 'IDLE' | 'CONNECTING' | 'OPEN' | 'CLOSED'

const url = ref('ws://localhost:9090')
const status = ref<Status>('IDLE')
const lastError = ref('')

const chatterText = ref<string | null>(null)
const chatterSubscribed = ref(false)

const scanView = ref<LaserScanView | null>(null)
const scanSubscribed = ref(false)

let client: RosbridgeClient | null = null

async function connect(): Promise<void> {
  lastError.value = ''
  status.value = 'CONNECTING'

  client = new RosbridgeClient(url.value)
  client.connect()

  try {
    await client.waitForOpen(5000)
    status.value = 'OPEN'
  } catch (e) {
    status.value = 'CLOSED'
    lastError.value = e instanceof Error ? e.message : 'connect failed'
  }
}

function disconnect(): void {
  client?.disconnect()
  client = null
  status.value = 'CLOSED'
  chatterSubscribed.value = false
  scanSubscribed.value = false
}

function toggleChatter(): void {
  if (!client) return
  if (!chatterSubscribed.value) {
    client.subscribe('/chatter', 'std_msgs/msg/String', (msg) => {
      const parsed = toStdStringMsg(msg)
      chatterText.value = parsed ? parsed.data : JSON.stringify(msg)
    })
    chatterSubscribed.value = true
    return
  }

  client.unsubscribe('/chatter')
  chatterSubscribed.value = false
}

function toggleScan(): void {
  if (!client) return
  if (!scanSubscribed.value) {
    client.subscribe('/scan', 'sensor_msgs/msg/LaserScan', (msg) => {
      const parsed = toLaserScanMsg(msg)
      scanView.value = parsed ? toLaserScanView(parsed) : null
    })
    scanSubscribed.value = true
    return
  }

  client.unsubscribe('/scan')
  scanSubscribed.value = false
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

.error {
  color: #b91c1c;
}
</style>
