<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useGalleryStore } from '@/stores/gallery'
import type { Asset } from '@/types'

interface Props {
  asset: Asset
}

const props = defineProps<Props>()

const galleryStore = useGalleryStore()

const isRatingOpen = ref(false)
const hoverRating = ref(0)
const ratingRef = ref<HTMLElement | null>(null)

function handleCardClick(e: MouseEvent) {
  // Quick selection with Ctrl / Cmd (or Shift for range selection)
  if (e.ctrlKey || e.metaKey || e.shiftKey) {
    e.preventDefault()
    e.stopPropagation()
    galleryStore.toggleSelectAsset(props.asset.id, e.shiftKey)
    return
  }
  galleryStore.openDetailModal(props.asset)
}

function toggleSelect(e: MouseEvent) {
  e.stopPropagation()
  galleryStore.toggleSelectAsset(props.asset.id, e.shiftKey)
}

function toggleStack(e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()
  if (props.asset.stack_id) {
    galleryStore.toggleStackExpanded(props.asset.stack_id)
  }
}

async function setCover(e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()
  await galleryStore.setStackCover(props.asset.id)
}

function toggleRatingPopup(e: MouseEvent) {
  e.preventDefault()
  e.stopPropagation()
  isRatingOpen.value = !isRatingOpen.value
  hoverRating.value = 0
}

async function selectRating(val: number, e?: MouseEvent) {
  e?.preventDefault()
  e?.stopPropagation()
  isRatingOpen.value = false
  hoverRating.value = 0
  await galleryStore.rateAsset(props.asset, val)
}

function handleClickOutside(event: MouseEvent) {
  if (isRatingOpen.value && ratingRef.value && !ratingRef.value.contains(event.target as Node)) {
    isRatingOpen.value = false
    hoverRating.value = 0
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && isRatingOpen.value) {
    isRatingOpen.value = false
    hoverRating.value = 0
    event.stopPropagation()
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
})
</script>

