<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import type { Asset, Generation } from '@/types'
import { useImageViewerStore } from '@/stores/imageViewer'
import { useGenerateStore } from '@/stores/generate'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import Spinner from '@/components/ui/Spinner.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import GenerationActions from './GenerationActions.vue'
import { describeUsage, formatDuration, formatTimestamp, formatUsage } from '@/utils/format'

interface Props {
  generation: Generation
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'image-loaded'): void
}>()

const imageViewerStore = useImageViewerStore()
const generateStore = useGenerateStore()
const authStore = useAuthStore()
const toastStore = useToastStore()

const isRetrying = ref(false)
const isCancelling = ref(false)
const isDeleteOpen = ref(false)
const isDeleting = ref(false)
const isPromptExpanded = ref(false)

const assets = computed(() => props.generation.assets || [])
const hasAssets = computed(() => assets.value.length > 0)
const isFailed = computed(() => props.generation.status === 'failed' || props.generation.status === 'cancelled')
const isPending = computed(() => !isFailed.value && !hasAssets.value && props.generation.status !== 'succeeded')
const isLongPrompt = computed(() => (props.generation.prompt || '').length > 220)

// --- Elapsed timer for running jobs ---------------------------------------
const now = ref(Date.now())
let ticker: ReturnType<typeof setInterval> | null = null

function stopTicker() {
  if (ticker) {
    clearInterval(ticker)
    ticker = null
  }
}

watch(
  isPending,
  (pending) => {
    stopTicker()
    if (pending) {
      now.value = Date.now()
      ticker = setInterval(() => {
        now.value = Date.now()
      }, 1000)
    }
  },
  { immediate: true }
)

onUnmounted(stopTicker)

const elapsedSeconds = computed(() => {
  const started = Date.parse(props.generation.created_at)
  if (Number.isNaN(started)) return 0
  return Math.max(0, (now.value - started) / 1000)
})

const statusLabel = computed(() => {
  const s = props.generation.status
  if (s === 'queued' || s === 'pending') return 'Waiting in queue'
  return 'Generating'
})

// --- Layout helpers --------------------------------------------------------
const expectedCount = computed(() => Math.min(Math.max(Number(props.generation.n_images) || 1, 1), 4))

const placeholderAspect = computed(() => {
  const ratio = props.generation.aspect_ratio || '1:1'
  const [w, h] = ratio.split(':').map(Number)
  if (!w || !h) return '1 / 1'
  return `${w} / ${h}`
})

const gridClass = computed(() => {
  const count = isPending.value ? expectedCount.value : assets.value.length
  if (count <= 1) return 'grid-cols-1'
  if (count === 2) return 'grid-cols-1 sm:grid-cols-2'
  return 'grid-cols-2 lg:grid-cols-3'
})

const dimensions = computed(() => {
  const first = assets.value[0]
  if (!first) return null
  const w = first.width || first.metadata?.width
  const h = first.height || first.metadata?.height
  return w && h ? `${w}×${h}` : null
})

const usageText = computed(() =>
  authStore.uiSettings.show_token_usage ? formatUsage(props.generation.usage) : null
)

const displayModelName = computed(() => {
  const raw = props.generation.model_name
  if (!raw) return ''
  const found = generateStore.activeModels.find(
    (m) => m.model_identifier === raw || m.name === raw
  )
  return found?.name || raw
})

// --- Actions ----------------------------------------------------------------
async function handleRetry() {
  isRetrying.value = true
  try {
    await generateStore.retryGeneration(props.generation)
  } finally {
    isRetrying.value = false
  }
}

async function handleCancel() {
  isCancelling.value = true
  try {
    await generateStore.cancelGeneration(props.generation.id)
  } finally {
    isCancelling.value = false
  }
}

async function handleDelete() {
  isDeleting.value = true
  try {
    await generateStore.deleteGeneration(props.generation.id)
    isDeleteOpen.value = false
  } finally {
    isDeleting.value = false
  }
}

