<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Film, Gauge, GripVertical, RotateCcw, ZoomIn } from 'lucide-vue-next'
import type { Asset, Generation } from '@/types'
import { useAuthStore } from '@/stores/auth'
import { useGenerateStore } from '@/stores/generate'
import { useImageViewerStore } from '@/stores/imageViewer'
import { useToastStore } from '@/stores/toast'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import Select, { type SelectOption } from '@/components/ui/Select.vue'
import Spinner from '@/components/ui/Spinner.vue'
import AnimationFrameActions from './AnimationFrameActions.vue'
import GenerationActions from './GenerationActions.vue'
import { formatDuration } from '@/utils/format'

const props = defineProps<{
  generation: Generation
  elapsedSeconds: number
  liveSlotLabel: string
}>()

const emit = defineEmits<{
  (e: 'image-loaded'): void
  (e: 'delete'): void
}>()

const authStore = useAuthStore()
const generateStore = useGenerateStore()
const imageViewerStore = useImageViewerStore()
const toastStore = useToastStore()

const formatOptions: SelectOption[] = [
  { value: 'gif', label: 'GIF' },
  { value: 'webp', label: 'WebP' },
]

const defaultFrameMs = computed(() => authStore.uiSettings.animation_default_frame_ms || 100)
const selectedFormat = ref<'gif' | 'webp'>(props.generation.animation?.output === 'webp' ? 'webp' : 'gif')
watch(
  () => props.generation.animation?.output,
  (out) => {
    if (out === 'gif' || out === 'webp') selectedFormat.value = out
  }
)

const isBusy = computed(() => ['queued', 'running', 'pending', 'processing'].includes(props.generation.status))
const isAssembling = computed(() => isBusy.value && props.generation.agentic_step === 'assembling')
const isGeneratingFrames = computed(() => isBusy.value && props.generation.agentic_step !== 'assembling')
const isBuilding = ref(false)

/** Individual frame assets sorted by persisted stack order. */
const serverFrames = computed<Asset[]>(() =>
  (props.generation.assets || [])
    .filter((a) => a.metadata?.role === 'frame' || (!a.metadata?.role && a.mime === 'image/png'))
    .sort((a, b) => (a.stack_order ?? 0) - (b.stack_order ?? 0) || a.id - b.id)
)

/** Assembled GIF / animated WebP asset shown in its own result row below the frame set. */
const animationAsset = computed<Asset | null>(
  () => (props.generation.assets || []).find((a) => a.metadata?.role === 'animation') || null
)

function originalIndex(asset: Asset): number {
  const raw = asset.metadata?.frame_index
  return typeof raw === 'number' && Number.isFinite(raw) ? raw : asset.id
}

const originalIds = computed<number[]>(() =>
  [...serverFrames.value].sort((a, b) => originalIndex(a) - originalIndex(b) || a.id - b.id).map((a) => a.id)
)

function deriveServerFrameMs(): string {
  if (props.generation.animation?.frame_ms != null) return String(props.generation.animation.frame_ms)
  const durations = serverFrames.value
    .map((a) => a.metadata?.duration_ms)
    .filter((d): d is number => typeof d === 'number' && d > 0)
  if (durations.length > 0 && durations.every((d) => d === durations[0])) return String(durations[0])
  return ''
}

const orderedIds = ref<number[]>([])
const disabledIds = ref<Set<number>>(new Set())
const frameMsInput = ref<string>(deriveServerFrameMs())
let previousFrameIndexById = new Map<number, number>()
let knownIds = new Set<number>()

