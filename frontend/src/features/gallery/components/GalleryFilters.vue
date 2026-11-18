<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useGalleryStore } from '@/stores/gallery'
import { CalendarRange, Search, X } from 'lucide-vue-next'
import Button from '@/components/ui/Button.vue'
import IconButton from '@/components/ui/IconButton.vue'
import Input from '@/components/ui/Input.vue'
import Select from '@/components/ui/Select.vue'

const galleryStore = useGalleryStore()
const isCategoryPopoverOpen = ref(false)
const popoverRef = ref<HTMLElement | null>(null)
const isPresetsOpen = ref(false)
const presetsRef = ref<HTMLElement | null>(null)
const presetName = ref('')
const isMoreOpen = ref(
  !!(galleryStore.filters.provider || galleryStore.filters.model || galleryStore.filters.profile_name)
)

const moreFilterCount = computed(
  () => [galleryStore.filters.provider, galleryStore.filters.model, galleryStore.filters.profile_name].filter(Boolean).length
)

function handleClickOutside(event: MouseEvent) {
  if (popoverRef.value && !popoverRef.value.contains(event.target as Node)) {
    isCategoryPopoverOpen.value = false
  }
  if (presetsRef.value && !presetsRef.value.contains(event.target as Node)) {
    isPresetsOpen.value = false
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape' && (isCategoryPopoverOpen.value || isPresetsOpen.value)) {
    isCategoryPopoverOpen.value = false
    isPresetsOpen.value = false
    event.stopPropagation()
  }
}

function setFacet(key: 'provider' | 'model' | 'profile_name', value: string) {
  galleryStore.filters[key] = value
  galleryStore.fetchAssets(true)
}

async function handleSavePreset() {
  if (!presetName.value.trim()) return
  await galleryStore.savePreset(presetName.value)
  presetName.value = ''
}

