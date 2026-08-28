<script setup lang="ts">
import { ref } from 'vue'
import { useGenerateStore } from '@/stores/generate'
import Button from '@/components/ui/Button.vue'
import ImageDropzone from './ImageDropzone.vue'
import PromptEnhanceModal from './PromptEnhanceModal.vue'

const generateStore = useGenerateStore()

const isEnhanceModalOpen = ref(false)

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault()
    if (!generateStore.isSubmitting) {
      generateStore.submit()
    }
  }
}
</script>

<template>
  <div class="rounded-2xl border border-slate-300/80 bg-white/90 p-3.5 shadow-xl backdrop-blur-xl dark:border-white/15 dark:bg-slate-900/90 transition-all">
    <!-- Attached Images Strip -->
    <div v-if="generateStore.attachedImages.length > 0" class="mb-3 pb-3 border-b border-slate-200 dark:border-white/10">
      <ImageDropzone />
    </div>

    <!-- Main Prompt Input -->
    <div class="relative">
      <textarea
        v-model="generateStore.prompt"
        @keydown="handleKeydown"
        placeholder="Beschreibe das gewünschte Bild... (Enter zum Generieren, Shift+Enter für Zeilenumbruch)"
        rows="2"
        class="w-full rounded-xl bg-transparent px-2 py-1.5 text-xs sm:text-sm text-slate-900 placeholder-slate-400 focus:outline-none dark:text-slate-100 dark:placeholder-slate-500 resize-none"
      ></textarea>
    </div>

    <!-- Negative Prompt Input (Collapsible) -->
    <div v-if="generateStore.showNegativePrompt" class="mt-2 pt-2 border-t border-slate-200/60 dark:border-white/10">
      <input
        type="text"
        v-model="generateStore.negativePrompt"
        placeholder="Negativer Prompt (Elemente, die vermieden werden sollen)..."
        class="w-full rounded-lg bg-transparent px-2 py-1 text-xs text-slate-800 placeholder-slate-400 focus:outline-none dark:text-slate-200 dark:placeholder-slate-500"
      />
    </div>

    <!-- Bottom Action Row -->
    <div class="mt-3 pt-2.5 border-t border-slate-200/60 dark:border-white/10 flex items-center justify-between gap-2 flex-wrap text-xs">
      <div class="flex items-center gap-1.5 flex-wrap">
        <!-- Magic Prompt Button -->
        <button
          type="button"
          @click="isEnhanceModalOpen = true"
          class="px-2.5 py-1 rounded-xl border border-slate-200 bg-white/80 text-slate-700 hover:border-sky-400 hover:text-sky-600 dark:border-white/10 dark:bg-slate-800/80 dark:text-slate-300 dark:hover:border-sky-400/60 transition-colors flex items-center gap-1"
          title="Prompt mit KI optimieren"
        >
          <span>✨</span> Magic Prompt
        </button>

        <!-- Negative Prompt Toggle -->
        <button
          type="button"
          @click="generateStore.showNegativePrompt = !generateStore.showNegativePrompt"
          :class="[
            'px-2.5 py-1 rounded-xl border transition-colors flex items-center gap-1',
            generateStore.showNegativePrompt
              ? 'bg-rose-500/10 border-rose-500/40 text-rose-600 dark:text-rose-400'
              : 'border-slate-200 bg-white/80 text-slate-700 hover:border-slate-300 dark:border-white/10 dark:bg-slate-800/80 dark:text-slate-300',
          ]"
        >
          <span>🚫</span> Negativ
        </button>

        <!-- Reference Image Upload trigger -->
        <ImageDropzone v-if="generateStore.attachedImages.length === 0" />
      </div>

      <!-- Submit Generate Button -->
      <Button
        variant="primary"
        size="md"
        :loading="generateStore.isSubmitting"
        @click="generateStore.submit"
        class="min-w-[120px]"
      >
        <template #icon>
          <span class="text-sm">⚡</span>
        </template>
        Generieren
      </Button>
    </div>

    <!-- Prompt Enhance Modal -->
    <PromptEnhanceModal
      :open="isEnhanceModalOpen"
      @update:open="isEnhanceModalOpen = $event"
    />
  </div>
</template>
