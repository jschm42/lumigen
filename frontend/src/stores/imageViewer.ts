import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Asset, Generation } from '@/types'

export interface OpenViewerOptions {
  asset?: Asset | null
  generation?: Generation | null
  url?: string
  showMetadata?: boolean
}

export const useImageViewerStore = defineStore('imageViewer', () => {
  const isOpen = ref(false)
  const activeAsset = ref<Asset | null>(null)
  const activeGeneration = ref<Generation | null>(null)
  const imageUrl = ref<string>('')
  const showMetadata = ref<boolean>(false)
  const naturalWidth = ref<number | null>(null)
  const naturalHeight = ref<number | null>(null)

  function openViewer(options: OpenViewerOptions) {
    activeAsset.value = options.asset || null
    activeGeneration.value = options.generation || null
    imageUrl.value =
      options.url ||
      options.asset?.image_url ||
      options.asset?.thumbnail_url ||
      ''
    showMetadata.value = options.showMetadata ?? false
    naturalWidth.value = options.asset?.metadata?.width ?? null
    naturalHeight.value = options.asset?.metadata?.height ?? null
    isOpen.value = true
  }

  function closeViewer() {
    isOpen.value = false
    // Delay clearing asset to avoid visual flickers during fade-out
    setTimeout(() => {
      if (!isOpen.value) {
        activeAsset.value = null
        activeGeneration.value = null
        imageUrl.value = ''
        naturalWidth.value = null
        naturalHeight.value = null
      }
    }, 200)
  }

  function toggleMetadata() {
    showMetadata.value = !showMetadata.value
  }

  function setDimensions(width: number, height: number) {
    naturalWidth.value = width
    naturalHeight.value = height
  }

  return {
    isOpen,
    activeAsset,
    activeGeneration,
    imageUrl,
    showMetadata,
    naturalWidth,
    naturalHeight,
    openViewer,
    closeViewer,
    toggleMetadata,
    setDimensions,
  }
})
