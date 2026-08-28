<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGalleryStore } from '@/stores/gallery'
import { useGenerateStore } from '@/stores/generate'
import { useToastStore } from '@/stores/toast'
import Modal from '@/components/ui/Modal.vue'
import Button from '@/components/ui/Button.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'

const router = useRouter()
const galleryStore = useGalleryStore()
const generateStore = useGenerateStore()
const toastStore = useToastStore()

const isDeleteConfirmOpen = ref(false)

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

async function handleDelete() {
  if (!galleryStore.activeAsset) return
  await galleryStore.deleteAsset(galleryStore.activeAsset.id)
  isDeleteConfirmOpen.value = false
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
            @click="galleryStore.rateAsset(galleryStore.activeAsset, star)"
            class="text-base text-amber-400 hover:scale-110 transition-transform"
          >
            {{ (galleryStore.activeAsset.rating || 0) >= star ? '★' : '☆' }}
          </button>
        </div>
      </div>
    </template>

    <div v-if="galleryStore.activeAsset" class="grid grid-cols-1 lg:grid-cols-12 gap-6 text-xs">
      <!-- Left: High-Res Image Display -->
      <div class="lg:col-span-7 flex flex-col items-center justify-center bg-slate-950 rounded-2xl p-2 border border-slate-200/60 dark:border-white/10 overflow-hidden min-h-[350px]">
        <img
          :src="galleryStore.activeAsset.image_url || galleryStore.activeAsset.thumbnail_url"
          :alt="galleryStore.activeAsset.prompt"
          class="max-h-[65vh] w-auto object-contain rounded-xl shadow-2xl"
        />
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

        <!-- Action Buttons -->
        <div class="pt-2 border-t border-slate-200 dark:border-white/10 flex flex-wrap gap-2">
          <Button variant="primary" size="sm" @click="handleRemix">
            🔁 Remix in Studio
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
