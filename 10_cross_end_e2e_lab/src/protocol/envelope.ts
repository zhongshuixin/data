// 统一跨端消息外壳（Envelope）：
// - “外壳字段”尽量稳定：用于版本、追踪、路由与审计
// - “payload”可变：承载具体业务（指令、状态、传感器数据等）
export type Envelope<TPayload extends Record<string, unknown>> = {
  schema_version: string
  trace_id: string
  msg_id: string
  source: string
  target?: string
  topic?: string
  event: string
  ts_ms: number
  content_type?: 'application/json'
  payload: TPayload
}

export type ValidateResult<T> =
  | { ok: true; data: T }
  | { ok: false; code: string; message: string; field?: string }

function isObject(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null && !Array.isArray(x)
}

export function validateEnvelope(input: unknown): ValidateResult<Envelope<Record<string, unknown>>> {
  // 这里不做“业务 payload 的强校验”，只保证 Envelope 的最小合法性：
  // - 能在联调阶段快速发现“类型漂移/字段丢失”
  // - 让日志与错误回执有统一口径（code/message/field）
  if (!isObject(input)) return { ok: false, code: 'BAD_BODY', message: 'body must be object' }

  const requiredStringFields = ['schema_version', 'trace_id', 'msg_id', 'source', 'event'] as const
  for (const field of requiredStringFields) {
    if (typeof input[field] !== 'string' || input[field] === '') {
      return { ok: false, code: 'BAD_FIELD', message: `${field} must be non-empty string`, field }
    }
  }

  if (typeof input.ts_ms !== 'number' || !Number.isFinite(input.ts_ms)) {
    return { ok: false, code: 'BAD_FIELD_TYPE', message: 'ts_ms must be finite number', field: 'ts_ms' }
  }

  if (!isObject(input.payload)) {
    return { ok: false, code: 'BAD_FIELD_TYPE', message: 'payload must be object', field: 'payload' }
  }

  return { ok: true, data: input as Envelope<Record<string, unknown>> }
}

export type UnwrapEnvelopeResult =
  | { kind: 'raw'; data: unknown }
  | { kind: 'envelope'; envelope: Envelope<Record<string, unknown>> }
  | { kind: 'invalid_envelope'; error: ValidateResult<Envelope<Record<string, unknown>>> }

export function unwrapMaybeEnvelope(input: unknown): UnwrapEnvelopeResult {
  if (!isObject(input)) return { kind: 'raw', data: input }
  if (!('schema_version' in input)) return { kind: 'raw', data: input }
  const v = validateEnvelope(input)
  if (!v.ok) return { kind: 'invalid_envelope', error: v }
  return { kind: 'envelope', envelope: v.data }
}

export function makeTraceId(prefix = 'T'): string {
  // trace_id：贯穿一次业务闭环（请求→执行→回执）的追踪主键
  const ts = Date.now()
  const rand = Math.random().toString(16).slice(2, 8)
  const day = new Date(ts)
  const y = String(day.getFullYear())
  const m = String(day.getMonth() + 1).padStart(2, '0')
  const d = String(day.getDate()).padStart(2, '0')
  return `${prefix}-${y}${m}${d}-${rand}`
}

export function makeMsgId(prefix = 'M'): string {
  // msg_id：单条消息唯一 id（用于去重、定位某一条“具体消息”）
  const ts = Date.now()
  const rand = Math.random().toString(16).slice(2, 8)
  const day = new Date(ts)
  const y = String(day.getFullYear())
  const m = String(day.getMonth() + 1).padStart(2, '0')
  const d = String(day.getDate()).padStart(2, '0')
  return `${prefix}-${y}${m}${d}-${rand}`
}

export function makeEnvelope<TPayload extends Record<string, unknown>>(input: {
  schema_version?: string
  trace_id?: string
  msg_id?: string
  source: string
  target?: string
  topic?: string
  event: string
  ts_ms?: number
  content_type?: 'application/json'
  payload: TPayload
}): Envelope<TPayload> {
  return {
    schema_version: input.schema_version ?? '1.0.0',
    trace_id: input.trace_id ?? makeTraceId(),
    msg_id: input.msg_id ?? makeMsgId(),
    source: input.source,
    target: input.target,
    topic: input.topic,
    event: input.event,
    ts_ms: input.ts_ms ?? Date.now(),
    content_type: input.content_type,
    payload: input.payload
  }
}
