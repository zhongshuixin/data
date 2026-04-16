<template>
  <div class="wrap">
    <h2>ROS2 数据实时监控面板（10）</h2>

    <div class="row">
      <label class="label" for="url">rosbridge URL</label>
      <input id="url" v-model="url" class="input" type="text" />
    </div>

    <div class="row">
      <div class="status">连接状态：{{ status }}</div>
      <button class="btn" type="button" :disabled="status === 'OPEN' || status === 'CONNECTING'" @click="connect">
        连接
      </button>
      <button class="btn" type="button" :disabled="status !== 'OPEN'" @click="disconnect">断开</button>
    </div>

    <div class="grid">
      <section class="card">
        <h3>设备状态</h3>
        <div class="kv"><span class="k">设备</span><span class="v">{{ deviceVm?.deviceId ?? '—' }}</span></div>
        <div class="kv"><span class="k">在线</span><span class="v">{{ deviceVm?.onlineText ?? '—' }}</span></div>
        <div class="kv"><span class="k">模式</span><span class="v">{{ deviceVm?.modeText ?? '—' }}</span></div>
        <div class="kv"><span class="k">告警</span><span class="v">{{ deviceVm?.alarmText ?? '—' }}</span></div>
        <div class="kv"><span class="k">电量</span><span class="v">{{ deviceVm?.batteryText ?? '—' }}</span></div>
        <div class="kv"><span class="k">温度</span><span class="v">{{ deviceVm?.temperatureText ?? '—' }}</span></div>
        <div class="kv"><span class="k">延迟</span><span class="v">{{ deviceVm?.delayText ?? '—' }}</span></div>
        <div class="kv"><span class="k">更新时间</span><span class="v">{{ deviceVm?.updatedAtText ?? '—' }}</span></div>
      </section>

      <section class="card">
        <h3>实时曲线</h3>
        <LineChartECharts :points="batteryPoints" :y-min="0" :y-max="100" label="battery(%)" />
        <div class="spacer"></div>
        <LineChartECharts :points="tempPoints" label="temp(℃)" />
      </section>

      <section class="card">
        <h3>视觉检测（最新一帧）</h3>
        <div class="muted">frame: {{ visionFrameId ?? '—' }} | time: {{ visionUpdatedAtText ?? '—' }}</div>
        <table class="table">
          <thead>
            <tr>
              <th>label</th>
              <th>score</th>
              <th>bbox</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(row, idx) in visionRows" :key="idx">
              <td>{{ row.label }}</td>
              <td>{{ row.scoreText }}</td>
              <td class="muted">{{ row.bboxText }}</td>
            </tr>
            <tr v-if="visionRows.length === 0">
              <td class="muted" colspan="3">（暂无数据）</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section class="card span2">
        <h3>参数快照（最新）</h3>
        <div class="muted">time: {{ paramsUpdatedAtText ?? '—' }}</div>
        <table class="table">
          <thead>
            <tr>
              <th style="width: 240px">key</th>
              <th>value</th>
              <th style="width: 160px">updated</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in paramRows" :key="row.key">
              <td>{{ row.key }}</td>
              <td>{{ row.valueText }}</td>
              <td class="muted">{{ row.updatedAtText }}</td>
            </tr>
            <tr v-if="paramRows.length === 0">
              <td class="muted" colspan="3">（暂无数据）</td>
            </tr>
          </tbody>
        </table>
      </section>
    </div>

    <div v-if="lastError" class="row error">错误：{{ lastError }}</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import LineChartECharts from './LineChartECharts.vue'
import { useRosbridgeUrl } from '../composables/useRosbridgeUrl'
import { RosbridgeClient } from '../utils/rosbridge'
import { parseDeviceStateJsonStringMsg, parseParamsJsonStringMsg, parseVisionDetectionsJsonStringMsg } from '../utils/ros-parse'
import { RingBuffer, type Point } from '../utils/ring-buffer'
import type { DeviceStatePayload, DeviceStateVM, ParamRowVM, VisionDetectionRowVM } from '../utils/ros-vm'

type Status = 'IDLE' | 'CONNECTING' | 'OPEN' | 'CLOSED'

// 页面核心逻辑：
// 1) 通过 rosbridge WebSocket 订阅 3 个 JSON 字符串话题（设备状态/参数快照/视觉检测）
// 2) 解析后写入响应式状态，派生出用于展示的 VM（格式化文本、在线判定、延迟计算）
// 3) 设备状态同时写入环形缓存，驱动 ECharts 的实时曲线

const { url } = useRosbridgeUrl('ws://localhost:9090')
const status = ref<Status>('IDLE')
const lastError = ref('')

