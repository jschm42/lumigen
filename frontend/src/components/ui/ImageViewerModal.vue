<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useImageViewerStore } from '@/stores/imageViewer'
import { useGenerateStore } from '@/stores/generate'
import { useToastStore } from '@/stores/toast'
import { downloadFile } from '@/utils/download'

const router = useRouter()
const imageViewerStore = useImageViewerStore()
const generateStore = useGenerateStore()
const toastStore = useToastStore()

// Transform / Zoom / Pan state
const scale = ref<number>(1)
const translateX = ref<number>(0)
const translateY = ref<number>(0)
const isDragging = ref<boolean>(false)
const hasMovedWhileDragging = ref<boolean>(false)
const dragStartX = ref<number>(0)
const dragStartY = ref<number>(0)
const initialTranslateX = ref<number>(0)
const initialTranslateY = ref<number>(0)

const imgRef = ref<HTMLImageElement | null>(null)
const isCopied = ref<boolean>(false)
const isDownloading = ref<boolean>(false)

// Reset transformations whenever a new image opens
watch(
  () => imageViewerStore.isOpen,
  (open) => {
    if (open) {
      resetZoom()
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
  }
)

function resetZoom() {
  scale.value = 1
  translateX.value = 0
  translateY.value = 0
  isDragging.value = false
  hasMovedWhileDragging.value = false
}

function zoomIn() {
  scale.value = Math.min(5, +(scale.value + 0.25).toFixed(2))
}

function zoomOut() {
  scale.value = Math.max(0.25, +(scale.value - 0.25).toFixed(2))
  if (scale.value === 1) {
    translateX.value = 0
    translateY.value = 0
  }
}

function setZoom100() {
  if (scale.value === 1) {
    scale.value = 2
  } else {
    scale.value = 1
    translateX.value = 0
    translateY.value = 0
  }
}

function handleWheel(e: WheelEvent) {
  e.preventDefault()
  const delta = e.deltaY < 0 ? 0.2 : -0.2
  const newScale = Math.min(5, Math.max(0.25, +(scale.value + delta).toFixed(2)))
  scale.value = newScale
  if (newScale === 1) {
    translateX.value = 0
    translateY.value = 0
  }
}

function handleMouseDown(e: MouseEvent) {
  // Only start drag on left mouse button
  if (e.button !== 0) return
  isDragging.value = true
  hasMovedWhileDragging.value = false
  dragStartX.value = e.clientX
  dragStartY.value = e.clientY
  initialTranslateX.value = translateX.value
  initialTranslateY.value = translateY.value
}

function handleMouseMove(e: MouseEvent) {
  if (!isDragging.value) return
  const dx = e.clientX - dragStartX.value
  const dy = e.clientY - dragStartY.value
  if (Math.abs(dx) > 3 || Math.abs(dy) > 3) {
    hasMovedWhileDragging.value = true
  }
  translateX.value = initialTranslateX.value + dx
  translateY.value = initialTranslateY.value + dy
}

function handleMouseUp() {
  isDragging.value = false
}

function handleDblClick() {
  if (scale.value === 1) {
    scale.value = 2
  } else {
    resetZoom()
  }
}

function handleBackdropClick(e: MouseEvent) {
  // Only close if we clicked directly on backdrop/canvas container and didn't drag
  if (hasMovedWhileDragging.value) return
  const target = e.target as HTMLElement
  if (target.classList.contains('viewer-backdrop')) {
    imageViewerStore.closeViewer()
  }
}

function handleImageLoad(e: Event) {
  const target = e.target as HTMLImageElement
  if (target && target.naturalWidth && target.naturalHeight) {
    imageViewerStore.setDimensions(target.naturalWidth, target.naturalHeight)
  }
}

async function copyPrompt(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    isCopied.value = true
    toastStore.success('Prompt copied to clipboard!')
    setTimeout(() => {
      isCopied.value = false
    }, 2000)
  } catch (_e) {
    toastStore.error('Copy failed.')
  }
}

