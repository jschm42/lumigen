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
  <div
    @click="handleCardClick"
    :title="galleryStore.selectedAssetIds.includes(asset.id) ? 'Ausgewählt (Strg+Klick zum Abwählen)' : 'Klicken zum Öffnen (Strg+Klick zur Schnellauswahl)'"
    :class="[
      'group relative rounded-2xl border bg-slate-900 shadow-sm transition-all duration-200 cursor-pointer select-none',
      isRatingOpen ? 'z-30 overflow-visible' : 'overflow-hidden z-10',
      galleryStore.selectedAssetIds.includes(asset.id)
        ? 'border-sky-500 ring-2 ring-sky-500/50 shadow-lg'
        : 'border-slate-200/80 hover:border-sky-400 dark:border-white/10 dark:hover:border-white/30',
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

    <!-- Top Overlay (Select checkbox & Rating button) -->
    <div
      class="absolute top-2 left-2 right-2 flex items-center justify-between pointer-events-none"
    >
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
        title="Auswählen (oder Strg + Klick auf das Bild)"
      >
        <span v-if="galleryStore.selectedAssetIds.includes(asset.id)" class="text-xs font-bold">✓</span>
      </button>

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
              ? `Bewertung: ${asset.rating} ${asset.rating === 1 ? 'Stern' : 'Sterne'} (Klicken zum Ändern)`
              : 'Bewerten (0–5 Sterne)'
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
            title="0 Sterne (Keine Bewertung)"
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
              :title="`${star} ${star === 1 ? 'Stern' : 'Sterne'}`"
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
        <span>{{ asset.model || asset.provider }}</span>
      </div>
    </div>
  </div>
</template>
