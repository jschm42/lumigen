<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useGenerateStore, DIMENSION_PRESETS } from '@/stores/generate'
import Button from '@/components/ui/Button.vue'
import PromptEnhanceModal from './PromptEnhanceModal.vue'
import StylePickerModal from './StylePickerModal.vue'
import GalleryImagePickerModal from './GalleryImagePickerModal.vue'

const generateStore = useGenerateStore()

const isEnhanceModalOpen = ref(false)
const isStyleModalOpen = ref(false)
const isGalleryPickerOpen = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

const activeProvider = computed(() => {
  return (generateStore.selectedModel?.provider || '').toLowerCase()
})

watch(
  [() => generateStore.customWidth, () => generateStore.customHeight],
  () => {
    generateStore.syncDimensionsToPreset()
  }
)

const customUpscaleOption = computed(() => {
  const current = generateStore.upscaleModel
  if (!current || current === '__profile__' || current === '__none__') return null
  const exists = generateStore.availableUpscaleModels.some((m) => m.value === current)
  if (!exists) {
    let label = current
    if (current.startsWith('falm:')) label = `FAL Modell #${current.split(':')[1]}`
    else if (current.startsWith('local:')) label = `${current.split(':')[1]} (Lokal)`
    return { value: current, label }
  }
  return null
})


const openRouterRatios = ['', '1:1', '4:3', '4:5', '5:4', '9:16', '16:9', '21:9']
const openRouterSizes = ['', '1K', '2K', '4K']

const falRatios = ['', 'auto', '21:9', '16:9', '3:2', '4:3', '5:4', '1:1', '4:5', '3:4', '2:3', '9:16', '4:1', '1:4', '8:1', '1:8']
const falResolutions = ['', '0.5K', '1K', '2K', '4K']

const googleRatios = ['', '1:1', '1:4', '1:8', '2:3', '3:2', '3:4', '4:1', '4:3', '4:5', '5:4', '8:1', '9:16', '16:9', '21:9']
const googleResolutions = ['', '512', '1K', '2K', '4K']

const selectedStyle = computed(() => {
  if (!generateStore.selectedStyleId) return null
  return generateStore.styles.find((s) => String(s.id) === String(generateStore.selectedStyleId)) || null
})

function triggerFileInput() {
  fileInputRef.value?.click()
}

function handleFileSelect(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files) {
    Array.from(target.files).forEach((file) => {
      if (file.type.startsWith('image/')) {
        generateStore.addAttachedImage(file)
      }
    })
    target.value = ''
  }
}

function randomizeSeed() {
  generateStore.seed = String(Math.floor(Math.random() * 1000000000))
}

function clearSeed() {
  generateStore.seed = ''
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (!generateStore.isGenerating) {
      generateStore.submit()
    }
  }
}
</script>

