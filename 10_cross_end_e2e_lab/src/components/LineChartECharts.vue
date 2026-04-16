<template>
  <div ref="elRef" class="chart"></div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import * as echarts from 'echarts'

type Point = { t: number; v: number }

const props = defineProps<{
  points: Point[]
  yMin?: number
  yMax?: number
  label?: string
}>()

const elRef = ref<HTMLDivElement | null>(null)

let chart: echarts.ECharts | null = null
let ro: ResizeObserver | null = null
let raf = 0

// time 轴的 label formatter：把默认的长日期缩短为 HH:mm:ss，配合 hideOverlap 避免挤在一起
function formatAxisTime(value: unknown): string {
  const ts = typeof value === 'number' ? value : typeof value === 'string' ? Number(value) : NaN
  if (!Number.isFinite(ts)) return ''
  const d = new Date(ts)
  const hh = String(d.getHours()).padStart(2, '0')
  const mm = String(d.getMinutes()).padStart(2, '0')
  const ss = String(d.getSeconds()).padStart(2, '0')
  return `${hh}:${mm}:${ss}`
}

// 根据 props.points 构建 ECharts option
// - xAxis 用 time 轴，输入数据形如 [timestampMs, value]
// - 关闭动画，提升高频更新时的稳定性与性能
function buildOption(): echarts.EChartsOption {
  const seriesData = props.points.map((p) => [p.t, p.v])
  const shouldScale = props.yMin === undefined || props.yMax === undefined

  return {
    animation: false,
    grid: { left: 40, right: 14, top: 30, bottom: 34 },
    title: props.label
      ? { text: props.label, left: 10, top: 6, textStyle: { fontSize: 12, fontWeight: 'normal', color: '#666' } }
      : undefined,
    tooltip: { trigger: 'axis', axisPointer: { type: 'line' } },
    xAxis: {
      type: 'time',
      splitNumber: 4,
      axisLabel: { color: '#888', hideOverlap: true, margin: 10, formatter: formatAxisTime },
      axisLine: { lineStyle: { color: '#eee' } }
    },
    yAxis: {
      type: 'value',
      min: props.yMin,
      max: props.yMax,
      scale: shouldScale,
      axisLabel: { color: '#888' },
      splitLine: { lineStyle: { color: '#f2f2f2' } },
      axisLine: { lineStyle: { color: '#eee' } }
    },
    series: [{ type: 'line', showSymbol: false, data: seriesData, lineStyle: { width: 2, color: '#1677ff' } }]
  }
}

function render(): void {
  if (!chart) return
  chart.setOption(buildOption(), { notMerge: true, lazyUpdate: true })
}

// 用 requestAnimationFrame 合并多次连续更新（比如 5Hz~几十 Hz 的推送）
function scheduleRender(): void {
  if (raf) cancelAnimationFrame(raf)
  raf = requestAnimationFrame(() => render())
}

function onResize(): void {
  chart?.resize()
}

watch(
  () => props.points,
  () => scheduleRender()
)

watch(
  () => [props.yMin, props.yMax, props.label],
  () => scheduleRender()
)

onMounted(() => {
  const el = elRef.value
  if (!el) return

  chart = echarts.init(el, undefined, { renderer: 'canvas' })
  scheduleRender()

  // 组件容器尺寸变化时自动 resize，避免父容器布局变化导致图表模糊/错位
  if (typeof ResizeObserver !== 'undefined') {
    ro = new ResizeObserver(() => {
      chart?.resize()
    })
    ro.observe(el)
  } else {
    window.addEventListener('resize', onResize)
  }
})

onUnmounted(() => {
  if (raf) cancelAnimationFrame(raf)

  if (ro && elRef.value) ro.unobserve(elRef.value)
  ro = null

  window.removeEventListener('resize', onResize)

  chart?.dispose()
  chart = null
})
</script>

<style scoped>
.chart {
  width: 100%;
  height: 180px;
  border-radius: 10px;
  background: #fff;
}
</style>
