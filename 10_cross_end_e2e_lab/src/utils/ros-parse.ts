import type { DeviceAlarmLevel, DeviceStatePayload, ParamsPayload, VisionDetectionsPayload } from './ros-vm'
import { unwrapMaybeEnvelope } from '../protocol/envelope'

// 这里的所有 parseXXX 函数都面向 rosbridge 的 std_msgs/msg/String：
// msg = { data: "<Envelope JSON string>" }
// JSON 字段约定见 ros-vm.ts（frame_id/stamp_ms/detections, device_id/..., params）
export function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text)
  } catch {
    return null
  }
}

function toNumber(x: unknown): number | null {
  return typeof x === 'number' && Number.isFinite(x) ? x : null
}

function toString(x: unknown): string | null {
  return typeof x === 'string' ? x : null
}

function toBoolean(x: unknown): boolean | null {
  return typeof x === 'boolean' ? x : null
}

function toAlarmLevel(x: unknown): DeviceAlarmLevel | null {
  return x === 'OK' || x === 'WARN' || x === 'ERROR' ? x : null
}

function parseStdStringMsgData(msg: unknown): string | null {
  if (!msg || typeof msg !== 'object' || !('data' in msg)) return null
  const m = msg as { data?: unknown }
  return toString(m.data)
}

function unwrapPayload(input: unknown): unknown | null {
  const r = unwrapMaybeEnvelope(input)
  if (r.kind === 'invalid_envelope') return null
  if (r.kind === 'envelope') return r.envelope.payload
  return null
}

export function parseVisionDetectionsJsonStringMsg(msg: unknown): VisionDetectionsPayload | null {
  const text = parseStdStringMsgData(msg)
  if (!text) return null

  const raw = safeJsonParse(text)
  const data = unwrapPayload(raw)
  if (!data) return null
  if (!data || typeof data !== 'object') return null

  // 视觉检测数据是“最新一帧”的快照：
  // { frame_id: string, stamp_ms: number, detections: Array<{label, score, bbox?}> }
  const d = data as { frame_id?: unknown; stamp_ms?: unknown; detections?: unknown }
  const frame_id = toString(d.frame_id)
  const stamp_ms = toNumber(d.stamp_ms)
  const detectionsRaw = Array.isArray(d.detections) ? d.detections : null
  if (!frame_id || stamp_ms === null || !detectionsRaw) return null

  const detections = detectionsRaw
    .map((item) => {
      if (!item || typeof item !== 'object') return null
      const it = item as { label?: unknown; score?: unknown; bbox?: unknown }
      const label = toString(it.label)
      const score = toNumber(it.score)
      if (!label || score === null) return null

      let bbox: { x: number; y: number; w: number; h: number } | undefined
      if (it.bbox && typeof it.bbox === 'object') {
        const b = it.bbox as { x?: unknown; y?: unknown; w?: unknown; h?: unknown }
        const x = toNumber(b.x)
        const y = toNumber(b.y)
        const w = toNumber(b.w)
        const h = toNumber(b.h)
        if (x !== null && y !== null && w !== null && h !== null) bbox = { x, y, w, h }
      }

      return { label, score, bbox }
    })
    .filter((x): x is NonNullable<typeof x> => x !== null)

  return { frame_id, stamp_ms, detections }
}

export function parseDeviceStateJsonStringMsg(msg: unknown): DeviceStatePayload | null {
  const text = parseStdStringMsgData(msg)
  if (!text) return null

  const raw = safeJsonParse(text)
  const data = unwrapPayload(raw)
  if (!data) return null
  if (!data || typeof data !== 'object') return null

  // 设备状态字段较固定，用显式校验保证前端不会因脏数据崩溃
  const d = data as {
    device_id?: unknown
    online?: unknown
    mode?: unknown
    battery?: unknown
    temperature?: unknown
    alarm_level?: unknown
    stamp_ms?: unknown
  }

  const device_id = toString(d.device_id)
  const online = toBoolean(d.online)
  const mode = toString(d.mode)
  const battery = toNumber(d.battery)
  const temperature = toNumber(d.temperature)
  const alarm_level = toAlarmLevel(d.alarm_level)
  const stamp_ms = toNumber(d.stamp_ms)

  if (
    !device_id ||
    online === null ||
    !mode ||
    battery === null ||
    temperature === null ||
    !alarm_level ||
    stamp_ms === null
  ) {
    return null
  }

  return { device_id, online, mode, battery, temperature, alarm_level, stamp_ms }
}

export function parseParamsJsonStringMsg(msg: unknown): ParamsPayload | null {
  const text = parseStdStringMsgData(msg)
  if (!text) return null

  const raw = safeJsonParse(text)
  const data = unwrapPayload(raw)
  if (!data) return null
  if (!data || typeof data !== 'object') return null

  // 参数快照是 key->value 的对象，value 类型不固定（number/string/bool/对象都可能）
  const d = data as { stamp_ms?: unknown; params?: unknown }
  const stamp_ms = toNumber(d.stamp_ms)
  const params = d.params && typeof d.params === 'object' ? (d.params as Record<string, unknown>) : null
  if (stamp_ms === null || !params) return null

  return { stamp_ms, params }
}
