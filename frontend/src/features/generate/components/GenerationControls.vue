<script setup lang="ts">
import { computed, ref, onMounted } from 'vue'
import { useGenerateStore } from '@/stores/generate'
import { useProfilesStore } from '@/stores/profiles'
import StylePickerModal from './StylePickerModal.vue'

const generateStore = useGenerateStore()
const profilesStore = useProfilesStore()

const isStyleModalOpen = ref(false)

onMounted(() => {
  generateStore.loadModelsAndStyles()
  profilesStore.fetchProfiles()
})

const aspectRatios = [
  { value: '1:1', label: '1:1 Quadrat' },
  { value: '16:9', label: '16:9 Quer' },
  { value: '9:16', label: '9:16 Hoch' },
  { value: '4:3', label: '4:3 Klassisch' },
  { value: '3:4', label: '3:4 Portrait' },
  { value: '21:9', label: '21:9 Panorama' },
]

const resolutions = ['0.5K', '1K', '2K', '4K']

function randomizeSeed() {
  generateStore.seed = String(Math.floor(Math.random() * 1000000000))
}

function clearSeed() {
  generateStore.seed = ''
}

const selectedStyleName = computed(() => {
  if (!generateStore.selectedStyleId) return 'Standard (Kein Style)'
  const style = generateStore.styles.find((s) => String(s.id) === String(generateStore.selectedStyleId))
  return style ? style.name : 'Gewählter Style'
})
</script>

<template>
  <div class="space-y-4 text-xs">
    <!-- Row 1: Model & Profile selection -->
    <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <!-- Model Config Selector -->
      <div>
        <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500 dark:text-slate-400 mb-1.5">
          Modell
        </label>
        <select
          v-model="generateStore.selectedModelConfigId"
          class="w-full rounded-xl border border-slate-300/80 bg-white/80 px-3 py-2 text-xs text-slate-900 transition-all dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500/40"
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
      <div>
        <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500 dark:text-slate-400 mb-1.5">
          Profil (Optional)
        </label>
        <select
          v-model="generateStore.selectedProfileId"
          class="w-full rounded-xl border border-slate-300/80 bg-white/80 px-3 py-2 text-xs text-slate-900 transition-all dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500/40"
        >
          <option :value="null">Kein Profil aktiv</option>
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

    <!-- Row 2: Aspect Ratio Buttons -->
    <div>
      <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500 dark:text-slate-400 mb-1.5">
        Seitenverhältnis
      </label>
      <div class="flex flex-wrap gap-1.5">
        <button
          v-for="ar in aspectRatios"
          :key="ar.value"
          type="button"
          @click="generateStore.aspectRatio = ar.value"
          :class="[
            'px-2.5 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer border',
            generateStore.aspectRatio === ar.value
              ? 'bg-sky-500 text-white border-sky-500 shadow-sm shadow-sky-500/30'
              : 'bg-white/60 text-slate-700 border-slate-200 hover:bg-slate-100 dark:bg-slate-900/60 dark:text-slate-300 dark:border-white/10 dark:hover:bg-white/10',
          ]"
        >
          {{ ar.value }}
        </button>
      </div>
    </div>

    <!-- Row 3: Resolution & Style Picker & Seed -->
    <div class="grid grid-cols-1 sm:grid-cols-3 gap-3 items-end">
      <!-- Resolution -->
      <div>
        <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500 dark:text-slate-400 mb-1.5">
          Auflösung
        </label>
        <div class="flex gap-1">
          <button
            v-for="res in resolutions"
            :key="res"
            type="button"
            @click="generateStore.resolution = res"
            :class="[
              'flex-1 py-1 rounded-lg text-xs font-semibold transition-all cursor-pointer border text-center',
              generateStore.resolution === res
                ? 'bg-sky-500 text-white border-sky-500 shadow-sm'
                : 'bg-white/60 text-slate-700 border-slate-200 hover:bg-slate-100 dark:bg-slate-900/60 dark:text-slate-300 dark:border-white/10 dark:hover:bg-white/10',
            ]"
          >
            {{ res }}
          </button>
        </div>
      </div>

      <!-- Style Preset Selector Trigger -->
      <div>
        <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500 dark:text-slate-400 mb-1.5">
          Style Preset
        </label>
        <button
          type="button"
          @click="isStyleModalOpen = true"
          class="w-full flex items-center justify-between px-3 py-1.5 rounded-xl border border-slate-300/80 bg-white/70 text-slate-800 hover:bg-white dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-200 dark:hover:bg-slate-800 transition-colors"
        >
          <span class="truncate">{{ selectedStyleName }}</span>
          <span class="text-xs text-sky-500">🎨</span>
        </button>
      </div>

      <!-- Seed Input -->
      <div>
        <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500 dark:text-slate-400 mb-1.5">
          Seed
        </label>
        <div class="flex gap-1.5">
          <input
            type="text"
            v-model="generateStore.seed"
            placeholder="Zufall"
            class="w-full rounded-xl border border-slate-300/80 bg-white/80 px-2.5 py-1 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
          />
          <button
            type="button"
            @click="randomizeSeed"
            class="px-2 py-1 rounded-xl bg-slate-200/80 hover:bg-slate-300 text-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-200 transition-colors shrink-0"
            title="Neuer Zufalls-Seed"
          >
            🎲
          </button>
          <button
            v-if="generateStore.seed"
            type="button"
            @click="clearSeed"
            class="px-2 py-1 rounded-xl bg-slate-200/80 hover:bg-slate-300 text-slate-700 dark:bg-slate-800 dark:hover:bg-slate-700 dark:text-slate-200 transition-colors shrink-0"
            title="Seed leeren"
          >
            ✕
          </button>
        </div>
      </div>
    </div>

    <!-- Style Picker Modal -->
    <StylePickerModal
      :open="isStyleModalOpen"
      @update:open="isStyleModalOpen = $event"
    />
  </div>
</template>
