<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

import type { Asset } from '@/types'
import { useGalleryStore } from '@/stores/gallery'
import { useGenerateStore } from '@/stores/generate'
import { useToastStore } from '@/stores/toast'
import { useImageViewerStore } from '@/stores/imageViewer'
import { downloadFile } from '@/utils/download'
import Modal from '@/components/ui/Modal.vue'
import Button from '@/components/ui/Button.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import UpscaleModal from '@/features/generate/components/UpscaleModal.vue'

const router = useRouter()
const galleryStore = useGalleryStore()
const generateStore = useGenerateStore()
const toastStore = useToastStore()
const imageViewerStore = useImageViewerStore()

const stackItems = computed<Asset[]>(() => {
  if (!galleryStore.activeAsset?.stack_id) return []
  if (galleryStore.activeAsset.stack_items && galleryStore.activeAsset.stack_items.length > 0) {
    return galleryStore.activeAsset.stack_items
  }
  const cover = galleryStore.assets.find((a) => a.stack_id === galleryStore.activeAsset?.stack_id)
  return cover?.stack_items || []
})

function switchStackAsset(asset: Asset) {
  const items = stackItems.value
  galleryStore.activeAsset = { ...asset, stack_items: items }
}

async function handleSetStackCover() {
  if (!galleryStore.activeAsset) return
  await galleryStore.setStackCover(galleryStore.activeAsset.id)
}

async function handleRemoveFromStack() {
  if (!galleryStore.activeAsset) return
  await galleryStore.removeAssetFromStack(galleryStore.activeAsset.id)
}

async function handleDissolveStack() {
  if (!galleryStore.activeAsset?.stack_id) return
  await galleryStore.unstackById(galleryStore.activeAsset.stack_id)
}

const isDeleteConfirmOpen = ref(false)
const isUpscaleModalOpen = ref(false)
const isAddCatOpen = ref(false)
const newCatName = ref('')
const isCreatingCat = ref(false)
const isDownloading = ref(false)

function handleUpscaleSubmitted(jobId: number) {
  generateStore.pollJob(jobId)
  galleryStore.closeDetailModal()
  router.push('/')
}

const assignedCategories = computed(() => {
  if (!galleryStore.activeAsset) return []
  const catIds = galleryStore.activeAsset.category_ids || []
  return galleryStore.categories.filter((c) => catIds.includes(c.id))
})

const availableCategoriesToAdd = computed(() => {
  if (!galleryStore.activeAsset) return []
  const catIds = galleryStore.activeAsset.category_ids || []
  return galleryStore.categories.filter((c) => !catIds.includes(c.id))
})

function removeCategory(catId: number) {
  if (!galleryStore.activeAsset) return
  const current = (galleryStore.activeAsset.category_ids || []).filter((id) => id !== catId)
  galleryStore.updateAssetCategories(galleryStore.activeAsset.id, current)
}

function addCategory(catId: number) {
  if (!galleryStore.activeAsset) return
  const current = [...(galleryStore.activeAsset.category_ids || []), catId]
  galleryStore.updateAssetCategories(galleryStore.activeAsset.id, current)
  isAddCatOpen.value = false
}

async function createAndAddCategory() {
  const name = newCatName.value.trim()
  if (!name || !galleryStore.activeAsset) return
  isCreatingCat.value = true
  try {
    const created = await galleryStore.createCategory(name)
    if (created) {
      addCategory(created.id)
    }
    newCatName.value = ''
  } catch (_e) {
    // handled in store
  } finally {
    isCreatingCat.value = false
  }
}

function openImageViewer() {
  if (!galleryStore.activeAsset) return
  imageViewerStore.openViewer({
    asset: galleryStore.activeAsset,
    url: galleryStore.activeAsset.image_url || galleryStore.activeAsset.thumbnail_url,
    showMetadata: true,
  })
}

async function copyText(text: string) {
  try {
    await navigator.clipboard.writeText(text)
    toastStore.success('Copied to clipboard!')
  } catch (_e) {
    toastStore.error('Copy failed.')
  }
}

function handleRemix() {
  if (!galleryStore.activeAsset) return
  generateStore.prompt = galleryStore.activeAsset.prompt
  if (galleryStore.activeAsset.negative_prompt) {
    generateStore.negativePrompt = galleryStore.activeAsset.negative_prompt
    generateStore.showNegativePrompt = true
  }
  if (galleryStore.activeAsset.aspect_ratio) {
    generateStore.aspectRatio = galleryStore.activeAsset.aspect_ratio
  }
  if (galleryStore.activeAsset.seed !== undefined && galleryStore.activeAsset.seed !== null) {
    generateStore.seed = String(galleryStore.activeAsset.seed)
  }
  galleryStore.closeDetailModal()
  router.push('/')
  toastStore.info('Prompt & settings loaded into Studio!')
}