<template>
  <div class="relative group/stack">
    <!-- Physical Stack Backplates (Shown for collapsed stack) -->
    <template v-if="asset.stack_id && !galleryStore.isStackExpanded(asset.stack_id)">
      <!-- Backmost Layer 2 -->
      <div
        class="absolute inset-0 translate-x-2 -translate-y-2 rounded-2xl border-2 border-indigo-400/50 bg-slate-800/90 dark:border-indigo-400/40 dark:bg-slate-900/90 pointer-events-none transition-transform duration-300 group-hover/stack:translate-x-2.5 group-hover/stack:-translate-y-2.5 shadow-sm"
      />
      <!-- Middle Layer 1 -->
      <div
        class="absolute inset-0 translate-x-1 -translate-y-1 rounded-2xl border-2 border-indigo-400/75 bg-slate-800/95 dark:border-indigo-400/65 dark:bg-slate-900/95 pointer-events-none transition-transform duration-300 group-hover/stack:translate-x-1.5 group-hover/stack:-translate-y-1.5 shadow-sm"
      />
    </template>

    <!-- Main Front Card -->
    <div
      @click="handleCardClick"
      :title="galleryStore.selectedAssetIds.includes(asset.id) ? 'Selected (Ctrl+Click to deselect)' : 'Click to open (Ctrl+Click for quick select)'"
      :class="[
        'group relative rounded-2xl bg-slate-900 shadow-sm transition-all duration-200 cursor-pointer select-none',
        isRatingOpen ? 'z-30 overflow-visible' : 'overflow-hidden z-10',
        galleryStore.selectedAssetIds.includes(asset.id)
          ? 'border-2 border-sky-500 ring-2 ring-sky-500/50 shadow-lg'
          : asset.stack_id && !galleryStore.isStackExpanded(asset.stack_id)
            ? 'border-2 border-indigo-500 dark:border-indigo-400 ring-2 ring-indigo-500/25 shadow-lg shadow-indigo-950/40 hover:border-indigo-400 hover:ring-indigo-400/50'
            : asset.stack_id && galleryStore.isStackExpanded(asset.stack_id)
              ? 'border-2 border-indigo-500/90 dark:border-indigo-400/90 ring-2 ring-indigo-500/30 bg-indigo-950/20'
              : 'border border-slate-200/80 hover:border-sky-400 dark:border-white/10 dark:hover:border-white/30',
      ]"
    >
      <!-- Thumbnail Image with aspect ratio placeholder -->
      <div class="w-full aspect-square overflow-hidden rounded-2xl bg-slate-950 flex items-center justify-center">
        <img
          :src="asset.thumbnail_url || asset.image_url"
          :alt="asset.prompt"
          class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          loading="lazy"
        />
      </div>

      <!-- Top Overlay (Select checkbox, Stack badge & Rating button) -->
      <div
        class="absolute top-2 left-2 right-2 flex items-center justify-between pointer-events-none"
      >
        <!-- Left side: Checkbox & Stack Badge -->
        <div class="flex items-center gap-1.5 pointer-events-auto">
          <!-- Select Checkbox -->
          <button
            type="button"
            @click="toggleSelect"
            :class="[
              'w-6 h-6 rounded-lg flex items-center justify-center pointer-events-auto transition-all border shadow-sm',
              galleryStore.selectedAssetIds.includes(asset.id)
                ? 'bg-sky-500 border-sky-500 text-white shadow-sky-500/50 opacity-100'
                : 'bg-black/60 border-white/30 text-white hover:bg-black/80 opacity-0 group-hover:opacity-100',
            ]"
            title="Select (or Ctrl + Click on image)"
          >
            <span v-if="galleryStore.selectedAssetIds.includes(asset.id)" class="text-xs font-bold">✓</span>
          </button>

          <!-- Stack Badge -->
          <button
            v-if="asset.stack_id"
            type="button"
            @click="toggleStack"
            :class="[
              'h-6 px-2 rounded-lg flex items-center gap-1.5 pointer-events-auto transition-all text-[11px] font-semibold border shadow-md',
              'bg-indigo-600/95 hover:bg-indigo-500 border-indigo-400 text-white shadow-indigo-950/60',
            ]"
            :title="
              galleryStore.isStackExpanded(asset.stack_id)
                ? `Stack of ${asset.stack_count || asset.stack_items?.length || 1} images (${(asset.stack_order || 0) + 1}/${asset.stack_count || asset.stack_items?.length || 1}) • Click to collapse`
                : `Photo Stack (${asset.stack_count || asset.stack_items?.length || 1} images) • Click to expand`
            "
          >
            <svg class="w-3.5 h-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
            </svg>
            <span v-if="!galleryStore.isStackExpanded(asset.stack_id)" class="font-bold font-mono">
              {{ asset.stack_count || asset.stack_items?.length || 1 }}
            </span>
            <span v-else class="flex items-center gap-0.5">
              <span class="font-bold font-mono">{{ (asset.stack_order || 0) + 1 }}/{{ asset.stack_count || asset.stack_items?.length || 1 }}</span>
              <span class="text-[9px] opacity-80 font-bold">◀</span>
            </span>
          </button>
        </div>

      <!-- Rating Button & Popup -->
      <div
        ref="ratingRef"
        :class="[
          'relative pointer-events-auto transition-opacity duration-150',
          (asset.rating && asset.rating > 0) || isRatingOpen
            ? 'opacity-100'
            : 'opacity-0 group-hover:opacity-100',
        ]"
      >
        <!-- Rating Button on Card -->
        <button
          type="button"
          @click="toggleRatingPopup"
          :class="[
            'h-6 rounded-lg border flex items-center justify-center transition-all shadow-sm pointer-events-auto',
            asset.rating && asset.rating > 0
              ? 'px-1.5 gap-1 bg-black/70 border-amber-400/40 text-amber-400 hover:bg-black/85 hover:border-amber-400/70'
              : 'w-6 bg-black/60 border-white/30 text-slate-300 hover:text-amber-400 hover:bg-black/80',
          ]"
          :title="
            asset.rating && asset.rating > 0
              ? `Rating: ${asset.rating} ${asset.rating === 1 ? 'star' : 'stars'} (Click to change)`
              : 'Rate (0–5 stars)'
          "
        >
          <span class="text-xs leading-none">{{ asset.rating && asset.rating > 0 ? '★' : '☆' }}</span>
          <span
            v-if="asset.rating && asset.rating > 0"
            class="text-[11px] font-bold text-amber-300 leading-none"
          >
            {{ asset.rating }}
          </span>
        </button>

        <!-- Rating Popup (0-5 stars) -->
        <div
          v-if="isRatingOpen"
          @click.stop
          class="absolute top-full right-0 mt-1.5 z-50 bg-slate-900/95 backdrop-blur-md border border-white/20 rounded-xl p-1 shadow-2xl flex items-center gap-1 select-none"
        >
          <!-- 0 Stars Option -->
          <button
            type="button"
            @click="selectRating(0, $event)"
            @mouseenter="hoverRating = -1"
            @mouseleave="hoverRating = 0"
            :class="[
              'px-1.5 py-1 rounded-lg text-[11px] font-semibold transition-colors flex items-center gap-0.5',
              (!asset.rating || asset.rating === 0)
                ? 'bg-white/20 text-white font-bold'
                : 'text-slate-400 hover:text-white hover:bg-white/10',
            ]"
            title="0 Stars (No rating)"
          >
            <span>0</span>
            <span class="text-xs leading-none">☆</span>
          </button>

          <div class="w-px h-3.5 bg-white/20"></div>

          <!-- 1-5 Stars -->
          <div class="flex items-center">
            <button
              v-for="star in [1, 2, 3, 4, 5]"
              :key="star"
              type="button"
              @click="selectRating(star, $event)"
              @mouseenter="hoverRating = star"
              @mouseleave="hoverRating = 0"
              class="p-1 text-sm leading-none transition-transform hover:scale-125 focus:outline-none"
              :class="
                hoverRating === -1
                  ? 'text-slate-600'
                  : (hoverRating > 0 ? hoverRating >= star : (asset.rating || 0) >= star)
                    ? 'text-amber-400 drop-shadow-[0_0_4px_rgba(251,191,36,0.6)]'
                    : 'text-slate-500 hover:text-amber-300'
              "
              :title="`${star} ${star === 1 ? 'star' : 'stars'}`"
            >
              ★
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Bottom Caption Overlay on hover -->
    <div class="absolute inset-x-0 bottom-0 p-2.5 bg-gradient-to-t from-black/90 via-black/60 to-transparent text-white opacity-0 group-hover:opacity-100 transition-opacity">
      <p class="text-[11px] line-clamp-2 leading-tight font-medium">
        {{ asset.prompt }}
      </p>
      <div class="flex items-center justify-between mt-1 text-[10px] text-slate-300 font-mono">
        <span>{{ asset.aspect_ratio }}</span>
        <div v-if="asset.stack_id && galleryStore.isStackExpanded(asset.stack_id)" class="flex items-center gap-1 font-sans">
          <button
            v-if="asset.stack_order !== 0"
            type="button"
            @click.stop="setCover"
            class="px-1.5 py-0.5 rounded bg-white/20 hover:bg-sky-500 text-white text-[10px] font-medium transition-colors"
            title="Make this image the stack cover"
          >
            ★ Cover
          </button>
        </div>
        <span>{{ asset.model || asset.provider }}</span>
      </div>
    </div>
  </div>
</div>
</template>
