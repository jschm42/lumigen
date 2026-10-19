<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import type { Asset } from '@/types'
import GalleryCard from './GalleryCard.vue'

/**
 * Virtualized, optionally date-grouped asset grid.
 *
 * Only rows near the viewport are rendered, so galleries with thousands of images stay
 * fast. Item positions are computed here, which also lets the rubber-band selection
 * hit items that are currently not rendered.
 */
interface Props {
  assets: Asset[]
  scrollEl: HTMLElement | null
  thumbSize: 'sm' | 'md' | 'lg'
  groupByDate?: boolean
  selectedIds: number[]
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'selection', ids: number[]): void
  (e: 'hover', id: number | null): void
}>()

const SIZES = {
  sm: { min: 120, gap: 8, minCols: 3 },
  md: { min: 180, gap: 12, minCols: 2 },
  lg: { min: 280, gap: 16, minCols: 1 },
} as const
const HEADER_HEIGHT = 44
const OVERSCAN_PX = 800
const DRAG_THRESHOLD_PX = 6
// Room for the stacked-card backplates that peek out above the first row.
const TOP_PADDING = 8

const rootRef = ref<HTMLElement | null>(null)
const width = ref(0)
const scrollTop = ref(0)
const viewportHeight = ref(0)
const gridOffset = ref(0)

// --- Layout ------------------------------------------------------------------
const metrics = computed(() => {
  const spec = SIZES[props.thumbSize] || SIZES.md
  const available = Math.max(width.value, 1)
  const cols = Math.max(spec.minCols, Math.floor((available + spec.gap) / (spec.min + spec.gap)))
  const cell = Math.max(40, (available - spec.gap * (cols - 1)) / cols)
  return { cols, cell, gap: spec.gap }
})

function dayKey(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'unknown'
  return `${date.getFullYear()}-${date.getMonth()}-${date.getDate()}`
}

function dayLabel(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return 'Unknown date'
  const today = new Date()
  const yesterday = new Date()
  yesterday.setDate(today.getDate() - 1)
  if (date.toDateString() === today.toDateString()) return 'Today'
  if (date.toDateString() === yesterday.toDateString()) return 'Yesterday'
  const sameYear = date.getFullYear() === today.getFullYear()
  return date.toLocaleDateString('en-US', {
    weekday: 'long',
    day: 'numeric',
    month: 'long',
    ...(sameYear ? {} : { year: 'numeric' }),
  })
}

interface Row {
  key: string
  type: 'header' | 'items'
  top: number
  height: number
  label?: string
  count?: number
  items?: Asset[]
}

interface ItemBox {
  id: number
  x: number
  y: number
  size: number
}

const layout = computed(() => {
  const { cols, cell, gap } = metrics.value
  const rows: Row[] = []
  const boxes: ItemBox[] = []
  let top = TOP_PADDING

  const groups: { key: string; label: string; items: Asset[] }[] = []
  if (props.groupByDate) {
    for (const asset of props.assets) {
      const key = dayKey(asset.created_at)
      const last = groups[groups.length - 1]
      if (last && last.key === key) last.items.push(asset)
      else groups.push({ key, label: dayLabel(asset.created_at), items: [asset] })
    }
  } else {
    groups.push({ key: 'all', label: '', items: props.assets })
  }

  for (const group of groups) {
    if (props.groupByDate) {
      rows.push({ key: `h-${group.key}`, type: 'header', top, height: HEADER_HEIGHT, label: group.label, count: group.items.length })
      top += HEADER_HEIGHT
    }
    for (let i = 0; i < group.items.length; i += cols) {
      const items = group.items.slice(i, i + cols)
      items.forEach((asset, col) => {
        boxes.push({ id: asset.id, x: col * (cell + gap), y: top, size: cell })
      })
      rows.push({ key: `r-${group.key}-${i}`, type: 'items', top, height: cell + gap, items })
      top += cell + gap
    }
  }
  return { rows, boxes, height: top }
})

