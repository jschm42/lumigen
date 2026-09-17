<script setup lang="ts">
import { ref, computed } from 'vue'
import type { Asset, Generation } from '@/types'
import { useImageViewerStore } from '@/stores/imageViewer'
import { useGenerateStore } from '@/stores/generate'
import Spinner from '@/components/ui/Spinner.vue'
import Badge from '@/components/ui/Badge.vue'
import GenerationActions from './GenerationActions.vue'

interface Props {
  generation: Generation
}

const props = defineProps<Props>()
const imageViewerStore = useImageViewerStore()
const generateStore = useGenerateStore()
const isRetrying = ref(false)

async function handleRetry() {
  isRetrying.value = true
  try {
    await generateStore.retryGeneration(props.generation)
  } finally {
    isRetrying.value = false
  }
}

const isPendingOrProcessing = computed(() => {
  const s = props.generation.status
  if (s === 'failed' || s === 'cancelled') return false
  if (props.generation.assets && props.generation.assets.length > 0) return false
  return true
})

const statusMessage = computed(() => {
  const s = props.generation.status
  if (s === 'queued') return 'In queue...'
  if (s === 'running') {
    if (props.generation.progress && props.generation.progress > 0 && props.generation.progress < 100) {
      return `Generating image... (${props.generation.progress}%)`
    }
    return 'Generating image...'
  }
  return 'Generating image...'
})

function handleImageClick(asset: Asset) {
  imageViewerStore.openViewer({
    asset,
    generation: props.generation,
    url: asset.image_url || asset.thumbnail_url,
  })
}
</script>

<template>
  <div class="space-y-3 p-4 sm:p-5 rounded-2xl border border-slate-200/80 bg-white/75 dark:border-white/10 dark:bg-slate-900/75 shadow-sm transition-all">
    <!-- Header: Prompt text & Model info -->
    <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-2 pb-2 border-b border-slate-200/60 dark:border-white/10">
      <div class="space-y-1 min-w-0 flex-1">
        <p class="text-xs sm:text-sm font-medium text-slate-900 dark:text-white leading-relaxed break-words">
          {{ generation.prompt }}
        </p>
        <p v-if="generation.negative_prompt" class="text-[11px] text-slate-500 dark:text-slate-400">
          <span class="font-semibold text-rose-500">Negative:</span> {{ generation.negative_prompt }}
        </p>
      </div>

      <!-- Badges -->
      <div class="flex flex-wrap items-center gap-1.5 shrink-0">
        <Badge v-if="generation.model_name" variant="sky" size="xs">
          {{ generation.model_name }}
        </Badge>
        <Badge v-if="generation.aspect_ratio" variant="slate" size="xs">
          {{ generation.aspect_ratio }}
        </Badge>
      </div>
    </div>

    <!-- Processing State (shown until generation finishes with assets or fails) -->
    <div
      v-if="isPendingOrProcessing"
      class="py-12 flex flex-col items-center justify-center gap-3 bg-slate-100/60 dark:bg-slate-950/40 rounded-xl border border-dashed border-slate-300 dark:border-white/10"
    >
      <Spinner size="lg" class="text-sky-500" />
      <span class="text-xs font-semibold text-slate-600 dark:text-slate-300 animate-pulse">
        {{ statusMessage }}
      </span>
      <div
        v-if="generation.progress && generation.progress > 0 && generation.progress < 100"
        class="w-44 h-1.5 bg-slate-200 dark:bg-slate-800 rounded-full overflow-hidden"
      >
        <div
          class="h-full bg-sky-500 rounded-full transition-all duration-300"
          :style="{ width: `${generation.progress}%` }"
        />
      </div>
    </div>

    <!-- Failed or Cancelled State with Retry Button -->
    <div
      v-else-if="generation.status === 'failed' || generation.status === 'cancelled'"
      class="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/60 text-xs text-rose-700 dark:text-rose-300 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
    >
      <div class="space-y-1 min-w-0 flex-1">
        <div class="font-semibold flex items-center gap-1.5">
          <span>{{ generation.status === 'cancelled' ? 'Generation cancelled' : 'Generation failed' }}</span>
        </div>
        <p class="break-words text-rose-600 dark:text-rose-400">
          {{ generation.error_message || (generation.status === 'cancelled' ? 'The job was cancelled manually.' : 'Unknown error during generation.') }}
        </p>
      </div>

      <button
        type="button"
        @click="handleRetry"
        :disabled="isRetrying"
        class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-rose-600 hover:bg-rose-700 text-white font-medium text-xs shadow-sm transition disabled:opacity-50 shrink-0 self-start sm:self-center"
        title="Retry this job"
      >
        <span :class="{ 'animate-spin': isRetrying }">🔄</span>
        <span>{{ isRetrying ? 'Starting...' : 'Retry' }}</span>
      </button>
    </div>

    <!-- Succeeded State (Image Results) -->
    <div v-else-if="generation.assets && generation.assets.length > 0" class="space-y-3">
      <div
        v-for="asset in generation.assets"
        :key="asset.id"
        class="space-y-3"
      >
        <!-- Result image container with restricted preview size and click-to-open viewer -->
        <div
          @click="handleImageClick(asset)"
          class="relative group rounded-xl overflow-hidden bg-slate-950 flex items-center justify-center border border-slate-300/60 dark:border-white/10 max-h-[380px] sm:max-h-[420px] cursor-pointer select-none transition-all duration-200 hover:border-sky-500/50 hover:shadow-lg"
          title="Click to enlarge (Fullscreen & Zoom)"
        >
          <img
            :src="asset.image_url || asset.thumbnail_url"
            :alt="asset.prompt"
            class="max-h-[380px] sm:max-h-[420px] w-auto max-w-full object-contain transition-transform duration-300 group-hover:scale-[1.01]"
            loading="lazy"
          />

          <!-- Hover Hint Overlay -->
          <div
            class="absolute inset-0 bg-gradient-to-t from-slate-950/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-end justify-between p-3 pointer-events-none"
          >
            <span class="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900/80 text-white text-xs font-medium backdrop-blur-md shadow-md border border-white/10">
              <svg class="w-3.5 h-3.5 text-sky-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
              </svg>
              <span>Fullscreen & Zoom</span>
            </span>

            <span v-if="asset.aspect_ratio" class="px-2 py-0.5 rounded bg-black/60 text-slate-300 text-[11px] font-mono border border-white/5">
              {{ asset.aspect_ratio }}
            </span>
          </div>
        </div>

        <!-- Action bar -->
        <GenerationActions :asset="asset" :generation="generation" />
      </div>
    </div>
  </div>
</template>
