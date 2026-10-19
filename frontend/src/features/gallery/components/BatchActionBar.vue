<script setup lang="ts">
import { computed, ref } from 'vue'
import { useGalleryStore } from '@/stores/gallery'
import Button from '@/components/ui/Button.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import BulkCategorizeModal from './BulkCategorizeModal.vue'

const galleryStore = useGalleryStore()
const isDeleteConfirmOpen = ref(false)
const isCategorizeModalOpen = ref(false)

const hasStackedSelected = computed(() => {
  return galleryStore.selectedAssetIds.some((id) => {
    const a = galleryStore.assets.find((item) => item.id === id)
    if (a?.stack_id) return true
    for (const item of galleryStore.assets) {
      if (item.stack_items?.some((sub) => sub.id === id && sub.stack_id)) return true
    }
    return false
  })
})

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

    <!-- Stack Button (if 2+ selected) -->
    <Button
      v-if="galleryStore.selectedAssetIds.length >= 2"
      variant="secondary"
      size="xs"
      @click="galleryStore.stackSelected"
      title="Group selected images into a photo stack"
    >
      📚 Stack ({{ galleryStore.selectedAssetIds.length }})
    </Button>

    <!-- Unstack Button (if stacked items selected) -->
    <Button
      v-if="hasStackedSelected"
      variant="secondary"
      size="xs"
      @click="galleryStore.unstackSelected"
      title="Unstack selected images"
    >
      📑 Unstack
    </Button>

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