let client: RosbridgeClient | null = null

const visionFrameId = ref<string | null>(null)
const visionUpdatedAt = ref<number | null>(null)
const visionRows = ref<VisionDetectionRowVM[]>([])

// 设备状态原始 payload（来自 /device/state_json）与当前本机时钟（用于延迟/超时判定）
const devicePayload = ref<DeviceStatePayload | null>(null)
const nowTick = ref(Date.now())

// 参数快照（来自 /device/params_json），每条 key/value 都显示同一批次的更新时间
const paramsUpdatedAt = ref<number | null>(null)
const paramRows = ref<ParamRowVM[]>([])

// 实时曲线数据源：固定长度 ring buffer，避免点无限增长导致卡顿
const batterySeries = new RingBuffer(120)
const tempSeries = new RingBuffer(120)
const batteryPoints = ref<Point[]>([])
const tempPoints = ref<Point[]>([])

let lastDeviceSeriesT: number | null = null
const deviceStampTrusted = ref(false)

// 将上游 stamp 转成 epoch(ms)：
// - 约定字段名为 stamp_ms，但有些示例会误传 sec/us/ns，这里做容错
// - 只接受落在 2000~2100 的合理区间，避免把随机数“误解析成时间”
function parseEpochMs(input: number): number | null {
  if (!Number.isFinite(input)) return null
  if (input <= 0) return null

  const minMs = Date.UTC(2000, 0, 1)
  const maxMs = Date.UTC(2100, 0, 1)

  if (input >= minMs && input <= maxMs) return Math.floor(input)

  const asSec = input * 1000
  if (asSec >= minMs && asSec <= maxMs) return Math.floor(asSec)

  const asUs = input / 1000
  if (asUs >= minMs && asUs <= maxMs) return Math.floor(asUs)

  const asNs = input / 1_000_000
  if (asNs >= minMs && asNs <= maxMs) return Math.floor(asNs)

  return null
}

// 解析失败则回退使用接收时刻（本机时间），并标记 trusted=false
function resolveStampMs(raw: number, receiveMs: number): { stampMs: number; trusted: boolean } {
  const parsed = parseEpochMs(raw)
  if (parsed === null) return { stampMs: receiveMs, trusted: false }
  return { stampMs: parsed, trusted: true }
}

// 时间格式化：本机时区
function formatTime(tsMs: number): string {
  const d = new Date(tsMs)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  const ms = String(d.getMilliseconds()).padStart(3, '0')
  return `${hh}:${mm}:${ss}.${ms}`
}

function formatDateTime(tsMs: number): string {
  const d = new Date(tsMs)
  const yyyy = String(d.getFullYear())
  const MM = String(d.getMonth() + 1).padStart(2, '0')
  const dd = String(d.getDate()).padStart(2, '0')
  return `${yyyy}-${MM}-${dd} ${formatTime(tsMs)}`
}

const visionUpdatedAtText = computed(() => (visionUpdatedAt.value ? formatDateTime(visionUpdatedAt.value) : null))
const paramsUpdatedAtText = computed(() => (paramsUpdatedAt.value ? formatDateTime(paramsUpdatedAt.value) : null))

// deviceVm 只负责“展示用字段”：
// - delayMs = 本机 nowTick - 上游 stamp_ms（可信时才展示）
// - 超过 3s 认为设备离线（超时）
const deviceVm = computed<DeviceStateVM | null>(() => {
  const p = devicePayload.value
  if (!p) return null
  const delayMs = Math.max(0, nowTick.value - p.stamp_ms)
  const isTimeout = delayMs > 3000
  return {
    deviceId: p.device_id,
    onlineText: p.online && !isTimeout ? '在线' : isTimeout ? '离线（超时）' : '离线',
    alarmText: formatAlarmText(p.alarm_level),
    modeText: p.mode,
    batteryText: `${p.battery.toFixed(1)}%`,
    temperatureText: `${p.temperature.toFixed(1)}℃`,
    delayText: deviceStampTrusted.value ? `${delayMs}ms` : '—',
    updatedAtText: formatTime(p.stamp_ms)
  }
})

let tickTimer: number | null = null

