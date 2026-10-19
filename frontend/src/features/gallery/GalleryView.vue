<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useGalleryStore } from '@/stores/gallery'
import { useImageViewerStore } from '@/stores/imageViewer'
import GalleryFilters from './components/GalleryFilters.vue'
import GalleryCard from './components/GalleryCard.vue'
import BatchActionBar from './components/BatchActionBar.vue'
import AssetDetailModal from './components/AssetDetailModal.vue'
import Spinner from '@/components/ui/Spinner.vue'
import Button from '@/components/ui/Button.vue'

const galleryStore = useGalleryStore()
const imageViewerStore = useImageViewerStore()

const scrollContainerRef = ref<HTMLElement | null>(null)
const sentinelRef = ref<HTMLElement | null>(null)
let observer: IntersectionObserver | null = null

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

function setupObserver() {
  observer?.disconnect()
  if (!sentinelRef.value || typeof IntersectionObserver === 'undefined') return
  observer = new IntersectionObserver(
    (entries) => {
      if (entries.some((entry) => entry.isIntersecting)) {
        galleryStore.loadMore()
      }
    },
    { root: scrollContainerRef.value, rootMargin: '600px 0px' }
  )
  observer.observe(sentinelRef.value)
}

// The sentinel only exists once results are rendered.
watch(sentinelRef, () => setupObserver())

onMounted(() => {
  galleryStore.fetchAssets(true)
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  observer?.disconnect()
})

const gridColsClass = computed(() => {
  switch (galleryStore.filters.thumb_size) {
    case 'sm':
      return 'grid-cols-3 sm:grid-cols-4 md:grid-cols-6 lg:grid-cols-8 xl:grid-cols-10 2xl:grid-cols-12 gap-2'
    case 'lg':
      return 'grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5 2xl:grid-cols-6 gap-4'
    case 'md':
    default:
      return 'grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7 2xl:grid-cols-9 gap-3'
  }
})

const isInitialLoading = computed(() => galleryStore.isLoading && !galleryStore.hasLoadedOnce)
const isRefreshing = computed(() => galleryStore.isLoading && galleryStore.hasLoadedOnce)
</script>

<template>
  <div ref="scrollContainerRef" class="h-full overflow-y-auto pb-24 pr-1" data-testid="gallery-scroll">
    <!-- Sticky filter bar -->
    <div class="sticky top-0 z-30 pb-3 pt-0.5">
      <GalleryFilters />
    </div>

    <!-- Initial loading: skeleton grid -->
    <div v-if="isInitialLoading" :class="['grid', gridColsClass]">
      <div
        v-for="n in 18"
        :key="n"
        class="aspect-square animate-pulse rounded-2xl bg-slate-200/80 dark:bg-slate-800/60"
      />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="galleryStore.displayedAssets.length === 0 && !galleryStore.isLoading"
      class="py-20 text-center space-y-3"
    >
      <div class="text-4xl">🖼️</div>
      <h3 class="text-base font-bold text-slate-800 dark:text-white">
        {{ galleryStore.activeFilterCount > 0 ? 'No images match your filters' : 'Your gallery is empty' }}
      </h3>
      <p class="text-xs text-slate-500 max-w-sm mx-auto">
        {{ galleryStore.activeFilterCount > 0 ? 'Try removing a filter or widening the time range.' : 'Generated images appear here automatically.' }}
      </p>
      <div class="flex justify-center gap-2 pt-1">
        <Button v-if="galleryStore.activeFilterCount > 0" variant="secondary" size="sm" @click="galleryStore.resetFilters">
          Reset filters
        </Button>
        <router-link v-else to="/">
          <Button variant="primary" size="sm">Open studio</Button>
        </router-link>
      </div>
    </div>

    <!-- Gallery Grid (stays visible while filters reload) -->
    <div v-else class="relative">
      <div
        v-if="isRefreshing"
        class="pointer-events-none absolute inset-x-0 -top-1 z-20 flex justify-center"
      >
        <span class="inline-flex items-center gap-2 rounded-full border border-slate-200 bg-white/95 px-3 py-1 text-[11px] font-medium text-slate-600 shadow-md dark:border-white/10 dark:bg-slate-800/95 dark:text-slate-300">
          <Spinner size="sm" class="text-sky-500" /> Updating…
        </span>
      </div>

      <div
        :class="['grid transition-opacity duration-150', gridColsClass, isRefreshing ? 'opacity-60' : '']"
        data-testid="gallery-grid"
      >
        <GalleryCard
          v-for="asset in galleryStore.displayedAssets"
          :key="asset.id"
          :asset="asset"
        />
      </div>

      <!-- Infinite scroll sentinel + manual fallback -->
      <div ref="sentinelRef" class="flex flex-col items-center gap-2 py-6 text-xs text-slate-400">
        <template v-if="galleryStore.hasMore">
          <Spinner v-if="galleryStore.isLoadingMore" size="md" class="text-sky-500" />
          <Button v-else variant="secondary" size="sm" @click="galleryStore.loadMore" data-testid="gallery-load-more">
            Load more
          </Button>
        </template>
        <span v-else-if="galleryStore.total > 0">All {{ galleryStore.total }} images loaded</span>
      </div>
    </div>

    <!-- Floating Batch Actions Toolbar -->
    <BatchActionBar />

    <!-- Asset Detail Modal -->
    <AssetDetailModal />
  </div>
</template>
