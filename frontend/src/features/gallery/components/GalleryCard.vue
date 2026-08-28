<script setup lang="ts">
import { useGalleryStore } from '@/stores/gallery'
import type { Asset } from '@/types'

interface Props {
  asset: Asset
}

const props = defineProps<Props>()

const galleryStore = useGalleryStore()

function handleCardClick() {
  galleryStore.openDetailModal(props.asset)
}

function toggleSelect(e: MouseEvent) {
  e.stopPropagation()
  galleryStore.toggleSelectAsset(props.asset.id)
}

function toggleFav(e: MouseEvent) {
  e.stopPropagation()
  galleryStore.toggleFavorite(props.asset)
}
</script>

<template>
  <div
    @click="handleCardClick"
    :class="[
      'group relative rounded-2xl overflow-hidden border bg-slate-900 shadow-sm transition-all duration-200 cursor-pointer select-none',
      galleryStore.selectedAssetIds.includes(asset.id)
        ? 'border-sky-500 ring-2 ring-sky-500/50 shadow-lg'
        : 'border-slate-200/80 hover:border-sky-400 dark:border-white/10 dark:hover:border-white/30',
    ]"
  >
    <!-- Thumbnail Image with aspect ratio placeholder -->
    <div class="w-full aspect-square overflow-hidden bg-slate-950 flex items-center justify-center">
      <img
        :src="asset.thumbnail_url || asset.image_url"
        :alt="asset.prompt"
        class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
        loading="lazy"
      />
    </div>

    <!-- Top Overlay (Select checkbox & Favorite star) -->
    <div class="absolute top-2 left-2 right-2 flex items-center justify-between pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity">
      <button
        type="button"
        @click="toggleSelect"
        :class="[
          'w-6 h-6 rounded-lg flex items-center justify-center pointer-events-auto transition-colors border shadow-sm',
          galleryStore.selectedAssetIds.includes(asset.id)
            ? 'bg-sky-500 border-sky-500 text-white'
            : 'bg-black/60 border-white/30 text-white hover:bg-black/80',
        ]"
      >
        <span v-if="galleryStore.selectedAssetIds.includes(asset.id)" class="text-xs font-bold">✓</span>
      </button>

      <button
        type="button"
        @click="toggleFav"
        class="w-6 h-6 rounded-lg bg-black/60 border border-white/30 text-amber-400 hover:bg-black/80 flex items-center justify-center pointer-events-auto transition-colors shadow-sm"
        title="Favorit"
      >
        <span>{{ asset.is_favorite ? '★' : '☆' }}</span>
      </button>
    </div>

    <!-- Bottom Caption Overlay on hover -->
    <div class="absolute inset-x-0 bottom-0 p-2.5 bg-gradient-to-t from-black/90 via-black/60 to-transparent text-white opacity-0 group-hover:opacity-100 transition-opacity">
      <p class="text-[11px] line-clamp-2 leading-tight font-medium">
        {{ asset.prompt }}
      </p>
      <div class="flex items-center justify-between mt-1 text-[10px] text-slate-300 font-mono">
        <span>{{ asset.aspect_ratio }}</span>
        <span>{{ asset.model || asset.provider }}</span>
      </div>
    </div>
  </div>
</template>
