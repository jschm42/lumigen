<script setup lang="ts">
import { ref } from 'vue'
import { useGalleryStore } from '@/stores/gallery'
import Button from '@/components/ui/Button.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import BulkCategorizeModal from './BulkCategorizeModal.vue'

const galleryStore = useGalleryStore()
const isDeleteConfirmOpen = ref(false)
const isCategorizeModalOpen = ref(false)

function handleBulkDelete() {
  isDeleteConfirmOpen.value = true
}

async function confirmDelete() {
  await galleryStore.bulkDelete()
  isDeleteConfirmOpen.value = false
}
</script>

<template>
  <div
    v-if="galleryStore.selectedAssetIds.length > 0"
    class="fixed bottom-6 left-1/2 -translate-x-1/2 z-40 flex items-center gap-3 px-4 py-2.5 rounded-2xl bg-slate-900/95 text-white shadow-2xl border border-white/15 backdrop-blur-xl animate-in fade-in slide-in-from-bottom-4 duration-200 text-xs"
  >
    <div class="font-semibold pr-2 border-r border-white/20">
      {{ galleryStore.selectedAssetIds.length }} selected
    </div>

    <!-- Clear selection -->
    <button
      type="button"
      @click="galleryStore.clearSelection"
      class="text-slate-400 hover:text-white transition-colors"
      title="Clear selection (Esc)"
    >
      Deselect (Esc)
    </button>

    <!-- Bulk Categorize Button -->
    <Button
      variant="secondary"
      size="xs"
      @click="isCategorizeModalOpen = true"
    >
      🏷️ Categories
    </Button>

    <!-- Bulk Delete Button -->
    <Button
      variant="danger"
      size="xs"
      @click="handleBulkDelete"
    >
      🗑️ Delete
    </Button>

    <ConfirmDialog
      :open="isDeleteConfirmOpen"
      :message="`Do you really want to delete all ${galleryStore.selectedAssetIds.length} selected images?`"
      @update:open="isDeleteConfirmOpen = $event"
      @confirm="confirmDelete"
    />

    <BulkCategorizeModal
      :open="isCategorizeModalOpen"
      @update:open="isCategorizeModalOpen = $event"
    />
  </div>
</template>