function handleRemix() {
  const asset = imageViewerStore.activeAsset
  const gen = imageViewerStore.activeGeneration

  if (gen) {
    generateStore.remixGeneration(gen)
  } else if (asset) {
    generateStore.prompt = asset.prompt
    if (asset.negative_prompt) {
      generateStore.negativePrompt = asset.negative_prompt
      generateStore.showNegativePrompt = true
    }
    if (asset.aspect_ratio) generateStore.aspectRatio = asset.aspect_ratio
    if (asset.seed !== undefined && asset.seed !== null) {
      generateStore.seed = String(asset.seed)
    }
  }

  imageViewerStore.closeViewer()
  router.push('/')
  toastStore.info('Prompt & settings loaded into Studio!')
}

async function handleDownload() {
  const url = imageViewerStore.imageUrl
  if (!url) return
  isDownloading.value = true
  try {
    await downloadFile(url)
  } finally {
    isDownloading.value = false
  }
}

// Fullscreen toggle
const isFullscreen = ref<boolean>(false)
function toggleFullscreen() {
  if (!document.fullscreenElement) {
    document.documentElement.requestFullscreen().then(() => {
      isFullscreen.value = true
    }).catch(() => {})
  } else {
    document.exitFullscreen().then(() => {
      isFullscreen.value = false
    }).catch(() => {})
  }
}

// Formatted metadata helpers
const promptText = computed(() => {
  return imageViewerStore.activeAsset?.prompt || imageViewerStore.activeGeneration?.prompt || ''
})

const negativePromptText = computed(() => {
  return (
    imageViewerStore.activeAsset?.negative_prompt ||
    imageViewerStore.activeGeneration?.negative_prompt ||
    ''
  )
})

const modelName = computed(() => {
  return (
    imageViewerStore.activeAsset?.model ||
    imageViewerStore.activeGeneration?.model_name ||
    'Unknown'
  )
})

const providerName = computed(() => {
  return (
    imageViewerStore.activeAsset?.provider ||
    imageViewerStore.activeGeneration?.provider ||
    ''
  )
})

const aspectRatio = computed(() => {
  return (
    imageViewerStore.activeAsset?.aspect_ratio ||
    imageViewerStore.activeGeneration?.aspect_ratio ||
    '1:1'
  )
})

const resolution = computed(() => {
  return (
    imageViewerStore.activeAsset?.resolution ||
    imageViewerStore.activeGeneration?.resolution ||
    null
  )
})

const imageFormat = computed(() => {
  const url = imageViewerStore.imageUrl || ''
  if (url.includes('.webp')) return 'WEBP'
  if (url.includes('.png')) return 'PNG'
  if (url.includes('.jpg') || url.includes('.jpeg')) return 'JPEG'
  return 'PNG / Raster'
})

const seedValue = computed(() => {
  const seed = imageViewerStore.activeAsset?.seed ?? imageViewerStore.activeGeneration?.seed
  return seed !== undefined && seed !== null ? String(seed) : null
})

