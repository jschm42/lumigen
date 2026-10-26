<script setup lang="ts">
import { ref } from 'vue'
import { useGenerateStore } from '@/stores/generate'
import { useGalleryStore } from '@/stores/gallery'
import { useToastStore } from '@/stores/toast'
import { downloadFile } from '@/utils/download'
import type { Asset, Generation } from '@/types'
import UpscaleModal from './UpscaleModal.vue'

interface Props {
  asset: Asset
  generation?: Generation
  compact?: boolean
  variant?: 'inline' | 'overlay'
}

const props = withDefaults(defineProps<Props>(), {
  compact: false,
  variant: 'inline',
})

const emit = defineEmits<{
  (e: 'delete'): void
}>()

const generateStore = useGenerateStore()
const galleryStore = useGalleryStore()
const toastStore = useToastStore()

const isDownloading = ref(false)
const isUpscaleModalOpen = ref(false)

function handleRemix() {
  if (props.generation) {
    generateStore.remixGeneration(props.generation)
  } else {
    generateStore.prompt = props.asset.prompt
    if (props.asset.negative_prompt) {
      generateStore.negativePrompt = props.asset.negative_prompt
      generateStore.showNegativePrompt = true
    }
    if (props.asset.aspect_ratio) generateStore.aspectRatio = props.asset.aspect_ratio
    toastStore.info('Prompt applied!')
  }
}

async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(props.asset.prompt)
    toastStore.success('Prompt copied to clipboard!')
  } catch (_e) {
    toastStore.error('Copy failed.')
  }
}

async function handleDownload() {
  const url = props.asset.download_url || props.asset.image_url
  if (!url) return
  isDownloading.value = true
  try {
    await downloadFile(url)
  } finally {
    isDownloading.value = false
  }
}

function openDetail() {
  galleryStore.openDetailModal(props.asset)
}

function handleUpscaleSubmitted(jobId: number) {
  generateStore.pollJob(jobId)
}
</script>

<template>
  <!-- Overlay Mode (Floating inside image hover overlay) -->
  <div
    v-if="variant === 'overlay'"
    class="flex items-center gap-0.5 rounded-xl bg-slate-950/85 backdrop-blur-md px-1.5 py-1 border border-white/15 shadow-xl text-white"
    @click.stop
  >
    <!-- Remix -->
    <button
      type="button"
      @click="handleRemix"
      class="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/20 transition-colors"
      title="Load prompt & settings into editor"
      aria-label="Remix"
    >
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      </svg>
    </button>

    <!-- Upscale -->
    <button
      v-if="!asset.mime?.startsWith('video/') && asset.mime !== 'image/svg+xml'"
      type="button"
      @click="isUpscaleModalOpen = true"
      class="p-1.5 rounded-lg text-amber-300 hover:text-amber-200 hover:bg-white/20 transition-colors"
      title="Upscale image"
      aria-label="Upscale"
    >
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
      </svg>
    </button>

    <!-- Use as Input Image -->
    <button
      type="button"
      @click="generateStore.attachAssetAsImage(asset)"
      class="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/20 transition-colors"
      title="Load as input image in prompt composer"
      aria-label="As Input"
    >
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
    </button>

    <!-- Copy Prompt -->
    <button
      type="button"
      @click="copyPrompt"
      class="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/20 transition-colors"
      title="Copy prompt"
      aria-label="Copy Prompt"
    >
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
      </svg>
    </button>

    <!-- Download button -->
    <button
      type="button"
      @click="handleDownload"
      :disabled="isDownloading"
      class="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/20 transition-colors disabled:opacity-50"
      title="Download image"
      aria-label="Download"
    >
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
    </button>

    <!-- Details View -->
    <button
      type="button"
      @click="openDetail"
      class="p-1.5 rounded-lg text-slate-300 hover:text-white hover:bg-white/20 transition-colors"
      title="Show metadata & details"
      aria-label="Details"
    >
      <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    </button>

    <!-- Upscale Modal -->
    <UpscaleModal
      :open="isUpscaleModalOpen"
      :asset="asset"
      @update:open="isUpscaleModalOpen = $event"
      @submitted="handleUpscaleSubmitted"
    />
  </div>

  <!-- Inline Mode (Normal bar under single image) -->
  <div v-else :class="['flex flex-wrap items-center text-xs', compact ? 'gap-1' : 'gap-1.5']">
    <!-- Remix / Re-use -->
    <button
      type="button"
      @click="handleRemix"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1.5"
      title="Load prompt & settings into editor"
    >
      <svg class="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
      </svg>
      <span v-if="!compact">Remix</span>
    </button>

    <!-- Upscale -->
    <button
      v-if="!asset.mime?.startsWith('video/') && asset.mime !== 'image/svg+xml'"
      type="button"
      @click="isUpscaleModalOpen = true"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1.5"
      title="Upscale image"
    >
      <svg class="w-3.5 h-3.5 text-amber-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
      </svg>
      <span v-if="!compact">Upscale</span>
    </button>

    <!-- Use as Input Image -->
    <button
      type="button"
      @click="generateStore.attachAssetAsImage(asset)"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1.5"
      title="Load as input image in prompt composer"
    >
      <svg class="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
      </svg>
      <span v-if="!compact">As Input</span>
    </button>

    <!-- Copy Prompt -->
    <button
      type="button"
      @click="copyPrompt"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1.5"
      title="Copy prompt"
    >
      <svg class="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
      </svg>
      <span v-if="!compact">Copy</span>
    </button>

    <!-- Download button -->
    <button
      type="button"
      @click="handleDownload"
      :disabled="isDownloading"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1.5 disabled:opacity-50"
      title="Download image"
    >
      <svg class="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
      </svg>
      <span v-if="!compact">{{ isDownloading ? 'Downloading...' : 'Download' }}</span>
    </button>

    <!-- Details View -->
    <button
      type="button"
      @click="openDetail"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1.5 ml-auto"
      title="Show metadata & details"
    >
      <svg class="w-3.5 h-3.5 text-slate-500 dark:text-slate-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
      <span v-if="!compact">Details</span>
    </button>

    <!-- Delete Generation -->
    <button
      v-if="generation && !compact"
      type="button"
      @click="emit('delete')"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:text-rose-400 dark:hover:bg-rose-950/30 transition-colors flex items-center gap-1.5"
      title="Delete generation from session"
    >
      <svg class="w-3.5 h-3.5 text-rose-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
      </svg>
      <span v-if="!compact">Delete</span>
    </button>

    <!-- Upscale Modal -->
    <UpscaleModal
      :open="isUpscaleModalOpen"
      :asset="asset"
      @update:open="isUpscaleModalOpen = $event"
      @submitted="handleUpscaleSubmitted"
    />
  </div>
</template>
