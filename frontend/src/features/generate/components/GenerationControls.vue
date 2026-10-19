<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { useGenerateStore } from '@/stores/generate'
import { useProfilesStore } from '@/stores/profiles'
import { galleryApi } from '@/api/gallery'
import type { Category } from '@/types'

const generateStore = useGenerateStore()
const profilesStore = useProfilesStore()

const availableCategories = ref<Category[]>([])
const isCategoryDropdownOpen = ref(false)
const categoryDropdownRef = ref<HTMLElement | null>(null)

async function loadCategories() {
  try {
    availableCategories.value = await galleryApi.listCategories()
  } catch (_e) {
    availableCategories.value = []
  }
}

function handleClickOutside(e: MouseEvent) {
  if (categoryDropdownRef.value && !categoryDropdownRef.value.contains(e.target as Node)) {
    isCategoryDropdownOpen.value = false
  }
}

onMounted(async () => {
  document.addEventListener('click', handleClickOutside)
  await Promise.all([
    generateStore.loadModelsAndStyles(),
    profilesStore.fetchProfiles(),
    loadCategories(),
  ])
  if (generateStore.selectedProfileId) {
    const profile = profilesStore.profiles.find((p) => p.id === Number(generateStore.selectedProfileId))
    if (profile) {
      generateStore.applyProfileDefaults(profile)
    }
  }
})

onUnmounted(() => {
  document.removeEventListener('click', handleClickOutside)
})

watch(
  () => generateStore.selectedProfileId,
  (profileId) => {
    if (!profileId) {
      generateStore.clearProfileDefaults()
      return
    }
    const profile = profilesStore.profiles.find((p) => p.id === Number(profileId))
    if (profile) {
      generateStore.applyProfileDefaults(profile)
    }
  }
)

function isLockedCategory(catId: number): boolean {
  return generateStore.profileLockedCategoryIds.includes(catId)
}

function isCategorySelected(catId: number): boolean {
  return generateStore.selectedCategoryIds.includes(catId)
}

function toggleCategory(catId: number) {
  if (isLockedCategory(catId)) return
  if (generateStore.selectedCategoryIds.includes(catId)) {
    generateStore.selectedCategoryIds = generateStore.selectedCategoryIds.filter((id) => id !== catId)
  } else {
    generateStore.selectedCategoryIds.push(catId)
  }
}

function handleCategoryItemClick(catId: number) {
  if (isLockedCategory(catId)) return
  toggleCategory(catId)
}

const selectedCategorySummaryText = computed(() => {
  const count = generateStore.selectedCategoryIds.length
  if (count === 0) return 'Categories (0)'
  if (count === 1) {
    const cat = availableCategories.value.find((c) => c.id === generateStore.selectedCategoryIds[0])
    return cat ? cat.name : '1 category'
  }
  return `Categories (${count})`
})

const selectedCategorySummaryTitle = computed(() => {
  if (generateStore.selectedCategoryIds.length === 0) return 'No categories selected'
  const names = generateStore.selectedCategoryIds
    .map((id) => availableCategories.value.find((c) => c.id === id)?.name)
    .filter(Boolean)
  return `Selected categories: ${names.join(', ')}`
})
</script>

<template>
  <div class="flex flex-wrap items-center gap-2 text-xs">
    <!-- Model Config Selector -->
    <div class="min-w-[160px] flex-1 max-w-xs">
      <select
        v-model.number="generateStore.selectedModelConfigId"
        class="w-full rounded-xl border border-slate-300/80 bg-white/80 px-2.5 py-1.5 text-xs text-slate-800 transition-all dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/40 cursor-pointer shadow-sm"
      >
        <option :value="null">Select model...</option>
        <option
          v-for="model in generateStore.activeModels"
          :key="model.id"
          :value="model.id"
        >
          {{ model.name }} ({{ model.provider.toUpperCase() }})
        </option>
      </select>
    </div>

    <!-- Profile Selector -->
    <div class="min-w-[140px] flex-1 max-w-xs">
      <select
        v-model.number="generateStore.selectedProfileId"
        class="w-full rounded-xl border border-slate-300/80 bg-white/80 px-2.5 py-1.5 text-xs text-slate-800 transition-all dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/40 cursor-pointer shadow-sm"
        title="Select profile (Optional)"
      >
        <option :value="null">No profile (Default)</option>
        <option
          v-for="profile in profilesStore.profiles"
          :key="profile.id"
          :value="profile.id"
        >
          {{ profile.name }}
        </option>
      </select>
    </div>

    <!-- Category Multi-Select Combobox -->
    <div class="min-w-[140px] flex-1 max-w-xs relative" ref="categoryDropdownRef">
      <button
        type="button"
        @click="isCategoryDropdownOpen = !isCategoryDropdownOpen"
        class="w-full flex items-center justify-between rounded-xl border border-slate-300/80 bg-white/80 px-2.5 py-1.5 text-xs text-slate-800 transition-all dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-200 focus:outline-none focus:ring-2 focus:ring-sky-500/40 cursor-pointer shadow-sm"
        :title="selectedCategorySummaryTitle"
      >
        <span class="truncate flex items-center gap-1.5 min-w-0">
          <span class="text-xs">🏷️</span>
          <span class="truncate font-medium">{{ selectedCategorySummaryText }}</span>
        </span>
        <span class="text-[10px] text-slate-400 shrink-0 ml-1">▼</span>
      </button>

      <!-- Dropdown Popover -->
      <div
        v-if="isCategoryDropdownOpen"
        class="absolute left-0 top-full mt-1.5 w-64 max-h-60 overflow-y-auto p-1.5 rounded-xl border border-slate-200 bg-white shadow-xl dark:border-white/10 dark:bg-slate-900 z-50 space-y-0.5 text-xs"
      >
        <div
          v-for="cat in availableCategories"
          :key="cat.id"
          @click="handleCategoryItemClick(cat.id)"
          :class="[
            'flex items-center justify-between gap-2 px-2.5 py-1.5 rounded-lg transition-colors select-none',
            isLockedCategory(cat.id)
              ? 'bg-slate-50 dark:bg-slate-800/40 cursor-not-allowed text-slate-500 dark:text-slate-400'
              : 'hover:bg-slate-100 dark:hover:bg-white/5 cursor-pointer text-slate-700 dark:text-slate-200',
          ]"
          :title="isLockedCategory(cat.id) ? 'Configured in active profile (cannot be deselected)' : ''"
        >
          <div class="flex items-center gap-2 min-w-0">
            <input
              type="checkbox"
              :checked="isCategorySelected(cat.id)"
              :disabled="isLockedCategory(cat.id)"
              class="rounded border-slate-300 text-sky-500 focus:ring-sky-400 cursor-pointer disabled:cursor-not-allowed"
              @click.stop
              @change="toggleCategory(cat.id)"
            />
            <span class="truncate text-xs font-medium">{{ cat.name }}</span>
          </div>
          <span
            v-if="isLockedCategory(cat.id)"
            class="text-[10px] px-1.5 py-0.5 rounded bg-indigo-100 dark:bg-indigo-950/70 text-indigo-600 dark:text-indigo-400 font-medium shrink-0"
            title="Fixed by active profile"
          >
            🔒 Profile
          </span>
        </div>

        <div
          v-if="availableCategories.length === 0"
          class="p-2.5 text-center text-slate-400 text-xs italic"
        >
          No categories available
        </div>
      </div>
    </div>
  </div>
</template>