watch(
  serverFrames,
  (incoming) => {
    const byId = new Map(incoming.map((a) => [a.id, a]))
    const byFrameIdx = new Map<number, Asset>()
    incoming.forEach((a) => {
      if (typeof a.metadata?.frame_index === 'number') byFrameIdx.set(a.metadata.frame_index, a)
    })
    const nextOrder: number[] = []
    const nextDisabled = new Set<number>()
    const seen = new Set<number>()

    for (const oldId of orderedIds.value) {
      if (byId.has(oldId) && !seen.has(oldId)) {
        nextOrder.push(oldId)
        seen.add(oldId)
        if (disabledIds.value.has(oldId)) nextDisabled.add(oldId)
        continue
      }
      const prevFrameIdx = previousFrameIndexById.get(oldId)
      const replacement = prevFrameIdx !== undefined ? byFrameIdx.get(prevFrameIdx) : undefined
      if (replacement && !seen.has(replacement.id)) {
        nextOrder.push(replacement.id)
        seen.add(replacement.id)
        if (disabledIds.value.has(oldId)) nextDisabled.add(replacement.id)
      }
    }
    for (const asset of incoming) {
      if (!seen.has(asset.id)) {
        nextOrder.push(asset.id)
        seen.add(asset.id)
        if (asset.metadata?.disabled) nextDisabled.add(asset.id)
      } else if (!knownIds.has(asset.id) && asset.metadata?.disabled) {
        nextDisabled.add(asset.id)
      }
    }
    orderedIds.value = nextOrder
    disabledIds.value = nextDisabled
    knownIds = new Set(incoming.map((a) => a.id))
    previousFrameIndexById = new Map(
      incoming
        .filter((a) => typeof a.metadata?.frame_index === 'number')
        .map((a) => [a.id, a.metadata!.frame_index as number])
    )
    if (!frameMsInput.value) frameMsInput.value = deriveServerFrameMs()
  },
  { immediate: true }
)

const frames = computed<Asset[]>(() => {
  const byId = new Map(serverFrames.value.map((a) => [a.id, a]))
  return orderedIds.value.map((id) => byId.get(id)).filter((a): a is Asset => !!a)
})

const enabledIds = computed(() => orderedIds.value.filter((id) => !disabledIds.value.has(id)))
const activeIndexMap = computed(() => new Map(enabledIds.value.map((id, idx) => [id, idx + 1])))
const canReorder = computed(() => frames.value.length > 1 && !isBusy.value && !isBuilding.value)

function sameSequence(a: number[], b: number[]): boolean {
  return a.length === b.length && a.every((val, idx) => val === b[idx])
}

const isOriginalOrder = computed(() => sameSequence(orderedIds.value, originalIds.value))
const canReset = computed(() => !isOriginalOrder.value || disabledIds.value.size > 0)

function parseFrameMs(text: string): number | null | 'invalid' {
  const trimmed = String(text ?? '').trim()
  if (!trimmed) return null
  const num = Number.parseInt(trimmed, 10)
  return Number.isFinite(num) && num >= 20 && num <= 10000 ? num : 'invalid'
}

const fpsLabel = computed(() => {
  const parsed = parseFrameMs(frameMsInput.value)
  const ms = typeof parsed === 'number' ? parsed : defaultFrameMs.value
  const fps = 1000 / ms
  return `${Number.isInteger(fps) ? fps : fps.toFixed(1)} fps`
})

const hasPendingChanges = computed(() => {
  const builtIds = animationAsset.value?.metadata?.frame_asset_ids
  const baseIds = Array.isArray(builtIds)
    ? builtIds
    : serverFrames.value.filter((a) => !a.metadata?.disabled).map((a) => a.id)
  if (!sameSequence(enabledIds.value, baseIds)) return true
  const parsed = parseFrameMs(frameMsInput.value)
  if (typeof parsed === 'number') {
    const builtDurations = animationAsset.value?.metadata?.durations_ms
    if (Array.isArray(builtDurations) && builtDurations.length > 0 && !builtDurations.every((d: number) => d === parsed)) {
      return true
    }
  }
  return false
})

const isTransparent = computed(
  () => !!props.generation.animation?.transparent || !!animationAsset.value?.metadata?.transparent
)

