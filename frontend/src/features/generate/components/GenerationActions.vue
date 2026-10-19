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
}

const props = defineProps<Props>()
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
  <div class="flex flex-wrap items-center gap-1.5 text-xs">
    <!-- Remix / Re-use -->
    <button
      type="button"
      @click="handleRemix"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1"
      title="Load prompt & settings into editor"
    >
      <span>🔁</span> Remix
    </button>

    <!-- Upscale -->
    <button
      type="button"
      @click="isUpscaleModalOpen = true"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1"
      title="Upscale image"
    >
      <span>✨</span> Upscale
    </button>

    <!-- Use as Input Image -->
    <button
      type="button"
      @click="generateStore.attachAssetAsImage(asset)"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1"
      title="Load as input image in prompt composer"
    >
      <span>🖼️</span> As Input Image
    </button>

    <!-- Copy Prompt -->
    <button
      type="button"
      @click="copyPrompt"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1"
      title="Copy prompt"
    >
      <span>📋</span> Copy
    </button>

    <!-- Download button -->
    <button
      type="button"
      @click="handleDownload"
      :disabled="isDownloading"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1 disabled:opacity-50"
      title="Download image"
    >
      <span>⬇️</span> {{ isDownloading ? 'Downloading...' : 'Download' }}
    </button>

    <!-- Details View -->
    <button
      type="button"
      @click="openDetail"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1 ml-auto"
      title="Show metadata & details"
    >
      <span>ℹ️</span> Details
    </button>

    <!-- Delete Generation -->
    <button
      v-if="generation"
      type="button"
      @click="emit('delete')"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-500 dark:text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:text-rose-400 dark:hover:bg-rose-950/30 transition-colors flex items-center gap-1"
      title="Delete generation from session"
    >
      <span>🗑️</span> Delete
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
