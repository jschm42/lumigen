<script setup lang="ts">
import { computed } from 'vue'
import type { Generation } from '@/types'
import Spinner from '@/components/ui/Spinner.vue'
import Badge from '@/components/ui/Badge.vue'
import GenerationActions from './GenerationActions.vue'

interface Props {
  generation: Generation
}

const props = defineProps<Props>()

const isPendingOrProcessing = computed(() => {
  return props.generation.status === 'pending' || props.generation.status === 'processing'
})
</script>

<template>
  <div class="space-y-3 p-4 sm:p-5 rounded-2xl border border-slate-200/80 bg-white/75 dark:border-white/10 dark:bg-slate-900/75 shadow-sm transition-all">
    <!-- Header: Prompt text & Model info -->
    <div class="flex flex-col sm:flex-row sm:items-start justify-between gap-2 pb-2 border-b border-slate-200/60 dark:border-white/10">
      <div class="space-y-1 min-w-0 flex-1">
        <p class="text-xs sm:text-sm font-medium text-slate-900 dark:text-white leading-relaxed break-words">
          {{ generation.prompt }}
        </p>
        <p v-if="generation.negative_prompt" class="text-[11px] text-slate-500 dark:text-slate-400">
          <span class="font-semibold text-rose-500">Negativ:</span> {{ generation.negative_prompt }}
        </p>
      </div>

      <!-- Badges -->
      <div class="flex flex-wrap items-center gap-1.5 shrink-0">
        <Badge v-if="generation.model_name" variant="sky" size="xs">
          {{ generation.model_name }}
        </Badge>
        <Badge v-if="generation.aspect_ratio" variant="slate" size="xs">
          {{ generation.aspect_ratio }}
        </Badge>
      </div>
    </div>

    <!-- Processing State -->
    <div
      v-if="isPendingOrProcessing"
      class="py-12 flex flex-col items-center justify-center gap-3 bg-slate-100/60 dark:bg-slate-950/40 rounded-xl border border-dashed border-slate-300 dark:border-white/10"
    >
      <Spinner size="lg" class="text-sky-500" />
      <span class="text-xs font-semibold text-slate-600 dark:text-slate-300 animate-pulse">
        Bild wird generiert...
      </span>
    </div>

    <!-- Failed State -->
    <div
      v-else-if="generation.status === 'failed'"
      class="p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800/60 text-xs text-rose-700 dark:text-rose-300"
    >
      <div class="font-semibold mb-1">Generierung fehlgeschlagen</div>
      <p>{{ generation.error_message || 'Unbekannter Fehler beim Generieren.' }}</p>
    </div>

    <!-- Succeeded State (Image Results) -->
    <div v-else-if="generation.assets && generation.assets.length > 0" class="space-y-3">
      <div
        v-for="asset in generation.assets"
        :key="asset.id"
        class="space-y-3"
      >
        <!-- Result image container with proper aspect ratio -->
        <div class="relative group rounded-xl overflow-hidden bg-slate-950 flex items-center justify-center border border-slate-300/60 dark:border-white/10 max-h-[70vh]">
          <img
            :src="asset.image_url || asset.thumbnail_url"
            :alt="asset.prompt"
            class="w-full h-auto object-contain max-h-[70vh]"
            loading="lazy"
          />
        </div>

        <!-- Action bar -->
        <GenerationActions :asset="asset" :generation="generation" />
      </div>
    </div>
  </div>
</template>
