<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useGalleryStore } from '@/stores/gallery'

const galleryStore = useGalleryStore()
const isCategoryPopoverOpen = ref(false)
const popoverRef = ref<HTMLElement | null>(null)

function handleClickOutside(event: MouseEvent) {
  if (popoverRef.value && !popoverRef.value.contains(event.target as Node)) {
    isCategoryPopoverOpen.value = false
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && isCategoryPopoverOpen.value) {
    isCategoryPopoverOpen.value = false
    event.stopPropagation()
  }
}

onMounted(() => {
  galleryStore.loadCategories()
  document.addEventListener('click', handleClickOutside)
  document.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
  document.removeEventListener('keydown', handleKeydown)
})

const timePresets = [
  { value: '', label: 'All time' },
  { value: 'today', label: 'Today' },
  { value: 'yesterday', label: 'Yesterday' },
  { value: 'last_7_days', label: 'Last 7 days' },
  { value: 'last_30_days', label: 'Last 30 days' },
  { value: 'custom', label: 'Custom range...' },
]

function handleTimePresetChange() {
  if (galleryStore.filters.time_preset !== 'custom') {
    galleryStore.filters.date_from = ''
    galleryStore.filters.date_to = ''
  }
  galleryStore.fetchAssets(true)
}

function setDateRangePreset(days: number) {
  const end = new Date()
  const start = new Date()
  if (days > 0) {
    start.setDate(start.getDate() - days)
  }
  galleryStore.filters.date_from = start.toISOString().split('T')[0]
  galleryStore.filters.date_to = end.toISOString().split('T')[0]
  galleryStore.fetchAssets(true)
}

function clearDateRange() {
  galleryStore.filters.date_from = ''
  galleryStore.filters.date_to = ''
  galleryStore.fetchAssets(true)
}

function toggleStacksCollapse() {
  galleryStore.filters.collapse_stacks = !galleryStore.filters.collapse_stacks
  if (galleryStore.filters.collapse_stacks) {
    galleryStore.collapseAllStacks()
  } else {
    galleryStore.expandAllStacks()
  }
  galleryStore.fetchAssets(true)
}

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
  <div class="relative z-30 space-y-3 p-4 rounded-2xl border border-slate-200/80 bg-white/70 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/70 shadow-sm text-xs">
    <!-- Top Filter Row: Search & Selects -->
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-2.5">
      <!-- Search Input -->
      <div class="lg:col-span-2">
        <input
          type="text"
          v-model="galleryStore.filters.q"
          @input="galleryStore.fetchAssets(true)"
          placeholder="Search prompt..."
          class="w-full rounded-xl border border-slate-300/80 bg-white/80 px-3 py-2 text-xs text-slate-900 placeholder-slate-400 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
        />
      </div>

      <!-- Time Preset -->
      <div>
        <select
          v-model="galleryStore.filters.time_preset"
          @change="handleTimePresetChange"
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
          <option :value="null">All ratings</option>
          <option :value="5">⭐⭐⭐⭐⭐ (5 stars)</option>
          <option :value="4">⭐⭐⭐⭐ (min. 4 stars)</option>
          <option :value="3">⭐⭐⭐ (min. 3 stars)</option>
          <option :value="1">⭐ (min. 1 star)</option>
        </select>
      </div>

      <!-- Categories Popover -->
      <div class="relative" ref="popoverRef">
        <button
          type="button"
          @click="isCategoryPopoverOpen = !isCategoryPopoverOpen"
          class="w-full flex items-center justify-between rounded-xl border border-slate-300/80 bg-white/80 px-3 py-2 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100"
        >
          <span>Categories ({{ galleryStore.filters.category_ids.length }})</span>
          <span>🏷️</span>
        </button>

        <div
          v-if="isCategoryPopoverOpen"
          class="absolute left-0 top-full mt-1.5 w-60 p-2 rounded-xl border border-slate-200 bg-white shadow-2xl dark:border-white/10 dark:bg-slate-900 z-50 space-y-1"
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
            No categories created
          </div>
        </div>
      </div>

      <!-- Stacks, Thumbnail Size & Reset -->
      <div class="flex items-center gap-2 justify-end">
        <!-- Stacks Collapse/Expand Toggle -->
        <button
          type="button"
          @click="toggleStacksCollapse"
          :class="[
            'px-2.5 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition-colors',
            galleryStore.filters.collapse_stacks
              ? 'border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-300'
              : 'border-slate-300/80 bg-white/80 text-slate-600 hover:text-slate-900 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-300 dark:hover:text-white',
          ]"
          :title="galleryStore.filters.collapse_stacks ? 'Stacks collapsed into covers (Click to expand all)' : 'Stacks expanded (Click to collapse)'"
        >
          <span>🥞</span>
          <span class="hidden sm:inline">{{ galleryStore.filters.collapse_stacks ? 'Stacked' : 'Expanded' }}</span>
        </button>

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
          title="Reset filters"
        >
          🔄
        </button>
      </div>
    </div>

    <!-- Custom Date Range Panel -->
    <div
      v-if="galleryStore.filters.time_preset === 'custom'"
      class="pt-2 border-t border-slate-200/60 dark:border-white/10 flex flex-wrap items-center gap-3 animate-in fade-in slide-in-from-top-2 duration-150"
    >
      <div class="flex items-center gap-1.5 font-semibold text-slate-700 dark:text-slate-300">
        <span>📅</span>
        <span>Date Range:</span>
      </div>

      <div class="flex items-center gap-2">
        <label class="text-slate-500 dark:text-slate-400">From</label>
        <input
          type="date"
          v-model="galleryStore.filters.date_from"
          @change="galleryStore.fetchAssets(true)"
          class="rounded-xl border border-slate-300/80 bg-white/90 px-2.5 py-1 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900/90 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
        />
      </div>

      <div class="flex items-center gap-2">
        <label class="text-slate-500 dark:text-slate-400">To</label>
        <input
          type="date"
          v-model="galleryStore.filters.date_to"
          @change="galleryStore.fetchAssets(true)"
          class="rounded-xl border border-slate-300/80 bg-white/90 px-2.5 py-1 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900/90 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
        />
      </div>

      <div class="flex items-center gap-1.5 ml-auto">
        <button
          type="button"
          @click="setDateRangePreset(0)"
          class="px-2 py-0.5 rounded-lg border border-slate-200 dark:border-white/10 bg-slate-100/80 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-[11px] text-slate-600 dark:text-slate-300 transition-colors"
        >
          Today
        </button>
        <button
          type="button"
          @click="setDateRangePreset(7)"
          class="px-2 py-0.5 rounded-lg border border-slate-200 dark:border-white/10 bg-slate-100/80 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-[11px] text-slate-600 dark:text-slate-300 transition-colors"
        >
          Last 7d
        </button>
        <button
          type="button"
          @click="setDateRangePreset(30)"
          class="px-2 py-0.5 rounded-lg border border-slate-200 dark:border-white/10 bg-slate-100/80 dark:bg-white/5 hover:bg-slate-200 dark:hover:bg-white/10 text-[11px] text-slate-600 dark:text-slate-300 transition-colors"
        >
          Last 30d
        </button>
        <button
          v-if="galleryStore.filters.date_from || galleryStore.filters.date_to"
          type="button"
          @click="clearDateRange"
          class="px-2 py-0.5 rounded-lg border border-rose-400/30 bg-rose-500/10 hover:bg-rose-500/20 text-rose-500 dark:text-rose-400 text-[11px] transition-colors"
        >
          Clear
        </button>
      </div>
    </div>
  </div>
</template>