function handleEditPrompt() {
  generateStore.remixGeneration(props.generation)
}

async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(props.generation.prompt)
    toastStore.success('Prompt copied to clipboard!')
  } catch (_e) {
    toastStore.error('Copy failed.')
  }
}

function isVideoAsset(asset: Asset): boolean {
  return !!asset.mime?.startsWith('video/')
}

function handleImageClick(asset: Asset) {
  imageViewerStore.openViewer({
    asset,
    generation: props.generation,
    url: asset.image_url || asset.thumbnail_url,
  })
}
</script>

<template>
  <article
    class="group/card space-y-3 rounded-2xl border border-slate-200/80 bg-white/75 p-3.5 sm:p-4 shadow-sm transition-all dark:border-white/10 dark:bg-slate-900/75"
    :data-generation-id="generation.id"
    :data-status="generation.status"
  >
    <!-- Header: prompt + quick actions -->
    <header class="flex items-start gap-3">
      <div class="min-w-0 flex-1 space-y-1">
        <p
          :class="[
            'text-xs sm:text-sm font-medium leading-relaxed text-slate-900 dark:text-white break-words',
            isLongPrompt && !isPromptExpanded ? 'line-clamp-3' : '',
          ]"
        >
          {{ generation.prompt }}
        </p>
        <button
          v-if="isLongPrompt"
          type="button"
          @click="isPromptExpanded = !isPromptExpanded"
          class="cursor-pointer text-[11px] font-medium text-sky-600 hover:underline dark:text-sky-400"
        >
          {{ isPromptExpanded ? 'Show less' : 'Show full prompt' }}
        </button>
        <p v-if="generation.negative_prompt" class="text-[11px] text-slate-500 dark:text-slate-400">
          <span class="font-semibold text-rose-500">Negative:</span> {{ generation.negative_prompt }}
        </p>
      </div>

      <div class="flex shrink-0 items-center gap-0.5 opacity-60 transition-opacity group-hover/card:opacity-100 focus-within:opacity-100">
        <button
          type="button"
          @click="handleEditPrompt"
          class="cursor-pointer rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-sky-600 dark:hover:bg-white/10 dark:hover:text-sky-300"
          title="Load prompt & settings into the composer"
          aria-label="Reuse prompt"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
          </svg>
        </button>
        <button
          type="button"
          @click="copyPrompt"
          class="cursor-pointer rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-slate-100 hover:text-sky-600 dark:hover:bg-white/10 dark:hover:text-sky-300"
          title="Copy prompt"
          aria-label="Copy prompt"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
        </button>
        <button
          type="button"
          @click="isDeleteOpen = true"
          class="cursor-pointer rounded-lg p-1.5 text-slate-400 transition-colors hover:bg-rose-500/10 hover:text-rose-500"
          title="Delete generation"
          aria-label="Delete generation"
        >
          <svg class="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.75" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
          </svg>
        </button>
      </div>
    </header>

    <!-- Pending: aspect-correct placeholders with live timer -->
    <div v-if="isPending" class="space-y-2.5">
      <div :class="['grid gap-2', gridClass]">
        <div
          v-for="n in expectedCount"
          :key="n"
          class="relative mx-auto w-full max-h-[420px] overflow-hidden rounded-xl border border-dashed border-slate-300 bg-slate-100/70 dark:border-white/10 dark:bg-slate-950/50"
          :style="{ aspectRatio: placeholderAspect, maxWidth: expectedCount === 1 ? '420px' : undefined }"
        >
          <div class="absolute inset-0 animate-pulse bg-gradient-to-br from-sky-500/5 via-transparent to-indigo-500/10" />
          <div v-if="n === 1" class="absolute inset-0 flex flex-col items-center justify-center gap-2 text-center">
            <Spinner size="lg" class="text-sky-500" />
            <span class="text-xs font-semibold text-slate-600 dark:text-slate-300">{{ statusLabel }}…</span>
            <span class="font-mono text-[11px] text-slate-400" data-testid="generation-elapsed">{{ formatDuration(elapsedSeconds) }}</span>
          </div>
        </div>
      </div>
      <div class="flex items-center justify-center gap-2">
        <button
          type="button"
          @click="handleCancel"
          :disabled="isCancelling"
          class="inline-flex cursor-pointer items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-500 shadow-sm transition-colors hover:bg-rose-500/10 hover:text-rose-600 disabled:opacity-50 dark:border-white/10 dark:text-slate-400 dark:hover:text-rose-400"
          title="Stop this generation"
        >
          <svg class="h-3.5 w-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
          </svg>
          {{ isCancelling ? 'Cancelling…' : 'Cancel' }}
        </button>
      </div>
    </div>

    <!-- Failed or cancelled -->
    <div
      v-else-if="isFailed"
      :class="[
        'flex flex-col justify-between gap-3 rounded-xl border p-3.5 text-xs sm:flex-row sm:items-center',
        generation.status === 'cancelled'
          ? 'border-slate-200 bg-slate-50 text-slate-600 dark:border-white/10 dark:bg-slate-950/40 dark:text-slate-300'
          : 'border-rose-200 bg-rose-50 text-rose-700 dark:border-rose-800/60 dark:bg-rose-950/40 dark:text-rose-300',
      ]"
    >
      <div class="min-w-0 flex-1 space-y-1">
        <div class="font-semibold">
          {{ generation.status === 'cancelled' ? 'Generation cancelled' : 'Generation failed' }}
        </div>
        <p class="break-words opacity-90">
          {{ generation.error_message || (generation.status === 'cancelled' ? 'The job was stopped before it finished.' : 'Unknown error during generation.') }}
        </p>
      </div>
      <div class="flex shrink-0 items-center gap-2 self-start sm:self-center">
        <button
          type="button"
          @click="isDeleteOpen = true"
          class="inline-flex cursor-pointer items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition hover:bg-black/5 dark:hover:bg-white/10"
        >
          Remove
        </button>
        <button
          type="button"
          @click="handleRetry"
          :disabled="isRetrying"
          class="inline-flex cursor-pointer items-center gap-1.5 rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-medium text-white shadow-sm transition hover:bg-sky-700 disabled:opacity-50"
          title="Queue this job again with the same settings"
        >
          <span :class="{ 'animate-spin': isRetrying }">↻</span>
          {{ isRetrying ? 'Starting…' : 'Retry' }}
        </button>
      </div>
    </div>

    <!-- Results -->
    <div v-else-if="hasAssets" :class="['grid gap-3', gridClass]">
      <div v-for="asset in assets" :key="asset.id" class="min-w-0 space-y-2">
        <div
          @click="handleImageClick(asset)"
          :class="[
            'group relative flex cursor-zoom-in select-none items-center justify-center overflow-hidden rounded-xl border border-slate-300/60 bg-slate-950 transition-all duration-200 hover:border-sky-500/50 hover:shadow-lg dark:border-white/10',
            assets.length === 1 ? 'max-h-[460px] sm:max-h-[520px]' : '',
          ]"
          title="Click to enlarge (fullscreen & zoom)"
        >
          <!-- Click is stopped so the video controls don't open the viewer -->
          <video
            v-if="isVideoAsset(asset)"
            :src="asset.image_url"
            :poster="asset.thumbnail_url"
            :class="[
              assets.length === 1 ? 'max-h-[460px] sm:max-h-[520px] w-auto max-w-full object-contain' : 'h-full w-full object-cover aspect-square',
            ]"
            controls
            playsinline
            preload="metadata"
            @click.stop
            @loadedmetadata="emit('image-loaded')"
          />
          <img
            v-else
            :src="asset.image_url || asset.thumbnail_url"
            :alt="asset.prompt"
            :class="[
              'transition-transform duration-300 group-hover:scale-[1.01]',
              assets.length === 1 ? 'max-h-[460px] sm:max-h-[520px] w-auto max-w-full object-contain' : 'h-full w-full object-cover aspect-square',
            ]"
            loading="lazy"
            @load="emit('image-loaded')"
          />
          <!-- Video badge (top-left); its "Open" overlay sits top-right so it doesn't cover the native controls -->
          <span
            v-if="isVideoAsset(asset)"
            class="pointer-events-none absolute left-2 top-2 inline-flex items-center gap-1 rounded-lg border border-white/30 bg-black/70 px-1.5 py-0.5 text-[10px] font-semibold text-white"
            data-testid="video-badge"
          >
            <svg class="h-3 w-3" fill="currentColor" viewBox="0 0 24 24" aria-hidden="true">
              <path d="M8 5v14l11-7z" />
            </svg>
            Video
          </span>
          <div
            v-if="isVideoAsset(asset)"
            class="pointer-events-none absolute right-2 top-2 opacity-0 transition-opacity duration-200 group-hover:opacity-100"
          >
            <span class="pointer-events-auto inline-flex items-center gap-1 rounded-lg border border-white/10 bg-slate-900/80 px-2 py-1 text-[11px] font-medium text-white backdrop-blur-md">
              Open
            </span>
          </div>
          <div v-else class="pointer-events-none absolute inset-0 flex items-end justify-end bg-gradient-to-t from-slate-950/70 via-transparent to-transparent p-2.5 opacity-0 transition-opacity duration-200 group-hover:opacity-100">
            <span class="inline-flex items-center gap-1 rounded-lg border border-white/10 bg-slate-900/80 px-2 py-1 text-[11px] font-medium text-white backdrop-blur-md">
              <svg class="h-3.5 w-3.5 text-sky-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
              </svg>
              Zoom
            </span>
          </div>
        </div>

        <GenerationActions
          :asset="asset"
          :generation="generation"
          :compact="assets.length > 1"
          @delete="isDeleteOpen = true"
        />
      </div>
    </div>

    <!-- Meta footer -->
    <footer class="flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-slate-500 dark:text-slate-400">
      <span v-if="displayModelName" class="font-medium text-sky-700 dark:text-sky-300" :title="generation.model_name">{{ displayModelName }}</span>
      <span v-if="generation.aspect_ratio" class="rounded bg-slate-100 px-1.5 py-0.5 font-mono dark:bg-slate-800">{{ generation.aspect_ratio }}</span>
      <span v-if="dimensions" class="rounded bg-slate-100 px-1.5 py-0.5 font-mono dark:bg-slate-800">{{ dimensions }}</span>
      <span v-if="generation.profile_name && generation.profile_name !== 'default'" title="Profile">· {{ generation.profile_name }}</span>
      <span class="flex-1" />
      <span
        v-if="usageText"
        class="inline-flex items-center gap-1 rounded-full bg-amber-500/10 px-2 py-0.5 font-medium text-amber-700 dark:text-amber-300"
        :title="describeUsage(generation.usage)"
        data-testid="generation-usage"
      >
        <svg class="h-3 w-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        {{ usageText }}
      </span>
      <span v-if="generation.duration_seconds" title="Generation time">{{ formatDuration(generation.duration_seconds) }}</span>
      <span :title="generation.created_at">{{ formatTimestamp(generation.created_at) }}</span>
    </footer>

    <ConfirmDialog
      :open="isDeleteOpen"
      :title="hasAssets ? 'Delete Generation' : 'Remove Generation'"
      :message="hasAssets ? 'Do you really want to delete this generation and its generated images?' : 'Do you want to remove this generation from the session?'"
      confirmText="Delete"
      variant="danger"
      :loading="isDeleting"
      @update:open="isDeleteOpen = $event"
      @confirm="handleDelete"
    />
  </article>
</template>
