<script setup lang="ts">
import { computed, onMounted } from 'vue'
import { useGalleryStore } from '@/stores/gallery'
import GalleryFilters from './components/GalleryFilters.vue'
import GalleryCard from './components/GalleryCard.vue'
import BatchActionBar from './components/BatchActionBar.vue'
import AssetDetailModal from './components/AssetDetailModal.vue'
import Spinner from '@/components/ui/Spinner.vue'

const galleryStore = useGalleryStore()

onMounted(() => {
  galleryStore.fetchAssets(true)
})

const gridColsClass = computed(() => {
  switch (galleryStore.filters.thumb_size) {
    case 'sm':
      return 'grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2.5'
    case 'lg':
      return 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4'
    case 'md':
    default:
      return 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3.5'
  }
})
</script>

<template>
  <div class="space-y-6 pb-20">
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