/** Index of the first row whose bottom edge is below ``y`` (binary search). */
function firstRowBelow(y: number): number {
  const rows = layout.value.rows
  let lo = 0
  let hi = rows.length - 1
  let result = rows.length
  while (lo <= hi) {
    const mid = (lo + hi) >> 1
    if (rows[mid].top + rows[mid].height >= y) {
      result = mid
      hi = mid - 1
    } else {
      lo = mid + 1
    }
  }
  return result
}

const visibleRows = computed(() => {
  const rows = layout.value.rows
  if (rows.length === 0) return []
  const start = scrollTop.value - gridOffset.value - OVERSCAN_PX
  const end = scrollTop.value - gridOffset.value + viewportHeight.value + OVERSCAN_PX
  const result: Row[] = []
  for (let i = firstRowBelow(start); i < rows.length && rows[i].top <= end; i++) {
    result.push(rows[i])
  }
  return result
})

// --- Measuring ---------------------------------------------------------------
let frame = 0
function measure() {
  frame = 0
  const root = rootRef.value
  const scroller = props.scrollEl
  if (!root || !scroller) return
  width.value = root.clientWidth
  scrollTop.value = scroller.scrollTop
  viewportHeight.value = scroller.clientHeight
  gridOffset.value = root.getBoundingClientRect().top - scroller.getBoundingClientRect().top + scroller.scrollTop
}

function scheduleMeasure() {
  if (!frame) frame = requestAnimationFrame(measure)
}

let resizeObserver: ResizeObserver | null = null

function attachScroller(el: HTMLElement | null, previous?: HTMLElement | null) {
  previous?.removeEventListener('scroll', scheduleMeasure)
  el?.addEventListener('scroll', scheduleMeasure, { passive: true })
  scheduleMeasure()
}

watch(() => props.scrollEl, (el, previous) => attachScroller(el, previous))
watch(() => props.assets.length, scheduleMeasure)

onMounted(() => {
  attachScroller(props.scrollEl)
  resizeObserver = new ResizeObserver(scheduleMeasure)
  if (rootRef.value) resizeObserver.observe(rootRef.value)
  if (props.scrollEl) resizeObserver.observe(props.scrollEl)
  window.addEventListener('resize', scheduleMeasure)
})

onUnmounted(() => {
  props.scrollEl?.removeEventListener('scroll', scheduleMeasure)
  resizeObserver?.disconnect()
  window.removeEventListener('resize', scheduleMeasure)
  if (frame) cancelAnimationFrame(frame)
  stopDrag()
})

// --- Rubber-band selection ----------------------------------------------------
const dragRect = ref<{ x: number; y: number; w: number; h: number } | null>(null)
let dragStart: { x: number; y: number } | null = null
let dragBase: number[] = []
let isDragging = false
let lastClient = { x: 0, y: 0 }
let autoScrollFrame = 0

function toContent(clientX: number, clientY: number) {
  const rect = rootRef.value!.getBoundingClientRect()
  return { x: clientX - rect.left, y: clientY - rect.top }
}

function updateDragSelection() {
  if (!dragStart || !rootRef.value) return
  const current = toContent(lastClient.x, lastClient.y)
  const x = Math.min(dragStart.x, current.x)
  const y = Math.min(dragStart.y, current.y)
  const w = Math.abs(current.x - dragStart.x)
  const h = Math.abs(current.y - dragStart.y)
  if (!isDragging && Math.hypot(w, h) < DRAG_THRESHOLD_PX) return
  isDragging = true
  dragRect.value = { x, y, w, h }
  const hits = layout.value.boxes
    .filter((box) => box.x < x + w && box.x + box.size > x && box.y < y + h && box.y + box.size > y)
    .map((box) => box.id)
  emit('selection', Array.from(new Set([...dragBase, ...hits])))
}

function autoScroll() {
  autoScrollFrame = 0
  const scroller = props.scrollEl
  if (!scroller || !dragStart) return
  const rect = scroller.getBoundingClientRect()
  const edge = 48
  let delta = 0
  if (lastClient.y < rect.top + edge) delta = -Math.ceil((rect.top + edge - lastClient.y) / 3)
  else if (lastClient.y > rect.bottom - edge) delta = Math.ceil((lastClient.y - (rect.bottom - edge)) / 3)
  if (delta !== 0 && isDragging) {
    scroller.scrollTop += delta
    updateDragSelection()
  }
  autoScrollFrame = requestAnimationFrame(autoScroll)
}

