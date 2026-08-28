<script setup lang="ts">
import { ref } from 'vue'
import { generationApi } from '@/api/generation'
import { useGenerateStore } from '@/stores/generate'
import { useGalleryStore } from '@/stores/gallery'
import { useToastStore } from '@/stores/toast'
import type { Asset, Generation } from '@/types'
import ExpandCanvasModal from './ExpandCanvasModal.vue'

interface Props {
  asset: Asset
  generation?: Generation
}

const props = defineProps<Props>()

const generateStore = useGenerateStore()
const galleryStore = useGalleryStore()
const toastStore = useToastStore()

const isUpscaling = ref(false)
const isExpandModalOpen = ref(false)

async function handleUpscale() {
  isUpscaling.value = true
  try {
    const res = await generationApi.upscale(props.asset.id)
    toastStore.success('Upscaling gestartet!')
    generateStore.pollJob(res.job_id)
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Upscaling fehlgeschlagen.')
  } finally {
    isUpscaling.value = false
  }
}

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
    toastStore.info('Prompt übernommen!')
  }
}

async function copyPrompt() {
  try {
    await navigator.clipboard.writeText(props.asset.prompt)
    toastStore.success('Prompt in die Zwischenablage kopiert!')
  } catch (_e) {
    toastStore.error('Kopieren fehlgeschlagen.')
  }
}

function openDetail() {
  galleryStore.openDetailModal(props.asset)
}

function handleExpandSubmitted(jobId: number) {
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
      title="Prompt & Parameter in Editor laden"
    >
      <span>🔁</span> Remix
    </button>

    <!-- Upscale -->
    <button
      type="button"
      @click="handleUpscale"
      :disabled="isUpscaling"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1 disabled:opacity-50"
      title="Bild hochskalieren"
    >
      <span>✨</span> {{ isUpscaling ? 'Skaliere...' : 'Upscale' }}
    </button>

    <!-- Expand / Outpaint -->
    <button
      type="button"
      @click="isExpandModalOpen = true"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1"
      title="Bild erweitern"
    >
      <span>📐</span> Erweitern
    </button>

    <!-- Copy Prompt -->
    <button
      type="button"
      @click="copyPrompt"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1"
      title="Prompt kopieren"
    >
      <span>📋</span> Kopieren
    </button>

    <!-- Download link -->
    <a
      :href="asset.download_url || asset.image_url"
      download
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1"
      title="Bild herunterladen"
    >
      <span>⬇️</span> Download
    </a>

    <!-- Details View -->
    <button
      type="button"
      @click="openDetail"
      class="px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 hover:bg-slate-200 dark:hover:bg-slate-700 transition-colors flex items-center gap-1 ml-auto"
      title="Metadaten & Details anzeigen"
    >
      <span>ℹ️</span> Details
    </button>

    <!-- Outpaint / Expand Modal -->
    <ExpandCanvasModal
      :open="isExpandModalOpen"
      :asset="asset"
      @update:open="isExpandModalOpen = $event"
      @submitted="handleExpandSubmitted"
    />
  </div>
</template>