const frameAspect = computed(() => {
  const ratio = props.generation.aspect_ratio || '1:1'
  const [w, h] = ratio.split(':').map(Number)
  return w && h ? `${w} / ${h}` : '1 / 1'
})

const frameGridClass = computed(() => {
  const count = Math.max(
    props.generation.total_planned || 0,
    frames.value.length + (isGeneratingFrames.value ? 1 : 0),
    2
  )
  if (count === 2) return 'grid-cols-2 sm:grid-cols-2'
  if (count === 3) return 'grid-cols-2 sm:grid-cols-3'
  if (count === 4) return 'grid-cols-2 sm:grid-cols-4'
  return 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-6'
})

const resultFormatLabel = computed(() => {
  const fmt = animationAsset.value?.metadata?.format || selectedFormat.value
  return fmt === 'webp' ? 'Animated WebP' : 'GIF'
})

const resultMetaText = computed(() => {
  const asset = animationAsset.value
  if (!asset) return ''
  const parts: string[] = []
  if (asset.width && asset.height) parts.push(`${asset.width}×${asset.height}`)
  const count = asset.metadata?.frame_count
  if (count) parts.push(`${count} frames`)
  const durs = asset.metadata?.durations_ms
  if (Array.isArray(durs) && durs.length > 0) parts.push(`${durs[0]} ms`)
  const loop = asset.metadata?.loop || props.generation.agentic_plan?.loop
  if (loop) parts.push(String(loop))
  return parts.join(' · ')
})

// --- Drag and drop, disable toggle & actions --------------------------------
const draggedId = ref<number | null>(null)
const dragOverId = ref<number | null>(null)
let justDragged = false

function moveFrame(fromIndex: number, toIndex: number) {
  if (fromIndex < 0 || toIndex < 0 || fromIndex >= orderedIds.value.length || toIndex >= orderedIds.value.length) return
  if (fromIndex === toIndex) return
  const next = [...orderedIds.value]
  const [moved] = next.splice(fromIndex, 1)
  next.splice(toIndex, 0, moved)
  orderedIds.value = next
}

function toggleDisabled(id: number) {
  const next = new Set(disabledIds.value)
  if (next.has(id)) next.delete(id)
  else if (enabledIds.value.length > 2) next.add(id)
  disabledIds.value = next
}

function resetFrames() {
  orderedIds.value = [...originalIds.value]
  disabledIds.value = new Set()
}

function onDragStart(event: DragEvent, id: number) {
  if (!canReorder.value || (event.target as HTMLElement | null)?.closest('button')) {
    event.preventDefault()
    return
  }
  draggedId.value = id
  if (event.dataTransfer) {
    event.dataTransfer.effectAllowed = 'move'
    event.dataTransfer.setData('text/plain', String(id))
  }
}

function onDragOver(event: DragEvent, targetId: number) {
  if (!canReorder.value || draggedId.value === null) return
  if (event.dataTransfer) event.dataTransfer.dropEffect = 'move'
  dragOverId.value = targetId
}

function onDrop(event: DragEvent, targetId: number) {
  const raw = event.dataTransfer?.getData('text/plain')
  const sourceId = draggedId.value ?? (raw ? Number(raw) : null)
  dragOverId.value = null
  draggedId.value = null
  if (sourceId === null || !Number.isFinite(sourceId) || sourceId === targetId) return
  moveFrame(orderedIds.value.indexOf(sourceId), orderedIds.value.indexOf(targetId))
  justDragged = true
  setTimeout(() => {
    justDragged = false
  }, 150)
}

function onDragEnd() {
  draggedId.value = null
  dragOverId.value = null
}

function openViewer(asset: Asset) {
  if (justDragged) return
  imageViewerStore.openViewer({
    asset,
    generation: props.generation,
    url: asset.image_url || asset.thumbnail_url,
  })
}

