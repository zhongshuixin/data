export type Point = { t: number; v: number }

// 固定容量的环形缓冲区：
// - push 覆盖最旧元素，避免数组无限增长
// - toArray 返回“时间顺序”的新数组，直接喂给图表组件
export class RingBuffer {
  private readonly cap: number
  private data: Point[]
  private head = 0
  private size = 0

  constructor(capacity: number) {
    this.cap = Math.max(1, Math.floor(capacity))
    this.data = new Array<Point>(this.cap)
  }

  push(p: Point): void {
    this.data[this.head] = p
    this.head = (this.head + 1) % this.cap
    this.size = Math.min(this.size + 1, this.cap)
  }

  toArray(): Point[] {
    if (this.size === 0) return []
    const start = (this.head - this.size + this.cap) % this.cap
    const out: Point[] = []
    for (let i = 0; i < this.size; i += 1) {
      out.push(this.data[(start + i) % this.cap])
    }
    return out
  }
}