// Keyboard shortcuts
function handleKeydown(e: KeyboardEvent) {
  if (!imageViewerStore.isOpen) return

  if (e.key === 'Escape') {
    imageViewerStore.closeViewer()
  } else if (e.key === '+' || e.key === '=') {
    zoomIn()
  } else if (e.key === '-') {
    zoomOut()
  } else if (e.key === '0') {
    resetZoom()
  } else if (e.key === 'i' || e.key === 'I') {
    imageViewerStore.toggleMetadata()
  }
}

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="imageViewerStore.isOpen"
        class="fixed inset-0 z-50 flex bg-slate-950/95 backdrop-blur-xl select-none overflow-hidden"
        @click="handleBackdropClick"
      >
        <!-- Floating Top Toolbar -->
        <header
          class="absolute top-4 inset-x-0 z-30 flex items-center justify-between px-4 sm:px-6 pointer-events-none"
        >
          <!-- Left: Title / Status -->
          <div class="pointer-events-auto flex items-center gap-2">
            <div
              class="px-3 py-1.5 rounded-full bg-slate-900/80 border border-white/10 text-white/90 text-xs font-semibold backdrop-blur-md shadow-lg flex items-center gap-2"
            >
              <span class="w-2 h-2 rounded-full bg-sky-400 animate-pulse"></span>
              <span>Image Viewer</span>
              <span v-if="imageViewerStore.naturalWidth && imageViewerStore.naturalHeight" class="text-slate-400 font-mono text-[11px]">
                {{ imageViewerStore.naturalWidth }} × {{ imageViewerStore.naturalHeight }}
              </span>
            </div>
          </div>

          <!-- Center: Zoom & Pan Toolbar -->
          <div
            class="pointer-events-auto flex items-center gap-1 sm:gap-1.5 p-1.5 rounded-2xl bg-slate-900/85 border border-white/10 shadow-2xl backdrop-blur-md text-white"
          >
            <!-- Zoom Out -->
            <button
              type="button"
              @click="zoomOut"
              :disabled="scale <= 0.25"
              class="p-2 rounded-xl text-slate-300 hover:text-white hover:bg-white/10 disabled:opacity-40 disabled:hover:bg-transparent transition-colors"
              title="Zoom out (-)"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20 12H4" />
              </svg>
            </button>

            <!-- Zoom Scale Display / Reset to 100% -->
            <button
              type="button"
              @click="setZoom100"
              class="px-2.5 py-1 text-xs font-mono font-semibold rounded-lg hover:bg-white/10 transition-colors min-w-[56px] text-center"
              title="Toggle 100% / Fit"
            >
              {{ Math.round(scale * 100) }}%
            </button>

            <!-- Zoom In -->
            <button
              type="button"
              @click="zoomIn"
              :disabled="scale >= 5"
              class="p-2 rounded-xl text-slate-300 hover:text-white hover:bg-white/10 disabled:opacity-40 disabled:hover:bg-transparent transition-colors"
              title="Zoom in (+)"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
              </svg>
            </button>

            <!-- Reset / Fit Button -->
            <button
              type="button"
              @click="resetZoom"
              class="p-2 rounded-xl text-slate-300 hover:text-white hover:bg-white/10 transition-colors"
              title="Reset zoom (0)"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 8V4m0 0h4M4 4l5 5m11-1V4m0 0h-4m4 0l-5 5M4 16v4m0 0h4m-4 0l5-5m11 5l-5-5m5 5v-4m0 4h-4" />
              </svg>
            </button>

            <div class="h-4 w-px bg-white/20 mx-1"></div>

            <!-- Fullscreen toggle -->
            <button
              type="button"
              @click="toggleFullscreen"
              class="p-2 rounded-xl text-slate-300 hover:text-white hover:bg-white/10 transition-colors hidden sm:inline-flex"
              title="Toggle fullscreen"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4h6M4 4v6M20 4h-6M20 4v6M4 20h6M4 20v-6M20 20h-6M20 20v-6" />
              </svg>
            </button>

            <!-- Metadata Toggle Button -->
            <button
              type="button"
              @click="imageViewerStore.toggleMetadata"
              :class="[
                'px-2.5 py-1.5 rounded-xl text-xs font-medium flex items-center gap-1.5 transition-all',
                imageViewerStore.showMetadata
                  ? 'bg-sky-500 text-white shadow-md shadow-sky-500/20'
                  : 'text-slate-300 hover:text-white hover:bg-white/10',
              ]"
              title="Toggle metadata (i)"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <span>Info</span>
            </button>
          </div>

          <!-- Right: Actions & Close -->
          <div class="pointer-events-auto flex items-center gap-2">
            <!-- Remix button -->
            <button
              v-if="imageViewerStore.activeAsset || imageViewerStore.activeGeneration"
              type="button"
              @click="handleRemix"
              class="hidden md:flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-slate-900/80 hover:bg-slate-800 border border-white/10 text-white text-xs font-semibold backdrop-blur-md shadow-lg transition-colors"
              title="Load in Studio"
            >
              <span>🔁</span> Remix
            </button>

            <!-- Download button -->
            <button
              type="button"
              @click="handleDownload"
              :disabled="isDownloading"
              class="p-2 sm:px-3 sm:py-1.5 rounded-full bg-slate-900/80 hover:bg-slate-800 border border-white/10 text-white text-xs font-semibold backdrop-blur-md shadow-lg transition-colors flex items-center gap-1.5 disabled:opacity-50"
              title="Download image"
            >
              <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              <span class="hidden sm:inline">{{ isDownloading ? 'Downloading...' : 'Download' }}</span>
            </button>

            <!-- Close Button -->
            <button
              type="button"
              @click="imageViewerStore.closeViewer"
              class="p-2 rounded-full bg-slate-900/80 hover:bg-rose-600/90 border border-white/10 text-slate-300 hover:text-white backdrop-blur-md shadow-lg transition-all"
              title="Close (Esc)"
            >
              <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </header>

        <!-- Main Zoom & Pan Stage -->
        <main
          class="viewer-backdrop flex-1 relative flex items-center justify-center overflow-hidden cursor-default"
          :class="[isDragging ? 'cursor-grabbing' : scale > 1 ? 'cursor-grab' : 'cursor-default']"
          @wheel="handleWheel"
          @mousedown="handleMouseDown"
          @mousemove="handleMouseMove"
          @mouseup="handleMouseUp"
          @mouseleave="handleMouseUp"
          @dblclick="handleDblClick"
        >
          <div
            class="transform-gpu transition-transform select-none max-w-full max-h-full flex items-center justify-center pointer-events-none"
            :style="{
              transform: `translate3d(${translateX}px, ${translateY}px, 0) scale(${scale})`,
              transition: isDragging ? 'none' : 'transform 0.15s cubic-bezier(0.2, 0, 0, 1)',
            }"
          >
            <img
              ref="imgRef"
              :src="imageViewerStore.imageUrl"
              :alt="promptText"
              class="max-h-[85vh] max-w-[85vw] object-contain rounded-lg shadow-2xl pointer-events-auto"
              draggable="false"
              @load="handleImageLoad"
            />
          </div>

          <!-- Bottom floating tips badge -->
          <div
            class="absolute bottom-4 left-1/2 -translate-x-1/2 pointer-events-none px-3 py-1 rounded-full bg-slate-900/60 border border-white/5 backdrop-blur-md text-[11px] text-slate-400 hidden sm:flex items-center gap-3 shadow-lg"
          >
            <span>Scroll: Zoom</span>
            <span class="w-1 h-1 rounded-full bg-slate-600"></span>
            <span>Drag: Pan</span>
            <span class="w-1 h-1 rounded-full bg-slate-600"></span>
            <span>Double click: 100% / Fit</span>
            <span class="w-1 h-1 rounded-full bg-slate-600"></span>
            <span>'i': Metadata</span>
          </div>
        </main>

        <!-- Slide-Over Metadata Panel -->
        <Transition
          enter-active-class="transition duration-300 ease-out"
          enter-from-class="translate-x-full opacity-0"
          enter-to-class="translate-x-0 opacity-100"
          leave-active-class="transition duration-200 ease-in"
          leave-from-class="translate-x-0 opacity-100"
          leave-to-class="translate-x-full opacity-0"
        >
          <aside
            v-if="imageViewerStore.showMetadata"
            class="relative z-40 w-80 sm:w-96 bg-slate-900/90 border-l border-white/10 backdrop-blur-2xl flex flex-col h-full shadow-2xl text-slate-200 shrink-0 overflow-hidden"
            @click.stop
          >
            <!-- Panel Header -->
            <div class="px-5 py-4 border-b border-white/10 flex items-center justify-between shrink-0">
              <div class="flex items-center gap-2">
                <span class="text-sky-400">ℹ️</span>
                <h3 class="font-semibold text-sm text-white tracking-wide">
                  Metadata
                </h3>
              </div>
              <button
                type="button"
                @click="imageViewerStore.showMetadata = false"
                class="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-white/10 transition-colors"
                title="Close panel"
              >
                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <!-- Panel Scrollable Content -->
            <div class="flex-1 overflow-y-auto p-5 space-y-4 text-xs">
              <!-- Dimensions / Size card -->
              <div class="p-3.5 rounded-xl bg-slate-950/60 border border-white/5 space-y-2">
                <div class="text-[11px] uppercase tracking-wider font-semibold text-slate-400 flex items-center justify-between">
                  <span>Size & Resolution</span>
                  <span v-if="resolution" class="px-1.5 py-0.5 rounded bg-sky-500/20 text-sky-300 font-mono text-[10px]">
                    {{ resolution }}
                  </span>
                </div>
                <div class="grid grid-cols-2 gap-2 text-xs">
                  <div>
                    <span class="text-slate-500 text-[10px] block">Dimensions</span>
                    <span class="font-mono font-semibold text-white">
                      {{ imageViewerStore.naturalWidth ? `${imageViewerStore.naturalWidth} × ${imageViewerStore.naturalHeight} px` : 'Calculating...' }}
                    </span>
                  </div>
                  <div>
                    <span class="text-slate-500 text-[10px] block">Aspect Ratio</span>
                    <span class="font-mono font-semibold text-white">
                      {{ aspectRatio }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Model & Provider card -->
              <div class="p-3.5 rounded-xl bg-slate-950/60 border border-white/5 space-y-2">
                <div class="text-[11px] uppercase tracking-wider font-semibold text-slate-400">
                  Model & Engine
                </div>
                <div class="space-y-1.5">
                  <div class="flex items-center justify-between">
                    <span class="text-slate-500 text-[11px]">Model:</span>
                    <span class="font-semibold text-sky-400 text-right truncate max-w-[180px]" :title="modelName">
                      {{ modelName }}
                    </span>
                  </div>
                  <div v-if="providerName" class="flex items-center justify-between">
                    <span class="text-slate-500 text-[11px]">Provider:</span>
                    <span class="font-semibold text-white uppercase text-[11px]">
                      {{ providerName }}
                    </span>
                  </div>
                  <div class="flex items-center justify-between">
                    <span class="text-slate-500 text-[11px]">Format / MIME:</span>
                    <span class="font-mono text-slate-300 text-[11px]">
                      {{ imageFormat }}
                    </span>
                  </div>
                  <div v-if="seedValue" class="flex items-center justify-between">
                    <span class="text-slate-500 text-[11px]">Seed:</span>
                    <span class="font-mono text-slate-300 text-[11px]">
                      {{ seedValue }}
                    </span>
                  </div>
                </div>
              </div>

              <!-- Prompt section -->
              <div class="p-3.5 rounded-xl bg-slate-950/60 border border-white/5 space-y-2">
                <div class="flex items-center justify-between text-[11px] uppercase tracking-wider font-semibold text-slate-400">
                  <span>Prompt</span>
                  <button
                    type="button"
                    @click="copyPrompt(promptText)"
                    class="text-sky-400 hover:text-sky-300 font-semibold normal-case text-xs transition-colors flex items-center gap-1"
                  >
                    <span>{{ isCopied ? '✓ Copied' : '📋 Copy' }}</span>
                  </button>
                </div>
                <p class="text-slate-200 leading-relaxed font-normal select-text break-words">
                  {{ promptText || 'No prompt specified.' }}
                </p>
              </div>

              <!-- Negative Prompt section (if exists) -->
              <div
                v-if="negativePromptText"
                class="p-3.5 rounded-xl bg-rose-950/20 border border-rose-500/20 space-y-1.5"
              >
                <div class="text-[11px] uppercase tracking-wider font-semibold text-rose-400">
                  Negative Prompt
                </div>
                <p class="text-slate-300 leading-relaxed select-text break-words">
                  {{ negativePromptText }}
                </p>
              </div>

              <!-- Bottom Actions -->
              <div class="pt-2 space-y-2">
                <button
                  type="button"
                  @click="handleRemix"
                  class="w-full py-2.5 px-4 rounded-xl bg-sky-600 hover:bg-sky-500 font-semibold text-white text-xs shadow-lg shadow-sky-600/30 transition-all flex items-center justify-center gap-2"
                >
                  <span>🔁</span> Remix in Studio
                </button>

                <button
                  type="button"
                  @click="handleDownload"
                  :disabled="isDownloading"
                  class="w-full py-2 px-4 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-semibold transition-colors flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  <span>⬇️</span> {{ isDownloading ? 'Downloading...' : 'Download Image' }}
                </button>
              </div>
            </div>
          </aside>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