<template>
  <div class="relative w-full rounded-2xl border border-slate-300/80 bg-white/95 p-3 sm:p-4 shadow-xl backdrop-blur-xl dark:border-white/15 dark:bg-slate-900/95 transition-all text-xs">
    <!-- Hidden File Input for Image Uploads -->
    <input
      ref="fileInputRef"
      type="file"
      multiple
      accept="image/*"
      class="hidden"
      @change="handleFileSelect"
    />

    <!-- Top: Attached Input Images Strip -->
    <div
      v-if="generateStore.attachedImages.length > 0"
      class="mb-3 pb-2.5 border-b border-slate-200/80 dark:border-white/10 flex items-center justify-between gap-3 overflow-x-auto"
    >
      <div class="flex items-center gap-2 flex-nowrap">
        <span class="text-[11px] font-semibold text-slate-500 uppercase tracking-wider shrink-0">
          Eingabebilder ({{ generateStore.attachedImages.length }}/5):
        </span>
        <div
          v-for="img in generateStore.attachedImages"
          :key="img.id"
          class="relative group w-12 h-12 rounded-xl border border-slate-300 dark:border-white/20 overflow-hidden bg-slate-900 shrink-0 shadow-sm"
        >
          <img :src="img.previewUrl" :alt="img.name || ''" class="w-full h-full object-cover" />
          <button
            type="button"
            @click="generateStore.removeAttachedImage(img.id)"
            class="absolute top-0.5 right-0.5 w-4 h-4 rounded-full bg-rose-600 text-white flex items-center justify-center text-[10px] opacity-80 hover:opacity-100 transition-opacity"
            title="Entfernen"
          >
            ✕
          </button>
        </div>

        <button
          v-if="generateStore.attachedImages.length < 5"
          type="button"
          @click="triggerFileInput"
          class="w-12 h-12 rounded-xl border border-dashed border-slate-300 dark:border-white/20 hover:border-sky-400 flex flex-col items-center justify-center text-slate-400 hover:text-sky-500 transition-colors shrink-0"
          title="Weiteres Bild hochladen"
        >
          <span class="text-base leading-none">+</span>
        </button>
      </div>

      <button
        type="button"
        @click="generateStore.clearAttachedImages"
        class="text-[11px] font-medium text-rose-500 hover:text-rose-600 dark:text-rose-400 hover:underline shrink-0"
      >
        Alle entfernen
      </button>
    </div>

    <!-- Active Style Tag Chip (if chosen) -->
    <div v-if="selectedStyle" class="mb-2 flex items-center gap-1.5 flex-wrap">
      <div class="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-lg bg-sky-100 dark:bg-sky-950/60 text-sky-800 dark:text-sky-300 border border-sky-300 dark:border-sky-800/50 text-[11px] font-medium">
        <span>🎨 {{ selectedStyle.name }}</span>
        <button
          type="button"
          @click="generateStore.selectedStyleId = null"
          class="ml-1 hover:text-rose-500 text-xs leading-none"
          title="Style entfernen"
        >
          ✕
        </button>
      </div>
    </div>

    <!-- Main Prompt Textarea Row with Quick Action Buttons -->
    <div class="flex items-end gap-2">
      <!-- Advanced Overrides Toggle Button (+) -->
      <button
        type="button"
        @click="generateStore.isAdvancedOpen = !generateStore.isAdvancedOpen"
        :class="[
          'inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border font-bold text-base transition-colors shadow-sm',
          generateStore.isAdvancedOpen
            ? 'border-sky-400 bg-sky-50 text-sky-600 dark:border-sky-500 dark:bg-sky-950/50 dark:text-sky-300'
            : 'border-slate-300/80 bg-white text-slate-700 hover:bg-slate-100 dark:border-white/10 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/20',
        ]"
        :title="generateStore.isAdvancedOpen ? 'Erweiterte Optionen schließen' : 'Erweiterte Überschreibungsoptionen öffnen'"
        :aria-expanded="generateStore.isAdvancedOpen"
      >
        {{ generateStore.isAdvancedOpen ? '−' : '+' }}
      </button>

      <!-- Input Image Picker (Paperclip) -->
      <button
        type="button"
        @click="triggerFileInput"
        class="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-300/80 bg-white text-base text-slate-700 shadow-sm transition hover:bg-slate-100 dark:border-white/10 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/20"
        title="Bilddatei als Referenzbild hochladen"
      >
        📎
      </button>

      <!-- Pick from Gallery Button -->
      <button
        type="button"
        @click="isGalleryPickerOpen = true"
        class="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-300/80 bg-white text-base text-slate-700 shadow-sm transition hover:bg-slate-100 dark:border-white/10 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/20"
        title="Eingabebild aus Galerie wählen"
      >
        🖼️
      </button>

      <!-- Style Picker Button -->
      <button
        type="button"
        @click="isStyleModalOpen = true"
        class="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-300/80 bg-white text-base text-slate-700 shadow-sm transition hover:bg-slate-100 dark:border-white/10 dark:bg-white/10 dark:text-slate-200 dark:hover:bg-white/20"
        title="Style-Vorlage auswählen"
      >
        🎨
      </button>

      <!-- Prompt Textarea -->
      <div class="relative flex-1 min-w-0">
        <textarea
          v-model="generateStore.prompt"
          @keydown="handleKeydown"
          rows="2"
          class="w-full min-h-[2.75rem] max-h-48 resize-y rounded-xl border border-slate-300/80 bg-slate-50 px-3 py-2 text-xs sm:text-sm text-slate-900 placeholder-slate-400 focus:border-sky-500 focus:bg-white focus:outline-none dark:border-white/15 dark:bg-slate-950/50 dark:text-slate-100 dark:placeholder-slate-500 dark:focus:border-sky-400 dark:focus:bg-slate-950/80"
          placeholder="Beschreibe dein gewünschtes Bild... (Enter = Generieren, Shift+Enter = Neue Zeile)"
        ></textarea>
      </div>

      <!-- Clear Button (if images or prompt) -->
      <button
        v-if="generateStore.prompt || generateStore.attachedImages.length > 0"
        type="button"
        @click="() => { generateStore.prompt = ''; generateStore.clearAttachedImages(); }"
        class="inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-slate-300/80 bg-white font-semibold text-slate-600 transition hover:bg-rose-100 hover:text-rose-700 dark:border-white/10 dark:bg-white/10 dark:text-slate-300 dark:hover:bg-rose-500/20 dark:hover:text-rose-200"
        title="Eingaben leeren"
      >
        ✕
      </button>

      <!-- Submit / Generate Button -->
      <Button
        variant="primary"
        size="md"
        :loading="generateStore.isGenerating"
        :disabled="!generateStore.prompt.trim() || generateStore.isGenerating"
        @click="generateStore.submit"
        class="h-10 px-4 shrink-0 rounded-xl font-semibold shadow-md"
        title="Generierung starten"
      >
        <template #icon>
          <span class="text-sm">⚡</span>
        </template>
        <span v-if="generateStore.isGenerating">Generiert...</span>
        <span v-else>Generieren</span>
      </Button>
    </div>

    <!-- Collapsible Negative Prompt -->
    <div v-if="generateStore.showNegativePrompt" class="mt-2.5 pt-2 border-t border-slate-200/60 dark:border-white/10">
      <div class="flex items-center gap-2">
        <span class="text-[10px] uppercase font-bold text-rose-500 tracking-wider">Negativ:</span>
        <input
          type="text"
          v-model="generateStore.negativePrompt"
          placeholder="Was im Bild vermieden werden soll (z. B. Unschärfe, Text, Artefakte)..."
          class="flex-1 rounded-lg bg-slate-100/70 px-2.5 py-1 text-xs text-slate-800 placeholder-slate-400 focus:outline-none dark:bg-slate-800/70 dark:text-slate-200 dark:placeholder-slate-500"
        />
      </div>
    </div>

    <!-- Secondary Utilities Row: Magic Prompt & Negative Toggle -->
    <div class="mt-2 flex items-center justify-between gap-2 text-[11px] text-slate-500 dark:text-slate-400">
      <div class="flex items-center gap-2">
        <!-- Magic Prompt Button -->
        <button
          type="button"
          @click="isEnhanceModalOpen = true"
          class="inline-flex items-center gap-1 hover:text-sky-500 transition-colors"
          title="Prompt durch KI detaillieren lassen"
        >
          <span>✨</span> Magic Prompt
        </button>

        <!-- Negative Prompt Toggle -->
        <button
          type="button"
          @click="generateStore.showNegativePrompt = !generateStore.showNegativePrompt"
          :class="[
            'inline-flex items-center gap-1 transition-colors',
            generateStore.showNegativePrompt ? 'text-rose-500 font-semibold' : 'hover:text-slate-800 dark:hover:text-slate-200',
          ]"
        >
          <span>🚫</span> Negativer Prompt
        </button>
      </div>

      <div class="text-[10px] hidden sm:block">
        Tipp: Shift+Enter für Zeilenumbruch
      </div>
    </div>

    <!-- Expandable Advanced / Overrides Panel (Old Prompt Panel Feature) -->
    <div
      v-if="generateStore.isAdvancedOpen"
      class="mt-3.5 rounded-xl border border-slate-200/80 bg-slate-100/80 p-3.5 dark:border-white/10 dark:bg-slate-950/60 space-y-3"
    >
      <div class="flex items-center justify-between border-b border-slate-200/60 dark:border-white/10 pb-1.5">
        <span class="text-[11px] font-bold uppercase tracking-wider text-slate-600 dark:text-slate-300">
          Erweiterte Überschreibungsoptionen
        </span>
        <button
          type="button"
          @click="generateStore.isAdvancedOpen = false"
          class="text-slate-400 hover:text-slate-600 dark:hover:text-white text-xs"
        >
          Schließen ✕
        </button>
      </div>

      <!-- Controls Grid -->
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-6 gap-2.5">
        <!-- 1. Dimension Preset -->
        <div>
          <label class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Preset
          </label>
          <select
            :value="generateStore.dimensionPreset"
            @change="generateStore.onDimensionPresetChange(($event.target as HTMLSelectElement).value)"
            class="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-400 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200"
          >
            <option v-for="p in DIMENSION_PRESETS" :key="p.value" :value="p.value">
              {{ p.label }}
            </option>
          </select>

        </div>

        <!-- 2. Provider-specific Ratio / Custom Width -->
        <div v-if="activeProvider === 'openrouter'">
          <label class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Ratio (OpenRouter)
          </label>
          <select
            v-model="generateStore.openRouterAspectRatio"
            class="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-400 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200"
          >
            <option value="">Aus Profil</option>
            <option v-for="r in openRouterRatios.slice(1)" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>

        <div v-else-if="activeProvider === 'fal'">
          <label class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Ratio (FAL.ai)
          </label>
          <select
            v-model="generateStore.falAspectRatio"
            class="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-400 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200"
          >
            <option value="">Aus Profil</option>
            <option v-for="r in falRatios.slice(1)" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>

        <div v-else-if="activeProvider === 'google'">
          <label class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Ratio (Google)
          </label>
          <select
            v-model="generateStore.googleAspectRatio"
            class="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-400 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200"
          >
            <option value="">Aus Profil</option>
            <option v-for="r in googleRatios.slice(1)" :key="r" :value="r">{{ r }}</option>
          </select>
        </div>

        <div v-else>
          <label class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Breite (px)
          </label>
          <input
            type="number"
            step="64"
            v-model="generateStore.customWidth"
            placeholder="z. B. 1024"
            class="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-400 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200"
          />
        </div>

        <!-- 3. Provider-specific Resolution / Custom Height -->
        <div v-if="activeProvider === 'openrouter'">
          <label class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Größe (OpenRouter)
          </label>
          <select
            v-model="generateStore.openRouterImageSize"
            class="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-400 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200"
          >
            <option value="">Aus Profil</option>
            <option v-for="s in openRouterSizes.slice(1)" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>

        <div v-else-if="activeProvider === 'fal'">
          <label class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Auflösung (FAL)
          </label>
          <select
            v-model="generateStore.falResolution"
            class="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-400 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200"
          >
            <option value="">Aus Profil</option>
            <option v-for="res in falResolutions.slice(1)" :key="res" :value="res">{{ res }}</option>
          </select>
        </div>

        <div v-else-if="activeProvider === 'google'">
          <label class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Auflösung (Google)
          </label>
          <select
            v-model="generateStore.googleResolution"
            class="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-400 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200"
          >
            <option value="">Aus Profil</option>
            <option v-for="res in googleResolutions.slice(1)" :key="res" :value="res">{{ res }}</option>
          </select>
        </div>

        <div v-else>
          <label class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Höhe (px)
          </label>
          <input
            type="number"
            step="64"
            v-model="generateStore.customHeight"
            placeholder="z. B. 1024"
            class="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-400 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200"
          />
        </div>

        <!-- 4. Number of Images (n_images) -->
        <div>
          <label class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Bilder (1-8)
          </label>
          <input
            type="number"
            min="1"
            max="8"
            v-model.number="generateStore.nImages"
            placeholder="Aus Profil"
            class="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-400 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200"
          />
        </div>

        <!-- 5. Seed with Random Dice & Clear -->
        <div>
          <label class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Seed
          </label>
          <div class="flex items-center gap-1">
            <input
              type="text"
              v-model="generateStore.seed"
              placeholder="Zufall"
              class="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-400 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200"
            />
            <button
              type="button"
              @click="randomizeSeed"
              class="p-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 dark:border-white/10 dark:bg-slate-800 text-xs shrink-0"
              title="Zufälligen Seed generieren"
            >
              🎲
            </button>
            <button
              v-if="generateStore.seed"
              type="button"
              @click="clearSeed"
              class="p-1.5 rounded-lg border border-slate-300 bg-white hover:bg-slate-100 dark:border-white/10 dark:bg-slate-800 text-xs shrink-0"
              title="Seed leeren"
            >
              ✕
            </button>
          </div>
        </div>

        <!-- 6. Upscale Mode Override -->
        <div>
          <label class="block text-[10px] font-semibold uppercase tracking-wider text-slate-500 mb-1">
            Upscaling
          </label>
          <select
            v-model="generateStore.upscaleModel"
            class="w-full rounded-lg border border-slate-300 bg-white px-2 py-1.5 text-xs text-slate-800 focus:outline-none focus:ring-1 focus:ring-sky-400 dark:border-white/10 dark:bg-slate-900 dark:text-slate-200"
          >
            <option
              v-for="opt in generateStore.availableUpscaleModels"
              :key="opt.value"
              :value="opt.value"
            >
              {{ opt.label }}
            </option>
            <option
              v-if="customUpscaleOption"
              :value="customUpscaleOption.value"
            >
              {{ customUpscaleOption.label }}
            </option>
          </select>

        </div>
      </div>
    </div>

    <!-- Modals -->
    <PromptEnhanceModal
      :open="isEnhanceModalOpen"
      @update:open="isEnhanceModalOpen = $event"
    />

    <StylePickerModal
      :open="isStyleModalOpen"
      @update:open="isStyleModalOpen = $event"
    />

    <GalleryImagePickerModal
      :open="isGalleryPickerOpen"
      @update:open="isGalleryPickerOpen = $event"
    />
  </div>
</template>