// connect() 做三件事：
// 1) 建立 rosbridge WebSocket 连接
// 2) 启动 tick，驱动“延迟/超时”实时刷新
// 3) subscribe 三个话题并写入状态
async function connect(): Promise<void> { // 承诺：函数执行完没有返回值
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
    client?.disconnect()
    client = null
    return
  }

  startTick()

  // /vision/detections_json: std_msgs/String，data 为 JSON 字符串
  client.subscribe('/vision/detections_json', 'std_msgs/msg/String', (msg) => {
    const receiveMs = Date.now()
    const p = parseVisionDetectionsJsonStringMsg(msg)
    if (!p) return
    const { stampMs } = resolveStampMs(p.stamp_ms, receiveMs)
    visionFrameId.value = p.frame_id
    visionUpdatedAt.value = stampMs
    const rows = p.detections.map((d) => ({
      label: d.label,
      scoreText: formatPercent(d.score),
      bboxText: d.bbox ? `${d.bbox.x},${d.bbox.y},${d.bbox.w},${d.bbox.h}` : '—'
    }))
    visionRows.value = keepLatestN(rows, 30)
  })

  // /device/state_json: 设备状态 + stamp_ms
  // 这里做了时间戳单调递增保护，避免 ECharts time 轴因点乱序/重复导致看起来“不画线”
  client.subscribe(
    '/device/state_json',
    'std_msgs/msg/String',
    (msg) => {
      const receiveMs = Date.now()
      const p = parseDeviceStateJsonStringMsg(msg)
      if (!p) return
      let { stampMs, trusted } = resolveStampMs(p.stamp_ms, receiveMs)
      if (lastDeviceSeriesT !== null && stampMs <= lastDeviceSeriesT) {
        stampMs = Math.max(receiveMs, lastDeviceSeriesT + 1)
        trusted = false
      }
      lastDeviceSeriesT = stampMs
      deviceStampTrusted.value = trusted
      devicePayload.value = { ...p, stamp_ms: stampMs }

      batterySeries.push({ t: stampMs, v: p.battery })
      tempSeries.push({ t: stampMs, v: p.temperature })
      batteryPoints.value = batterySeries.toArray()
      tempPoints.value = tempSeries.toArray()
    },
    { throttle_rate: 200, queue_length: 1 }
  )

  // /device/params_json: 一组参数快照，params 是 key->value 的对象
  client.subscribe('/device/params_json', 'std_msgs/msg/String', (msg) => {
    const receiveMs = Date.now()
    const p = parseParamsJsonStringMsg(msg)
    if (!p) return
    const { stampMs } = resolveStampMs(p.stamp_ms, receiveMs)
    paramsUpdatedAt.value = stampMs
    const rows = Object.entries(p.params)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([key, value]) => ({
        key,
        valueText: formatAny(value),
        updatedAtText: formatDateTime(stampMs)
      }))
    paramRows.value = rows
  })
}

function disconnect(): void {
  stopTick()
  client?.disconnect()
  client = null
  status.value = 'CLOSED'
}

function startTick(): void {
  stopTick()
  tickTimer = window.setInterval(() => {
    nowTick.value = Date.now()
  }, 300)
}

function stopTick(): void {
  if (!tickTimer) return
  window.clearInterval(tickTimer)
  tickTimer = null
}

function formatPercent(x: number): string {
  const v = Math.max(0, Math.min(1, x))
  return `${(v * 100).toFixed(1)}%`
}

function formatAlarmText(level: 'OK' | 'WARN' | 'ERROR'): string {
  return level === 'OK' ? '正常' : level === 'WARN' ? '预警' : '故障'
}

function formatAny(v: unknown): string {
  if (typeof v === 'string') return v
  if (typeof v === 'number') return Number.isFinite(v) ? String(v) : 'NaN'
  if (typeof v === 'boolean') return v ? 'true' : 'false'
  if (v === null) return 'null'
  if (v === undefined) return 'undefined'
  try {
    return JSON.stringify(v)
  } catch {
    return String(v)
  }
}

function keepLatestN<T>(arr: T[], n: number): T[] {
  if (arr.length <= n) return arr
  return arr.slice(arr.length - n)
}

onUnmounted(() => {
  disconnect()
})
</script>

<style scoped>
.wrap {
  max-width: 1120px;
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

.grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.card {
  border: 1px solid #eee;
  border-radius: 12px;
  padding: 12px;
  background: #fff;
}

.span2 {
  grid-column: span 2;
}

.spacer {
  height: 8px;
}

.kv {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  padding: 4px 0;
}

.k {
  color: #666;
}

.v {
  color: #111;
}

.muted {
  color: #888;
  font-size: 12px;
}

.table {
  width: 100%;
  border-collapse: collapse;
  margin-top: 8px;
}

.table th,
.table td {
  border-top: 1px solid #f0f0f0;
  padding: 6px 8px;
  text-align: left;
  vertical-align: top;
}

.error {
  color: #b91c1c;
}
</style>
