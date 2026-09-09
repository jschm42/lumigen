<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

import { useGalleryStore } from '@/stores/gallery'
import { useGenerateStore } from '@/stores/generate'
import { useToastStore } from '@/stores/toast'
import { useImageViewerStore } from '@/stores/imageViewer'
import Modal from '@/components/ui/Modal.vue'
import Button from '@/components/ui/Button.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'

const router = useRouter()
const galleryStore = useGalleryStore()
const generateStore = useGenerateStore()
const toastStore = useToastStore()
const imageViewerStore = useImageViewerStore()

const isDeleteConfirmOpen = ref(false)
const isAddCatOpen = ref(false)
const newCatName = ref('')
const isCreatingCat = ref(false)

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
    toastStore.success('In die Zwischenablage kopiert!')
  } catch (_e) {
    toastStore.error('Kopieren fehlgeschlagen.')
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
  toastStore.info('Prompt & Einstellungen in Studio geladen!')
}

function handleUseAsInputImage() {
  if (!galleryStore.activeAsset) return
  generateStore.attachAssetAsImage(galleryStore.activeAsset)
  galleryStore.closeDetailModal()
  router.push('/')
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
            :title="galleryStore.activeAsset.rating === star ? 'Bewertung aufheben' : `${star} Sterne`"
          >
            {{ (galleryStore.activeAsset.rating || 0) >= star ? '★' : '☆' }}
          </button>
        </div>
      </div>
    </template>

    <div v-if="galleryStore.activeAsset" class="grid grid-cols-1 lg:grid-cols-12 gap-6 text-xs">
      <!-- Left: High-Res Image Display with Zoom Trigger -->
      <div
        @click="openImageViewer"
        class="lg:col-span-7 group relative flex flex-col items-center justify-center bg-slate-950 rounded-2xl p-2 border border-slate-200/60 dark:border-white/10 overflow-hidden min-h-[350px] cursor-pointer hover:border-sky-500/50 transition-colors"
        title="In Vollbild & Zoom-Viewer öffnen"
      >
        <img
          :src="galleryStore.activeAsset.image_url || galleryStore.activeAsset.thumbnail_url"
          :alt="galleryStore.activeAsset.prompt"
          class="max-h-[65vh] w-auto object-contain rounded-xl shadow-2xl transition-transform duration-200 group-hover:scale-[1.01]"
        />
        <div class="absolute bottom-4 right-4 opacity-0 group-hover:opacity-100 transition-opacity bg-slate-900/80 backdrop-blur-md px-2.5 py-1 rounded-lg text-white text-xs flex items-center gap-1.5 border border-white/10 shadow-lg pointer-events-none">
          <svg class="w-3.5 h-3.5 text-sky-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v6m3-3H7" />
          </svg>
          <span>Vollbild & Zoom</span>
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
              Kopieren
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
          <div class="text-[11px] font-semibold uppercase tracking-wider">Negativer Prompt</div>
          <p class="text-xs leading-relaxed break-words">
            {{ galleryStore.activeAsset.negative_prompt }}
          </p>
        </div>

        <!-- Technical Parameters Grid -->
        <div class="grid grid-cols-2 gap-2 text-[11px]">
          <div class="p-2.5 rounded-xl bg-slate-100 dark:bg-slate-800/60 border border-slate-200 dark:border-white/10">
            <span class="text-slate-500 block">Modell</span>
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
            <span class="text-slate-500 block">Format / Ratio</span>
            <span class="font-semibold text-slate-900 dark:text-white">
              {{ galleryStore.activeAsset.aspect_ratio || '1:1' }}
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
              Kategorien ({{ assignedCategories.length }})
            </span>
            <div class="relative">
              <button
                type="button"
                @click="isAddCatOpen = !isAddCatOpen"
                class="text-[11px] text-sky-600 dark:text-sky-400 font-bold hover:underline"
              >
                + Kategorie zuweisen
              </button>

              <!-- Category Picker Popover -->
              <div
                v-if="isAddCatOpen"
                class="absolute right-0 top-full mt-1.5 w-56 rounded-xl bg-white dark:bg-slate-900 border border-slate-300/80 dark:border-white/15 shadow-xl p-2 z-50 text-xs space-y-2 animate-in fade-in zoom-in-95 duration-150"
              >
                <div class="flex items-center justify-between pb-1 border-b border-slate-200 dark:border-white/10">
                  <span class="font-bold text-[11px]">Kategorie wählen</span>
                  <button type="button" @click="isAddCatOpen = false" class="text-slate-400 hover:text-white">✕</button>
                </div>

                <div v-if="availableCategoriesToAdd.length === 0" class="py-2 text-center text-slate-400 text-[11px]">
                  Keine weiteren Kategorien verfügbar
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
                    placeholder="Neu anlegen..."
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
                title="Kategorie entfernen"
              >
                ✕
              </button>
            </span>
          </div>
          <p v-else class="text-[11px] text-slate-400 italic">
            Keine Kategorien zugewiesen.
          </p>
        </div>

        <!-- Action Buttons -->

        <div class="pt-2 border-t border-slate-200 dark:border-white/10 flex flex-wrap gap-2">
          <Button variant="primary" size="sm" @click="handleRemix">
            🔁 Remix in Studio
          </Button>

          <Button variant="surface" size="sm" @click="handleUseAsInputImage">
            🖼️ Als Eingabebild nutzen
          </Button>

          <a
            :href="galleryStore.activeAsset.download_url || galleryStore.activeAsset.image_url"
            download
            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-slate-300 dark:border-white/10 bg-white/70 dark:bg-slate-800 hover:bg-slate-100 text-slate-800 dark:text-white font-semibold transition-colors"
          >
            ⬇️ Download
          </a>

          <Button variant="danger" size="sm" @click="isDeleteConfirmOpen = true">
            🗑️ Löschen
          </Button>
        </div>
      </div>
    </div>

    <!-- Confirm Delete Dialog -->
    <ConfirmDialog
      :open="isDeleteConfirmOpen"
      message="Möchtest du dieses Bild unwiderruflich löschen?"
      @update:open="isDeleteConfirmOpen = $event"
      @confirm="handleDelete"
    />
  </Modal>
</template>