function onMouseMove(e: MouseEvent) {
  lastClient = { x: e.clientX, y: e.clientY }
  updateDragSelection()
  if (isDragging) e.preventDefault()
}

function suppressClick(e: MouseEvent) {
  e.stopPropagation()
  e.preventDefault()
}

function stopDrag() {
  window.removeEventListener('mousemove', onMouseMove)
  window.removeEventListener('mouseup', onMouseUp)
  if (autoScrollFrame) cancelAnimationFrame(autoScrollFrame)
  autoScrollFrame = 0
  dragStart = null
  dragRect.value = null
}

function onMouseUp() {
  const wasDragging = isDragging
  stopDrag()
  isDragging = false
  if (wasDragging) {
    // The click that follows this mouseup must not open the detail dialog.
    window.addEventListener('click', suppressClick, { capture: true })
    setTimeout(() => window.removeEventListener('click', suppressClick, { capture: true }), 0)
  }
}

function onMouseDown(e: MouseEvent) {
  if (e.button !== 0 || !rootRef.value) return
  const target = e.target as HTMLElement
  if (target.closest('button, input, select, textarea, a')) return
  dragStart = toContent(e.clientX, e.clientY)
  lastClient = { x: e.clientX, y: e.clientY }
  dragBase = e.shiftKey || e.ctrlKey || e.metaKey ? [...props.selectedIds] : []
  isDragging = false
  window.addEventListener('mousemove', onMouseMove)
  window.addEventListener('mouseup', onMouseUp)
  autoScrollFrame = requestAnimationFrame(autoScroll)
}

// --- Hover / focus tracking (keyboard rating) ----------------------------------
function assetIdFromEvent(e: Event): number | null {
  const el = (e.target as HTMLElement | null)?.closest('[data-asset-id]') as HTMLElement | null
  if (!el) return null
  const id = Number(el.dataset.assetId)
  return Number.isFinite(id) ? id : null
}

function onPointerOver(e: Event) {
  emit('hover', assetIdFromEvent(e))
}

defineExpose({ measure: scheduleMeasure })
</script>

<template>
  <div
    ref="rootRef"
    class="relative select-none"
    :style="{ height: `${layout.height}px` }"
    data-testid="gallery-grid"
    @mousedown="onMouseDown"
    @mouseover="onPointerOver"
    @focusin="onPointerOver"
    @mouseleave="emit('hover', null)"
  >
    <template v-for="row in visibleRows" :key="row.key">
      <div
        v-if="row.type === 'header'"
        class="absolute inset-x-0 flex items-end gap-2 px-1 pb-2"
        :style="{ top: `${row.top}px`, height: `${row.height}px` }"
        data-testid="gallery-date-header"
      >
        <span class="text-sm font-bold text-slate-800 dark:text-slate-100">{{ row.label }}</span>
        <span class="text-[11px] text-slate-400">{{ row.count }} {{ row.count === 1 ? 'image' : 'images' }}</span>
      </div>
      <div
        v-else
        class="absolute inset-x-0 grid"
        :style="{
          top: `${row.top}px`,
          gridTemplateColumns: `repeat(${metrics.cols}, minmax(0, 1fr))`,
          columnGap: `${metrics.gap}px`,
        }"
      >
        <GalleryCard v-for="asset in row.items" :key="asset.id" :asset="asset" />
      </div>
    </template>

    <div
      v-if="dragRect"
      class="pointer-events-none absolute z-40 rounded-md border border-sky-400 bg-sky-400/15"
      :style="{ left: `${dragRect.x}px`, top: `${dragRect.y}px`, width: `${dragRect.w}px`, height: `${dragRect.h}px` }"
      data-testid="gallery-drag-rect"
    />
  </div>
</template>
