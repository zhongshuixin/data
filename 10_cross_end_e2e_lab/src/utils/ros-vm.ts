export type VisionBBox = {
  x: number
  y: number
  w: number
  h: number
}

export type VisionDetection = {
  label: string
  score: number
  bbox?: VisionBBox
}

export type VisionDetectionsPayload = {
  frame_id: string
  stamp_ms: number
  detections: VisionDetection[]
}

export type DeviceAlarmLevel = 'OK' | 'WARN' | 'ERROR'

export type DeviceStatePayload = {
  device_id: string
  online: boolean
  mode: string
  battery: number
  temperature: number
  alarm_level: DeviceAlarmLevel
  stamp_ms: number
}

export type ParamsPayload = {
  stamp_ms: number
  params: Record<string, unknown>
}

export type VisionDetectionRowVM = {
  label: string
  scoreText: string
  bboxText: string
}

export type DeviceStateVM = {
  deviceId: string
  onlineText: string
  alarmText: string
  modeText: string
  batteryText: string
  temperatureText: string
  delayText: string
  updatedAtText: string
}

export type ParamRowVM = {
  key: string
  valueText: string
  updatedAtText: string
}
