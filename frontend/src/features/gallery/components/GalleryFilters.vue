<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { useGalleryStore } from '@/stores/gallery'

const galleryStore = useGalleryStore()
const isCategoryPopoverOpen = ref(false)

onMounted(() => {
  galleryStore.loadCategories()
})

const timePresets = [
  { value: '', label: 'Gesamte Zeit' },
  { value: 'today', label: 'Heute' },
  { value: 'yesterday', label: 'Gestern' },
  { value: 'last_7_days', label: 'Letzte 7 Tage' },
  { value: 'last_30_days', label: 'Letzte 30 Tage' },
]

function toggleCategory(catId: number) {
  const current = [...galleryStore.filters.category_ids]
  const index = current.indexOf(catId)
  if (index !== -1) {
    current.splice(index, 1)
  } else {
    current.push(catId)
  }
  galleryStore.filters.category_ids = current
  galleryStore.fetchAssets(true)
}
</script>

<template>
  <div class="space-y-3 p-4 rounded-2xl border border-slate-200/80 bg-white/70 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/70 shadow-sm text-xs">
    <!-- Top Filter Row: Search & Selects -->
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
      <!-- Search Input -->
      <div class="lg:col-span-2">
        <input
          type="text"
          v-model="galleryStore.filters.q"
          @input="galleryStore.fetchAssets(true)"
          placeholder="Suchbegriff im Prompt..."
          class="w-full rounded-xl border border-slate-300/80 bg-white/80 px-3 py-2 text-xs text-slate-900 placeholder-slate-400 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
        />
      </div>

      <!-- Time Preset -->
      <div>
        <select
          v-model="galleryStore.filters.time_preset"
          @change="galleryStore.fetchAssets(true)"
          class="w-full rounded-xl border border-slate-300/80 bg-white/80 px-3 py-2 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
        >
          <option v-for="t in timePresets" :key="t.value" :value="t.value">{{ t.label }}</option>
        </select>
      </div>

      <!-- Min Rating -->
      <div>
        <select
          v-model="galleryStore.filters.min_rating"
          @change="galleryStore.fetchAssets(true)"
          class="w-full rounded-xl border border-slate-300/80 bg-white/80 px-3 py-2 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
        >
          <option :value="null">Alle Bewertungen</option>
          <option :value="5">⭐⭐⭐⭐⭐ (5 Sterne)</option>
          <option :value="4">⭐⭐⭐⭐ (min. 4 Sterne)</option>
          <option :value="3">⭐⭐⭐ (min. 3 Sterne)</option>
          <option :value="1">⭐ (min. 1 Stern)</option>
        </select>
      </div>

      <!-- Categories Popover -->
      <div class="relative">
        <button
          type="button"
          @click="isCategoryPopoverOpen = !isCategoryPopoverOpen"
          class="w-full flex items-center justify-between rounded-xl border border-slate-300/80 bg-white/80 px-3 py-2 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100"
        >
          <span>Kategorien ({{ galleryStore.filters.category_ids.length }})</span>
          <span>🏷️</span>
        </button>

        <div
          v-if="isCategoryPopoverOpen"
          class="absolute left-0 top-full mt-1.5 w-56 p-2 rounded-xl border border-slate-200 bg-white shadow-xl dark:border-white/10 dark:bg-slate-900 z-30 space-y-1"
        >
          <div
            v-for="cat in galleryStore.categories"
            :key="cat.id"
            @click="toggleCategory(cat.id)"
            class="flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-100 dark:hover:bg-white/5 cursor-pointer"
          >
            <input
              type="checkbox"
              :checked="galleryStore.filters.category_ids.includes(cat.id)"
              class="rounded border-slate-300 text-sky-500"
              @click.stop
              @change="toggleCategory(cat.id)"
            />
            <span class="truncate">{{ cat.name }}</span>
          </div>
          <div v-if="galleryStore.categories.length === 0" class="p-2 text-slate-400 text-center">
            Keine Kategorien angelegt
          </div>
        </div>
      </div>

      <!-- Thumbnail Size & Reset -->
      <div class="flex items-center gap-2 justify-end">
        <div class="inline-flex rounded-xl border border-slate-300/80 p-0.5 bg-white/80 dark:border-white/10 dark:bg-slate-900/80">
          <button
            v-for="size in (['sm', 'md', 'lg'] as const)"
            :key="size"
            type="button"
            @click="galleryStore.filters.thumb_size = size"
            :class="[
              'px-2 py-1 rounded-lg text-[10px] font-bold uppercase transition-colors',
              galleryStore.filters.thumb_size === size
                ? 'bg-sky-500 text-white'
                : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white',
            ]"
          >
            {{ size }}
          </button>
        </div>

        <button
          type="button"
          @click="galleryStore.resetFilters"
          class="p-2 rounded-xl border border-slate-200 bg-white/80 hover:bg-slate-100 text-slate-600 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-400 dark:hover:bg-white/10"
          title="Filter zurücksetzen"
        >
          🔄
        </button>
      </div>
    </div>
  </div>
</template>
