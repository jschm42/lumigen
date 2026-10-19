<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useGalleryStore } from '@/stores/gallery'
import { useImageViewerStore } from '@/stores/imageViewer'
import GalleryFilters from './components/GalleryFilters.vue'
import VirtualAssetGrid from './components/VirtualAssetGrid.vue'
import BatchActionBar from './components/BatchActionBar.vue'
import AssetDetailModal from './components/AssetDetailModal.vue'
import Spinner from '@/components/ui/Spinner.vue'
import Button from '@/components/ui/Button.vue'

const route = useRoute()
const router = useRouter()
const galleryStore = useGalleryStore()
const imageViewerStore = useImageViewerStore()

const scrollContainerRef = ref<HTMLElement | null>(null)
const sentinelRef = ref<HTMLElement | null>(null)
const hoveredAssetId = ref<number | null>(null)
let observer: IntersectionObserver | null = null

function isOverlayOpen() {
  return (
    imageViewerStore.isOpen ||
    galleryStore.isDetailModalOpen ||
    document.body.style.overflow === 'hidden' ||
    !!document.querySelector('.fixed.inset-0.z-50')
  )
}

function isTypingTarget(el: EventTarget | null) {
  const node = el as HTMLElement | null
  return !!node && (node.tagName === 'INPUT' || node.tagName === 'TEXTAREA' || node.tagName === 'SELECT' || node.isContentEditable)
}

function handleKeydown(e: KeyboardEvent) {
  if (isOverlayOpen()) return

  if (e.key === 'Escape') {
    const activeEl = document.activeElement as HTMLElement | null
    if (isTypingTarget(activeEl)) {
      activeEl?.blur()
      return
    }
    if (galleryStore.selectedAssetIds.length > 0) galleryStore.clearSelection()
    return
  }

  if (isTypingTarget(e.target)) return

  if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'a') {
    e.preventDefault()
    galleryStore.selectAll()
    return
  }
  if (e.ctrlKey || e.metaKey || e.altKey) return

  const targetId = hoveredAssetId.value
  if (targetId === null) return

  if (/^[0-5]$/.test(e.key)) {
    // Rating a selected image applies to the whole selection.
    const selection = galleryStore.selectedAssetIds
    const ids = selection.length > 1 && selection.includes(targetId) ? [...selection] : [targetId]
    galleryStore.rateAssets(ids, Number(e.key))
    e.preventDefault()
  } else if (e.key === ' ') {
    e.preventDefault()
    galleryStore.toggleSelectAsset(targetId, e.shiftKey)
  } else if (e.key === 'Enter') {
    const asset = galleryStore.displayedAssets.find((a) => a.id === targetId)
    if (asset) {
      e.preventDefault()
      galleryStore.openDetailModal(asset)
    }
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
    { root: scrollContainerRef.value, rootMargin: '800px 0px' }
  )
  observer.observe(sentinelRef.value)
}

// The sentinel only exists once results are rendered.
watch(sentinelRef, () => setupObserver())

// --- URL <-> filter sync ------------------------------------------------------
function queryKey(query: Record<string, unknown>) {
  return JSON.stringify(
    Object.keys(query)
      .sort()
      .map((key) => [key, query[key]])
  )
}

const filterQuery = computed(() => galleryStore.filtersToQuery())

// Filter changes update the URL: discrete changes push a history entry (so the
// browser's Back button steps through them), typing in the search box replaces it.
watch(filterQuery, (next, previous) => {
  if (queryKey(next) === queryKey(route.query as Record<string, unknown>)) return
  const onlySearchChanged =
    previous && queryKey({ ...next, q: undefined }) === queryKey({ ...previous, q: undefined })
  const navigate = onlySearchChanged ? router.replace : router.push
  navigate({ query: next })
})

// Back/forward navigation: apply the URL filters and reload.
watch(
  () => route.query,
  (query) => {
    if (route.name !== 'gallery') return
    if (queryKey(query as Record<string, unknown>) === queryKey(filterQuery.value)) return
    galleryStore.applyQuery(query as Record<string, unknown>)
    galleryStore.fetchAssets(true)
  }
)

onMounted(() => {
  if (Object.keys(route.query).length > 0) {
    galleryStore.applyQuery(route.query as Record<string, unknown>)
  } else if (Object.keys(filterQuery.value).length > 0) {
    router.replace({ query: filterQuery.value })
  }
  galleryStore.fetchAssets(true)
  galleryStore.loadFacets()
  galleryStore.loadPresets()
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  observer?.disconnect()
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
    <div v-if="isInitialLoading" class="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6 xl:grid-cols-7">
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

      <div :class="['transition-opacity duration-150', isRefreshing ? 'opacity-60' : '']">
        <VirtualAssetGrid
          :assets="galleryStore.displayedAssets"
          :scroll-el="scrollContainerRef"
          :thumb-size="galleryStore.filters.thumb_size"
          :group-by-date="galleryStore.filters.group_by_date !== false"
          :selected-ids="galleryStore.selectedAssetIds"
          @selection="galleryStore.setSelection($event)"
          @hover="hoveredAssetId = $event"
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