function buildPayloadFrames(parsedMs: number | null) {
  return orderedIds.value.map((id) => ({
    id,
    duration_ms: parsedMs,
    disabled: disabledIds.value.has(id),
  }))
}

async function syncPendingBeforeFrameEdit() {
  if (!hasPendingChanges.value) return
  const parsed = parseFrameMs(frameMsInput.value)
  const validMs = typeof parsed === 'number' ? parsed : null
  await generateStore.updateAnimationFrames(props.generation, buildPayloadFrames(validMs), {
    frame_ms: validMs,
    silent: true,
  })
}

async function handleCreateAnimation() {
  if (enabledIds.value.length < 2 || isBusy.value || isBuilding.value) return
  const parsed = parseFrameMs(frameMsInput.value)
  if (parsed === 'invalid') {
    toastStore.error('Frame duration must be between 20 and 10000 ms.')
    return
  }
  isBuilding.value = true
  try {
    await generateStore.updateAnimationFrames(props.generation, buildPayloadFrames(parsed), {
      output: selectedFormat.value,
      frame_ms: parsed,
    })
  } finally {
    isBuilding.value = false
  }
}
</script>

<template>
  <div class="space-y-3" data-testid="animation-set-section">
    <!-- Row 1: Draggable Animation Frame Set -->
    <div :class="['grid gap-3', frameGridClass]" data-testid="animation-frame-list">
      <div
        v-for="(asset, index) in frames"
        :key="asset.id"
        :draggable="canReorder"
        :tabindex="canReorder ? 0 : undefined"
        :data-frame-id="asset.id"
        :data-disabled="disabledIds.has(asset.id) ? 'true' : 'false'"
        data-testid="animation-frame-item"
        :class="[
          'min-w-0 space-y-1.5 rounded-xl transition-all duration-150 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40',
          canReorder ? 'cursor-grab active:cursor-grabbing' : '',
          draggedId === asset.id ? 'opacity-45 scale-[0.98]' : '',
          dragOverId === asset.id && draggedId !== asset.id ? 'ring-2 ring-sky-500 ring-offset-2 dark:ring-offset-slate-900' : '',
        ]"
        @dragstart="onDragStart($event, asset.id)"
        @dragover.prevent="onDragOver($event, asset.id)"
        @dragleave="dragOverId === asset.id && (dragOverId = null)"
        @drop.prevent="onDrop($event, asset.id)"
        @dragend="onDragEnd"
        @keydown.alt.arrow-left.prevent="canReorder && moveFrame(index, index - 1)"
        @keydown.alt.arrow-right.prevent="canReorder && moveFrame(index, index + 1)"
      >
        <div
          :class="[
            'group relative flex select-none items-center justify-center overflow-hidden rounded-xl border border-slate-300/60 transition-all duration-200 hover:border-sky-500/50 hover:shadow-md dark:border-white/10',
            isTransparent ? 'bg-checkerboard' : 'bg-slate-950',
          ]"
          :style="{ aspectRatio: frameAspect }"
          :title="canReorder ? 'Drag to reorder or click to zoom (Alt+Left/Right)' : 'Click to enlarge'"
          @click="openViewer(asset)"
        >
          <img
            :src="asset.image_url || asset.thumbnail_url"
            :alt="asset.metadata?.item_title || asset.prompt"
            :class="[
              'pointer-events-none h-full w-full object-contain motion-safe:transition-all motion-safe:duration-300',
              disabledIds.has(asset.id) ? 'opacity-35 grayscale' : 'motion-safe:group-hover:scale-[1.02]',
            ]"
            loading="lazy"
            @load="emit('image-loaded')"
          />

          <!-- Top-left sequence / skipped badge -->
          <span
            :class="[
              'pointer-events-none absolute left-2 top-2 inline-flex items-center gap-0.5 rounded-lg border px-1.5 py-0.5 font-mono text-2xs font-semibold backdrop-blur-md',
              disabledIds.has(asset.id)
                ? 'border-white/10 bg-slate-900/85 text-slate-400'
                : 'border-white/15 bg-slate-900/80 text-white',
            ]"
          >
            <GripVertical v-if="canReorder" class="size-3 text-slate-300" aria-hidden="true" />
            <span>{{ disabledIds.has(asset.id) ? 'Skipped' : `#${activeIndexMap.get(asset.id)}` }}</span>
          </span>

          <!-- Hover actions -->
          <div
            class="pointer-events-none absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-slate-950/25 opacity-0 transition-opacity duration-200 group-hover:opacity-100"
          >
            <div class="pointer-events-auto absolute right-2 top-2">
              <span
                class="inline-flex cursor-pointer items-center gap-1 rounded-lg border border-white/10 bg-slate-900/80 px-2 py-1 text-2xs font-medium text-white backdrop-blur-md hover:bg-slate-800"
              >
                <ZoomIn class="size-3.5 text-sky-400" aria-hidden="true" />
                Zoom
              </span>
            </div>
            <div class="pointer-events-auto absolute bottom-2 left-0 right-0 flex items-center justify-center px-1.5" @click.stop>
              <GenerationActions :asset="asset" :generation="generation" variant="overlay" @delete="emit('delete')" />
            </div>
          </div>
        </div>

        <div class="flex items-center justify-between gap-1 px-1">
          <span
            :class="[
              'truncate text-xs font-semibold',
              disabledIds.has(asset.id)
                ? 'text-slate-400 line-through dark:text-slate-500'
                : 'text-slate-800 dark:text-slate-200',
            ]"
            :title="asset.metadata?.item_title || `Frame ${index + 1}`"
          >
            {{ asset.metadata?.item_title || `Frame ${index + 1}` }}
          </span>
          <AnimationFrameActions
            :generation="generation"
            :asset="asset"
            :disabled="disabledIds.has(asset.id)"
            :enabled-count="enabledIds.length"
            :before-action="syncPendingBeforeFrameEdit"
            @toggle-disabled="toggleDisabled(asset.id)"
          />
        </div>
      </div>

      <!-- Live generating slot while frames are being produced -->
      <div v-if="isGeneratingFrames" class="min-w-0 space-y-1.5">
        <div
          class="relative flex flex-col items-center justify-center rounded-xl border border-dashed border-sky-400/70 bg-slate-100/80 p-4 text-center dark:border-sky-500/40 dark:bg-slate-900/60"
          :style="{ aspectRatio: frameAspect }"
        >
          <Spinner size="md" class="text-sky-500" />
          <span class="mt-2 line-clamp-2 px-2 text-2xs font-semibold text-slate-700 dark:text-slate-200">
            {{ liveSlotLabel }}
          </span>
          <span class="mt-1 font-mono text-2xs text-slate-500 dark:text-slate-400">{{ formatDuration(elapsedSeconds) }}</span>
        </div>
      </div>
    </div>

    <!-- Frame order, disable status, speed & assembly toolbar -->
    <div
      v-if="frames.length >= 2 || canReset"
      class="flex flex-wrap items-center justify-between gap-2 rounded-xl bg-slate-100 px-3 py-2 dark:bg-slate-800/60"
      data-testid="animation-set-controls"
    >
      <div class="flex flex-wrap items-center gap-2 text-xs text-slate-600 dark:text-slate-300">
        <GripVertical class="size-3.5 text-slate-400" aria-hidden="true" />
        <span>Drag to reorder · {{ enabledIds.length }}/{{ frames.length }} active</span>
        <Badge v-if="hasPendingChanges" variant="sky" size="xs">Order modified</Badge>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <Button
          variant="ghost"
          size="xs"
          data-testid="reset-frame-order"
          :disabled="!canReset || isBusy || isBuilding"
          @click="resetFrames"
        >
          <template #icon><RotateCcw class="size-3.5" aria-hidden="true" /></template>
          Reset
        </Button>
        <div class="flex items-center gap-1.5" title="Frame duration in milliseconds (animation speed)">
          <Gauge class="size-3.5 text-slate-400" aria-hidden="true" />
          <Input
            v-model="frameMsInput"
            type="number"
            size="sm"
            class="w-24"
            min="20"
            max="10000"
            step="10"
            :placeholder="`${defaultFrameMs} ms`"
            aria-label="Animation frame duration in milliseconds"
            data-testid="animation-speed-ms"
            :disabled="isBusy || isBuilding"
          />
          <span class="font-mono text-2xs text-slate-500 dark:text-slate-400" data-testid="animation-speed-fps">
            {{ fpsLabel }}
          </span>
        </div>
        <Select
          :model-value="selectedFormat"
          :options="formatOptions"
          size="sm"
          class="w-24"
          aria-label="Animation output format"
          data-testid="create-animation-format"
          :disabled="isBusy || isBuilding"
          @update:model-value="selectedFormat = $event as 'gif' | 'webp'"
        />
        <Button
          variant="primary"
          size="sm"
          data-testid="create-animation-btn"
          :disabled="enabledIds.length < 2 || isBusy"
          :loading="isBuilding"
          @click="handleCreateAnimation"
        >
          <template #icon><Film class="size-4" aria-hidden="true" /></template>
          Create {{ selectedFormat === 'webp' ? 'WebP' : 'GIF' }}
        </Button>
      </div>
    </div>

    <!-- Row 2: Dedicated Result GIF / Animated WebP Row -->
    <div
      v-if="animationAsset || isAssembling || isBuilding"
      class="space-y-2 border-t border-slate-200/80 pt-3 dark:border-white/10"
      data-testid="animation-result-row"
    >
      <div class="flex flex-wrap items-center gap-2">
        <Film class="size-4 text-sky-600 dark:text-sky-400" aria-hidden="true" />
        <h3 class="text-xs font-semibold text-slate-900 dark:text-white">Result animation</h3>
        <Badge variant="sky" size="xs">{{ resultFormatLabel }}</Badge>
        <span v-if="resultMetaText" class="font-mono text-2xs text-slate-500 dark:text-slate-400">{{ resultMetaText }}</span>
      </div>

      <div v-if="animationAsset" class="flex flex-col gap-3 sm:flex-row sm:items-start">
        <div
          :class="[
            'group relative inline-flex max-h-72 max-w-xs cursor-zoom-in select-none items-center justify-center overflow-hidden rounded-xl border border-slate-300/60 transition-all hover:border-sky-500/50 hover:shadow-md dark:border-white/10',
            isTransparent ? 'bg-checkerboard' : 'bg-slate-950',
          ]"
          title="Click to enlarge animation"
          @click="openViewer(animationAsset)"
        >
          <img
            :src="animationAsset.image_url"
            :alt="animationAsset.metadata?.item_title || generation.prompt"
            class="max-h-72 w-auto max-w-full object-contain"
            @load="emit('image-loaded')"
          />
          <div
            v-if="isBuilding || isAssembling"
            class="absolute inset-0 flex items-center justify-center bg-slate-950/60 backdrop-blur-sm"
          >
            <Spinner size="md" class="text-sky-400" />
          </div>
        </div>

        <div class="flex flex-col gap-2">
          <GenerationActions
            :asset="animationAsset"
            :generation="generation"
            variant="inline"
            @delete="emit('delete')"
          />
        </div>
      </div>

      <div
        v-else
        class="flex items-center gap-2.5 rounded-xl border border-dashed border-sky-300 bg-slate-100/80 px-4 py-3 text-xs font-medium text-slate-700 dark:border-sky-700/50 dark:bg-slate-900/60 dark:text-slate-200"
      >
        <Spinner size="sm" class="text-sky-500" />
        <span>{{ liveSlotLabel }}</span>
      </div>
    </div>
  </div>
</template>