function handleUseAsInputImage() {
  if (!galleryStore.activeAsset) return
  generateStore.attachAssetAsImage(galleryStore.activeAsset)
  galleryStore.closeDetailModal()
  router.push('/')
}

async function handleDownload() {
  const url = galleryStore.activeAsset?.download_url || galleryStore.activeAsset?.image_url
  if (!url) return
  isDownloading.value = true
  try {
    await downloadFile(url)
  } finally {
    isDownloading.value = false
  }
}

async function handleDelete() {
  if (!galleryStore.activeAsset) return
  await galleryStore.deleteAsset(galleryStore.activeAsset.id)
  isDeleteConfirmOpen.value = false
}

function handleRateAsset(star: number) {
  if (!galleryStore.activeAsset) return
  const current = galleryStore.activeAsset.rating || 0
  const next = current === star ? 0 : star
  galleryStore.rateAsset(galleryStore.activeAsset, next)
}
</script>

<template>
  <Modal
    :open="galleryStore.isDetailModalOpen"
    size="2xl"
    @update:open="galleryStore.closeDetailModal"
  >
    <template #header>
      <div class="flex items-center justify-between w-full pr-6 text-xs">
        <h3 class="text-sm font-bold text-slate-900 dark:text-white truncate">
          Asset #{{ galleryStore.activeAsset?.id }} – Details
        </h3>
        <!-- Rating stars -->
        <div v-if="galleryStore.activeAsset" class="flex items-center gap-1">
          <button
            v-for="star in [1, 2, 3, 4, 5]"
            :key="star"
            type="button"
            @click="handleRateAsset(star)"
            class="text-base text-amber-400 hover:scale-110 transition-transform"
            :title="galleryStore.activeAsset.rating === star ? 'Clear rating' : `${star} stars`"
          >
            {{ (galleryStore.activeAsset.rating || 0) >= star ? '★' : '☆' }}
          </button>
        </div>
      </div>
    </template>

    <div v-if="galleryStore.activeAsset" class="grid grid-cols-1 lg:grid-cols-12 gap-6 text-xs">
      <!-- Left: High-Res Image Display & Stack Filmstrip -->
      <div class="lg:col-span-7 flex flex-col gap-3">
        <div
          @click="openImageViewer"
          class="group relative flex flex-col items-center justify-center bg-slate-950 rounded-2xl p-2 border border-slate-200/60 dark:border-white/10 overflow-hidden min-h-[320px] cursor-pointer hover:border-sky-500/50 transition-colors"
          title="Open in fullscreen & zoom viewer"
        >
          <img
            :src="galleryStore.activeAsset.image_url || galleryStore.activeAsset.thumbnail_url"
            :alt="galleryStore.activeAsset.prompt"
            class="max-h-[52vh] w-auto object-contain rounded-xl shadow-2xl transition-transform duration-200 group-hover:scale-[1.01]"
          />
          <div class="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900/80 backdrop-blur-md px-2.5 py-1 rounded-lg text-white text-xs flex items-center gap-1.5 border border-white/10 shadow-lg pointer-events-none">
            <svg class="w-3.5 h-3.5 text-sky-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
            </svg>
            <span>Fullscreen & Zoom</span>
          </div>
        </div>

        <!-- Stack Filmstrip Panel (if asset belongs to a stack) -->
        <div
          v-if="galleryStore.activeAsset.stack_id"
          class="p-3 rounded-2xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200/80 dark:border-white/10 space-y-2.5"
        >
          <div class="flex items-center justify-between text-xs">
            <div class="flex items-center gap-1.5 font-semibold text-slate-800 dark:text-slate-200">
              <span>🥞</span>
              <span>Photo Stack ({{ stackItems.length || galleryStore.activeAsset.stack_count || 1 }} images)</span>
            </div>
            <div class="flex items-center gap-1.5">
              <button
                v-if="galleryStore.activeAsset.stack_order !== 0"
                type="button"
                @click="handleSetStackCover"
                class="px-2 py-1 rounded-lg border border-sky-400/40 bg-sky-500/10 hover:bg-sky-500/20 text-sky-600 dark:text-sky-300 font-medium text-[11px] transition-colors"
                title="Make this image the cover of the stack"
              >
                ★ Set as Cover
              </button>
              <button
                type="button"
                @click="handleRemoveFromStack"
                class="px-2 py-1 rounded-lg border border-slate-300 dark:border-white/10 bg-white/60 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-slate-600 dark:text-slate-300 text-[11px] transition-colors"
                title="Remove this image from the stack"
              >
                Remove
              </button>
              <button
                type="button"
                @click="handleDissolveStack"
                class="px-2 py-1 rounded-lg border border-rose-400/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-500 dark:text-rose-400 text-[11px] transition-colors"
                title="Dissolve this stack into individual images"
              >
                Dissolve
              </button>
            </div>
          </div>

          <!-- Thumbnails Strip -->
          <div class="flex items-center gap-2 overflow-x-auto py-1 pr-1">
            <div
              v-for="(item, idx) in stackItems"
              :key="item.id"
              @click="switchStackAsset(item)"
              :class="[
                'relative flex-shrink-0 w-14 h-14 rounded-xl overflow-hidden cursor-pointer transition-all border-2',
                item.id === galleryStore.activeAsset.id
                  ? 'border-sky-500 ring-2 ring-sky-500/40 scale-105 shadow-md'
                  : 'border-slate-300 dark:border-white/15 opacity-70 hover:opacity-100 hover:scale-100',
              ]"
              :title="`Image #${item.id} (Stack item ${idx + 1}/${stackItems.length})`"
            >
              <img
                :src="item.thumbnail_url || item.image_url"
                :alt="item.prompt"
                class="w-full h-full object-cover"
                loading="lazy"
              />
              <span
                v-if="item.stack_order === 0"
                class="absolute top-0.5 left-0.5 px-1 rounded bg-amber-500/90 text-black text-[9px] font-bold leading-tight"
                title="Cover photo"
              >
                ★
              </span>
            </div>
          </div>
        </div>
      </div>

      <!-- Right: Metadata Sidecar Inspector -->
      <div class="lg:col-span-5 space-y-4 overflow-y-auto max-h-[65vh] pr-1">
        <!-- Prompt Box -->
        <div class="space-y-1.5 p-3.5 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-white/10">
          <div class="flex items-center justify-between text-[11px] font-semibold uppercase tracking-wider text-slate-500">
            <span>Prompt</span>
            <button
              type="button"
              @click="copyText(galleryStore.activeAsset.prompt)"
              class="text-sky-500 hover:text-sky-400 font-bold"
            >
              Copy
            </button>
          </div>
          <p class="text-xs text-slate-900 dark:text-slate-100 leading-relaxed break-words font-medium">
            {{ galleryStore.activeAsset.prompt }}
          </p>
        </div>

        <!-- Negative Prompt (if any) -->
        <div
          v-if="galleryStore.activeAsset.negative_prompt"
          class="space-y-1.5 p-3.5 rounded-xl bg-rose-50 dark:bg-rose-950/30 border border-rose-200 dark:border-rose-900/40 text-rose-800 dark:text-rose-300"
        >
          <div class="text-[11px] font-semibold uppercase tracking-wider">Negative Prompt</div>
          <p class="text-xs leading-relaxed break-words">
            {{ galleryStore.activeAsset.negative_prompt }}
          </p>
        </div>

        <!-- Technical Parameters Grid -->
        <div class="grid grid-cols-2 gap-2 text-[11px]">
          <div class="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-white/10">
            <span class="text-slate-500 block">Model</span>
            <span class="font-semibold text-slate-900 dark:text-white truncate block">
              {{ galleryStore.activeAsset.model || 'N/A' }}
            </span>
          </div>

          <div class="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-white/10">
            <span class="text-slate-500 block">Provider</span>
            <span class="font-semibold text-slate-900 dark:text-white uppercase">
              {{ galleryStore.activeAsset.provider || 'N/A' }}
            </span>
          </div>

          <div class="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-white/10">
            <span class="text-slate-500 block">Dimensions / Ratio</span>
            <span class="font-semibold text-slate-900 dark:text-white">
              {{ (galleryStore.activeAsset.width && galleryStore.activeAsset.height) ? `${galleryStore.activeAsset.width} × ${galleryStore.activeAsset.height} (${galleryStore.activeAsset.aspect_ratio || '1:1'})` : (galleryStore.activeAsset.aspect_ratio || '1:1') }}
            </span>
          </div>

          <div class="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-white/10">
            <span class="text-slate-500 block">Seed</span>
            <span class="font-mono text-slate-900 dark:text-white">
              {{ galleryStore.activeAsset.seed ?? 'N/A' }}
            </span>
          </div>
        </div>

        <!-- Categories Management Section -->
        <div class="space-y-2 p-3 rounded-xl bg-slate-100 dark:bg-slate-800/80 border border-slate-200 dark:border-white/10">
          <div class="flex items-center justify-between">
            <span class="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
              Categories ({{ assignedCategories.length }})
            </span>
            <div class="relative">
              <button
                type="button"
                @click="isAddCatOpen = !isAddCatOpen"
                class="text-[11px] text-sky-600 dark:text-sky-400 font-bold hover:underline"
              >
                + Assign Category
              </button>

              <!-- Category Picker Popover -->
              <div
                v-if="isAddCatOpen"
                class="absolute right-0 top-full mt-1.5 w-56 rounded-xl bg-white dark:bg-slate-900 border border-slate-300/80 dark:border-white/15 shadow-xl p-2 z-50 text-xs space-y-2 animate-in fade-in zoom-in-95 duration-150"
              >
                <div class="flex items-center justify-between pb-1 border-b border-slate-200 dark:border-white/10">
                  <span class="font-bold text-[11px]">Select Category</span>
                  <button type="button" @click="isAddCatOpen = false" class="text-slate-400 hover:text-white">✕</button>
                </div>

                <div v-if="availableCategoriesToAdd.length === 0" class="py-2 text-center text-slate-400 text-[11px]">
                  No additional categories available
                </div>
                <div v-else class="max-h-36 overflow-y-auto space-y-1">
                  <button
                    v-for="cat in availableCategoriesToAdd"
                    :key="cat.id"
                    type="button"
                    @click="addCategory(cat.id)"
                    class="w-full text-left px-2 py-1.5 rounded-lg hover:bg-sky-50 dark:hover:bg-sky-950/50 hover:text-sky-600 dark:hover:text-sky-300 font-medium transition-colors truncate"
                  >
                    🏷️ {{ cat.name }}
                  </button>
                </div>

                <!-- Quick add new inline -->
                <div class="pt-1.5 border-t border-slate-200 dark:border-white/10 flex items-center gap-1">
                  <input
                    v-model="newCatName"
                    placeholder="New category..."
                    @keydown.enter.prevent="createAndAddCategory"
                    class="w-full rounded-lg bg-slate-100 dark:bg-slate-800 px-2 py-1 text-[11px] text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-none"
                  />
                  <button
                    type="button"
                    @click="createAndAddCategory"
                    :disabled="!newCatName.trim()"
                    class="px-2 py-1 bg-sky-500 text-white rounded-lg text-[11px] font-bold disabled:opacity-40"
                  >
                    +
                  </button>
                </div>
              </div>
            </div>
          </div>

          <!-- Assigned Category Badges -->
          <div v-if="assignedCategories.length > 0" class="flex flex-wrap gap-1.5">
            <span
              v-for="cat in assignedCategories"
              :key="cat.id"
              class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-sky-100 dark:bg-sky-950/60 text-sky-800 dark:text-sky-300 border border-sky-300 dark:border-sky-800/50 text-[11px] font-medium"
            >
              <span>🏷️ {{ cat.name }}</span>
              <button
                type="button"
                @click="removeCategory(cat.id)"
                class="hover:text-rose-500 font-bold ml-0.5"
                title="Remove category"
              >
                ✕
              </button>
            </span>
          </div>
          <p v-else class="text-[11px] text-slate-400 italic">
            No categories assigned.
          </p>
        </div>

        <!-- Action Buttons -->
        <div class="pt-2 border-t border-slate-200 dark:border-white/10 flex flex-wrap gap-2">
          <Button variant="primary" size="sm" @click="handleRemix">
            🔁 Remix in Studio
          </Button>

          <Button variant="surface" size="sm" @click="isUpscaleModalOpen = true">
            ✨ Upscale
          </Button>

          <Button variant="surface" size="sm" @click="handleUseAsInputImage">
            🖼️ Use as Input Image
          </Button>

          <Button
            variant="surface"
            size="sm"
            :disabled="isDownloading"
            @click="handleDownload"
          >
            ⬇️ {{ isDownloading ? 'Downloading...' : 'Download' }}
          </Button>

          <Button variant="danger" size="sm" @click="isDeleteConfirmOpen = true">
            🗑️ Delete
          </Button>
        </div>
      </div>
    </div>

    <!-- Confirm Delete Dialog -->
    <ConfirmDialog
      :open="isDeleteConfirmOpen"
      message="Do you really want to permanently delete this image?"
      @update:open="isDeleteConfirmOpen = $event"
      @confirm="handleDelete"
    />

    <!-- Upscale Modal -->
    <UpscaleModal
      :open="isUpscaleModalOpen"
      :asset="galleryStore.activeAsset"
      @update:open="isUpscaleModalOpen = $event"
      @submitted="handleUpscaleSubmitted"
    />
  </Modal>
</template>
