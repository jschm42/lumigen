<script setup lang="ts">
import { computed, onMounted, onUnmounted } from 'vue'
import { useGalleryStore } from '@/stores/gallery'
import { useImageViewerStore } from '@/stores/imageViewer'
import GalleryFilters from './components/GalleryFilters.vue'
import GalleryCard from './components/GalleryCard.vue'
import BatchActionBar from './components/BatchActionBar.vue'
import AssetDetailModal from './components/AssetDetailModal.vue'
import Spinner from '@/components/ui/Spinner.vue'

const galleryStore = useGalleryStore()
const imageViewerStore = useImageViewerStore()

function handleKeydown(e: KeyboardEvent) {
  if (e.key !== 'Escape') return

  // Do not clear selection if a modal or image viewer is active
  if (
    imageViewerStore.isOpen ||
    galleryStore.isDetailModalOpen ||
    document.body.style.overflow === 'hidden' ||
    document.querySelector('.fixed.inset-0.z-50')
  ) {
    return
  }

  // If focused in an input/textarea, blur it first
  const activeEl = document.activeElement as HTMLElement | null
  if (activeEl && (activeEl.tagName === 'INPUT' || activeEl.tagName === 'TEXTAREA')) {
    activeEl.blur()
    return
  }

  if (galleryStore.selectedAssetIds.length > 0) {
    galleryStore.clearSelection()
  }
}

onMounted(() => {
  galleryStore.fetchAssets(true)
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
})

const gridColsClass = computed(() => {
  switch (galleryStore.filters.thumb_size) {
    case 'sm':
      return 'grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 2xl:grid-cols-12 gap-2.5'
    case 'lg':
      return 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4'
    case 'md':
    default:
      return 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-8 2xl:grid-cols-10 gap-3.5'
  }
})
</script>

<template>
  <div class="h-full overflow-y-auto space-y-4 pb-20 pr-1">
    <!-- Top Filter Bar -->
    <GalleryFilters />

    <!-- Loading state -->
    <div v-if="galleryStore.isLoading" class="py-20 flex justify-center">
      <Spinner size="lg" class="text-sky-500" />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="galleryStore.assets.length === 0"
      class="py-20 text-center space-y-3"
    >
      <div class="text-4xl">🖼️</div>
      <h3 class="text-base font-bold text-slate-800 dark:text-white">Keine Bilder gefunden</h3>
      <p class="text-xs text-slate-500 max-w-sm mx-auto">
        Passe deine Filter an oder generiere neue Bilder im Studio.
      </p>
    </div>

    <!-- Gallery Grid -->
    <div v-else :class="['grid', gridColsClass]">
      <GalleryCard
        v-for="asset in galleryStore.assets"
        :key="asset.id"
        :asset="asset"
      />
    </div>

    <!-- Floating Batch Actions Toolbar -->
    <BatchActionBar />

    <!-- Asset Detail Modal -->
    <AssetDetailModal />
  </div>
</template>