function handleApplyPreset(preset: (typeof galleryStore.presets)[number]) {
  galleryStore.applyPreset(preset)
  isPresetsOpen.value = false
  isMoreOpen.value = isMoreOpen.value || moreFilterCount.value > 0
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

function handleTimePresetChange(value: string | number) {
  galleryStore.filters.time_preset = String(value) as typeof galleryStore.filters.time_preset
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

// Rating select combines "minimum stars" and "unrated only" into one control.
const ratingFilter = computed<string>({
  get() {
    if (galleryStore.filters.unrated) return 'unrated'
    return galleryStore.filters.min_rating ? String(galleryStore.filters.min_rating) : ''
  },
  set(value: string) {
    galleryStore.filters.unrated = value === 'unrated'
    galleryStore.filters.min_rating = value && value !== 'unrated' ? Number(value) : null
    galleryStore.fetchAssets(true)
  },
})

function clearSearch() {
  galleryStore.filters.q = ''
  galleryStore.fetchAssets(true)
}

function toggleFit() {
  galleryStore.filters.thumb_fit = galleryStore.filters.thumb_fit === 'contain' ? 'cover' : 'contain'
}

const resultSummary = computed(() => {
  const loaded = galleryStore.assets.length
  const total = galleryStore.total
  if (!galleryStore.hasLoadedOnce) return ''
  const base = `${total} ${total === 1 ? 'image' : 'images'}`
  return loaded < total ? `${base} · ${loaded} loaded` : base
})

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
  <div class="relative z-30 space-y-2.5 p-3 rounded-2xl border border-slate-200/80 bg-white/70 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/70 shadow-sm text-xs">
    <!-- Top Filter Row: Search & Selects -->
    <div class="flex flex-wrap items-center gap-2">
      <!-- Search Input -->
      <Input
        v-model="galleryStore.filters.q"
        size="sm"
        class="min-w-[200px] flex-[2_1_260px]"
        placeholder="Search prompts..."
        aria-label="Search prompts"
        data-testid="gallery-search"
        @input="galleryStore.searchDebounced()"
        @keydown.enter="galleryStore.fetchAssets(true)"
      >
        <template #prefix><Search class="size-3.5" aria-hidden="true" /></template>
        <template v-if="galleryStore.filters.q" #suffix>
          <IconButton label="Clear search" size="xs" @click="clearSearch">
            <X class="size-3.5" aria-hidden="true" />
          </IconButton>
        </template>
      </Input>

      <!-- Time Preset -->
      <Select
        :model-value="galleryStore.filters.time_preset"
        :options="timePresets"
        size="sm"
        class="min-w-[140px] flex-[1_1_150px]"
        aria-label="Time range"
        @update:model-value="handleTimePresetChange"
      />

      <!-- Min Rating -->
      <Select v-model="ratingFilter" size="sm" class="min-w-[140px] flex-[1_1_150px]" aria-label="Rating">
          <option value="">All ratings</option>
          <option value="5">★★★★★ 5 stars</option>
          <option value="4">★★★★ min. 4 stars</option>
          <option value="3">★★★ min. 3 stars</option>
          <option value="1">★ min. 1 star</option>
          <option value="unrated">Unrated only</option>
      </Select>

      <!-- Categories Popover -->
      <div class="relative min-w-[140px] flex-[1_1_150px]" ref="popoverRef">
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
      <div class="ml-auto flex shrink-0 items-center gap-2">
        <!-- More filters (provider / model / profile) -->
        <button
          type="button"
          @click="isMoreOpen = !isMoreOpen"
          :class="[
            'px-2.5 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer',
            isMoreOpen || moreFilterCount > 0 ? 'border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-300' : 'border-slate-300/80 bg-white/80 text-slate-600 hover:text-slate-900 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-300 dark:hover:text-white',
          ]"
          title="Filter by provider, model or profile"
          data-testid="gallery-more-filters"
        >
          <span>⚙️</span>
          <span class="hidden sm:inline">More</span>
          <span v-if="moreFilterCount" class="rounded-full bg-sky-500 px-1.5 text-[10px] font-bold text-white">{{ moreFilterCount }}</span>
        </button>

        <!-- Saved filter presets -->
        <div class="relative" ref="presetsRef">
          <button
            type="button"
            @click="isPresetsOpen = !isPresetsOpen"
            :class="[
              'px-2.5 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer',
              isPresetsOpen ? 'border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-300' : 'border-slate-300/80 bg-white/80 text-slate-600 hover:text-slate-900 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-300 dark:hover:text-white',
            ]"
            title="Saved filter presets"
            data-testid="gallery-presets"
          >
            <span>🔖</span>
            <span class="hidden sm:inline">Presets</span>
          </button>
          <div
            v-if="isPresetsOpen"
            class="absolute right-0 top-full z-50 mt-1.5 w-72 space-y-2 rounded-xl border border-slate-200 bg-white p-2 shadow-2xl dark:border-white/10 dark:bg-slate-900"
          >
            <div v-if="galleryStore.presets.length === 0" class="px-2 py-1.5 text-slate-400">
              No presets yet. Set up filters and save them here.
            </div>
            <div
              v-for="preset in galleryStore.presets"
              :key="preset.id"
              class="group flex items-center gap-1 rounded-lg hover:bg-slate-100 dark:hover:bg-white/5"
            >
              <button
                type="button"
                @click="handleApplyPreset(preset)"
                class="min-w-0 flex-1 cursor-pointer truncate px-2 py-1.5 text-left text-slate-700 dark:text-slate-200"
                :title="`Apply preset ${preset.name}`"
              >
                {{ preset.name }}
              </button>
              <button
                type="button"
                @click.stop="galleryStore.deletePreset(preset.id)"
                class="cursor-pointer px-2 py-1 text-slate-400 opacity-0 transition-opacity hover:text-rose-500 group-hover:opacity-100"
                title="Delete preset"
                aria-label="Delete preset"
              >
                ✕
              </button>
            </div>
            <form class="flex gap-1.5 border-t border-slate-200 pt-2 dark:border-white/10" @submit.prevent="handleSavePreset">
              <input
                v-model="presetName"
                maxlength="40"
                placeholder="Save current filters as…"
                class="min-w-0 flex-1 rounded-lg border border-slate-300/80 bg-white px-2 py-1.5 text-xs text-slate-900 focus:outline-none focus:ring-1 focus:ring-sky-500 dark:border-white/10 dark:bg-slate-950 dark:text-slate-100"
                data-testid="gallery-preset-name"
              />
              <button
                type="submit"
                :disabled="!presetName.trim()"
                class="cursor-pointer rounded-lg bg-sky-500 px-2.5 py-1.5 text-xs font-semibold text-white disabled:cursor-not-allowed disabled:opacity-40"
              >
                Save
              </button>
            </form>
          </div>
        </div>

        <!-- Group by day -->
        <button
          type="button"
          @click="galleryStore.filters.group_by_date = galleryStore.filters.group_by_date === false"
          :class="[
            'px-2.5 py-1.5 rounded-xl border text-xs font-medium flex items-center gap-1.5 transition-colors cursor-pointer',
            galleryStore.filters.group_by_date !== false ? 'border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-300' : 'border-slate-300/80 bg-white/80 text-slate-600 hover:text-slate-900 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-300 dark:hover:text-white',
          ]"
          :title="galleryStore.filters.group_by_date !== false ? 'Grouped by day (click for one continuous grid)' : 'Group images by day'"
          data-testid="gallery-group-toggle"
        >
          <span>📅</span>
          <span class="hidden sm:inline">Days</span>
        </button>

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

        <button
          type="button"
          @click="toggleFit"
          :class="[
            'px-2.5 py-1.5 rounded-xl border text-xs font-medium transition-colors cursor-pointer',
            galleryStore.filters.thumb_fit === 'contain'
              ? 'border-sky-500/40 bg-sky-500/10 text-sky-600 dark:text-sky-300'
              : 'border-slate-300/80 bg-white/80 text-slate-600 hover:text-slate-900 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-300 dark:hover:text-white',
          ]"
          :title="galleryStore.filters.thumb_fit === 'contain' ? 'Showing full images (click to crop to squares)' : 'Thumbnails cropped to squares (click to show full images)'"
        >
          {{ galleryStore.filters.thumb_fit === 'contain' ? 'Fit' : 'Crop' }}
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

      </div>
    </div>

    <!-- More filters row -->
    <div v-if="isMoreOpen" class="flex flex-wrap items-center gap-2 border-t border-slate-200/60 pt-2.5 dark:border-white/10">
      <Select
        :model-value="galleryStore.filters.provider || ''"
        size="sm"
        class="min-w-[140px] flex-[1_1_160px]"
        aria-label="Provider"
        data-testid="gallery-filter-provider"
        @update:model-value="setFacet('provider', String($event))"
      >
          <option value="">All providers</option>
          <option v-for="item in galleryStore.facets.providers" :key="item" :value="item">{{ item }}</option>
      </Select>
      <Select
        :model-value="galleryStore.filters.model || ''"
        size="sm"
        class="min-w-[160px] flex-[2_1_220px]"
        aria-label="Model"
        data-testid="gallery-filter-model"
        @update:model-value="setFacet('model', String($event))"
      >
          <option value="">All models</option>
          <option v-for="item in galleryStore.facets.models" :key="item" :value="item">{{ item }}</option>
      </Select>
      <Select
        :model-value="galleryStore.filters.profile_name || ''"
        size="sm"
        class="min-w-[140px] flex-[1_1_160px]"
        aria-label="Profile"
        data-testid="gallery-filter-profile"
        @update:model-value="setFacet('profile_name', String($event))"
      >
          <option value="">All profiles</option>
          <option v-for="item in galleryStore.facets.profiles" :key="item" :value="item">{{ item }}</option>
      </Select>
    </div>

    <!-- Result summary & reset -->
    <div class="flex flex-wrap items-center justify-between gap-2 text-[11px] text-slate-500 dark:text-slate-400">
      <span data-testid="gallery-result-summary">{{ resultSummary }}</span>
      <span class="hidden flex-1 text-center text-slate-400 lg:inline" data-testid="gallery-keyboard-hint">
        Drag to select · hover + <kbd class="font-mono">0–5</kbd> rate · <kbd class="font-mono">Space</kbd> select · <kbd class="font-mono">Enter</kbd> open · <kbd class="font-mono">Ctrl+A</kbd> all
      </span>
      <button
        v-if="galleryStore.activeFilterCount > 0"
        type="button"
        @click="galleryStore.resetFilters"
        class="cursor-pointer rounded-lg px-2 py-0.5 font-medium text-sky-600 hover:bg-sky-500/10 dark:text-sky-400"
      >
        Reset {{ galleryStore.activeFilterCount }} {{ galleryStore.activeFilterCount === 1 ? 'filter' : 'filters' }}
      </button>
    </div>

    <!-- Custom Date Range Panel -->
    <div
      v-if="galleryStore.filters.time_preset === 'custom'"
      class="pt-2 border-t border-slate-200/60 dark:border-white/10 flex flex-wrap items-center gap-3 animate-in fade-in slide-in-from-top-2 duration-150"
    >
      <div class="flex items-center gap-1.5 font-semibold text-slate-700 dark:text-slate-300">
        <CalendarRange class="size-4" aria-hidden="true" />
        <span>Date Range:</span>
      </div>

      <Input
        v-model="galleryStore.filters.date_from"
        type="date"
        size="sm"
        aria-label="From date"
        @change="galleryStore.fetchAssets(true)"
      />

      <Input
        v-model="galleryStore.filters.date_to"
        type="date"
        size="sm"
        aria-label="To date"
        @change="galleryStore.fetchAssets(true)"
      />

      <div class="flex items-center gap-1.5 ml-auto">
        <Button variant="secondary" size="xs" @click="setDateRangePreset(0)">Today</Button>
        <Button variant="secondary" size="xs" @click="setDateRangePreset(7)">Last 7d</Button>
        <Button variant="secondary" size="xs" @click="setDateRangePreset(30)">Last 30d</Button>
        <Button
          v-if="galleryStore.filters.date_from || galleryStore.filters.date_to"
          variant="danger-ghost"
          size="xs"
          @click="clearDateRange"
        >
          Clear
        </Button>
      </div>
    </div>
  </div>
</template>
