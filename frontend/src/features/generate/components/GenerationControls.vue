<script setup lang="ts">
import { computed, ref, watch, onMounted } from 'vue'
import { useGenerateStore } from '@/stores/generate'
import { useProfilesStore } from '@/stores/profiles'
import StylePickerModal from './StylePickerModal.vue'

const generateStore = useGenerateStore()
const profilesStore = useProfilesStore()

const isStyleModalOpen = ref(false)

onMounted(async () => {
  await Promise.all([
    generateStore.loadModelsAndStyles(),
    profilesStore.fetchProfiles(),
  ])
  if (generateStore.selectedProfileId) {
    const profile = profilesStore.profiles.find((p) => p.id === Number(generateStore.selectedProfileId))
    if (profile) {
      generateStore.applyProfileDefaults(profile)
    }
  }
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


const aspectRatios = ['1:1', '16:9', '9:16', '4:3', '3:4', '21:9']
const resolutions = ['0.5K', '1K', '2K', '4K']

const selectedStyleName = computed(() => {
  if (!generateStore.selectedStyleId) return 'Kein Style'
  const style = generateStore.styles.find((s) => String(s.id) === String(generateStore.selectedStyleId))
  return style ? style.name : 'Style aktiv'
})
</script>

<template>
  <div class="flex flex-wrap items-center justify-between gap-2.5 text-xs">
    <!-- Left: Model & Profile selection -->
    <div class="flex flex-wrap items-center gap-2 flex-1 min-w-[280px]">
      <!-- Model Config Selector -->
      <div class="min-w-[160px] flex-1 max-w-xs">
        <select
          v-model.number="generateStore.selectedModelConfigId"
          class="w-full rounded-xl border border-slate-300/80 bg-white/80 px-2.5 py-1.5 text-xs font-medium text-slate-900 transition-all dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500/40 cursor-pointer shadow-sm"
          title="Modell wählen"
        >
          <option :value="null" disabled>Modell wählen</option>
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
          title="Profil wählen (Optional)"
        >
          <option :value="null">Kein Profil (Standard)</option>
          <option
            v-for="profile in profilesStore.profiles"
            :key="profile.id"
            :value="profile.id"
          >
            {{ profile.name }}
          </option>
        </select>
      </div>
    </div>

    <!-- Center/Right: Aspect Ratio, Resolution & Style Trigger -->
    <div class="flex flex-wrap items-center gap-2 shrink-0">
      <!-- Aspect Ratio Pills -->
      <div class="hidden sm:flex items-center gap-1 bg-slate-100 dark:bg-slate-800/80 p-0.5 rounded-xl border border-slate-200 dark:border-white/10">
        <button
          v-for="ar in aspectRatios"
          :key="ar"
          type="button"
          @click="generateStore.aspectRatio = ar"
          :class="[
            'px-2 py-1 rounded-lg text-[11px] font-semibold transition-all cursor-pointer',
            generateStore.aspectRatio === ar
              ? 'bg-sky-500 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white',
          ]"
        >
          {{ ar }}
        </button>
      </div>

      <!-- Fallback Ratio Select for narrow screens -->
      <div class="sm:hidden">
        <select
          v-model="generateStore.aspectRatio"
          class="rounded-xl border border-slate-300/80 bg-white/80 px-2 py-1.5 text-xs text-slate-800 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-200"
        >
          <option v-for="ar in aspectRatios" :key="ar" :value="ar">{{ ar }}</option>
        </select>
      </div>

      <!-- Resolution Pills -->
      <div class="hidden md:flex items-center gap-1 bg-slate-100 dark:bg-slate-800/80 p-0.5 rounded-xl border border-slate-200 dark:border-white/10">
        <button
          v-for="res in resolutions"
          :key="res"
          type="button"
          @click="generateStore.resolution = res"
          :class="[
            'px-2 py-1 rounded-lg text-[11px] font-semibold transition-all cursor-pointer',
            generateStore.resolution === res
              ? 'bg-sky-500 text-white shadow-sm'
              : 'text-slate-600 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white',
          ]"
        >
          {{ res }}
        </button>
      </div>

      <!-- Style Preset Trigger -->
      <button
        type="button"
        @click="isStyleModalOpen = true"
        class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border border-slate-300/80 bg-white/80 text-slate-700 hover:bg-white dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-200 dark:hover:bg-slate-800 transition-colors shadow-sm cursor-pointer"
        title="Style-Vorlage wählen"
      >
        <span class="text-xs text-sky-500">🎨</span>
        <span class="truncate max-w-[100px] text-[11px] font-medium">{{ selectedStyleName }}</span>
      </button>
    </div>

    <!-- Style Picker Modal -->
    <StylePickerModal
      :open="isStyleModalOpen"
      @update:open="isStyleModalOpen = $event"
    />
  </div>
</template>
