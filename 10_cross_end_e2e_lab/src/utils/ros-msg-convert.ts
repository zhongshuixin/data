export type StdStringMsg = { data: string }

export function toStdStringMsg(input: unknown): StdStringMsg | null {
  if (!input || typeof input !== 'object') return null
  if (!('data' in input)) return null
  const data = (input as { data: unknown }).data
  return typeof data === 'string' ? { data } : null
}

export type LaserScanMsg = {
  angle_min: number
  angle_max: number
  angle_increment: number
  ranges: number[]
}

export type LaserScanView = {
  minRange: number
  maxRange: number
  validCount: number
}

export function toLaserScanMsg(input: unknown): LaserScanMsg | null {
  if (!input || typeof input !== 'object') return null
  const x = input as Record<string, unknown>

  const angle_min = x.angle_min
  const angle_max = x.angle_max
  const angle_increment = x.angle_increment
  const ranges = x.ranges

  if (
    typeof angle_min !== 'number' ||
    typeof angle_max !== 'number' ||
    typeof angle_increment !== 'number' ||
    !Array.isArray(ranges)
  ) {
    return null
  }

  const numericRanges = ranges.filter((v): v is number => typeof v === 'number')
  return { angle_min, angle_max, angle_increment, ranges: numericRanges }
}

export function toLaserScanView(msg: LaserScanMsg): LaserScanView {
  const finite = msg.ranges.filter((v) => Number.isFinite(v))
  if (finite.length === 0) return { minRange: NaN, maxRange: NaN, validCount: 0 }

  let minRange = finite[0]
  let maxRange = finite[0]
  for (const v of finite) {
    if (v < minRange) minRange = v
    if (v > maxRange) maxRange = v
  }

  return { minRange, maxRange, validCount: finite.length }
}
