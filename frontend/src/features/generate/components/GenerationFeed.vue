<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import { useGenerateStore } from '@/stores/generate'
import GenerationCard from './GenerationCard.vue'
import Spinner from '@/components/ui/Spinner.vue'

const generateStore = useGenerateStore()
const feedContainerRef = ref<HTMLDivElement | null>(null)

function scrollToBottom() {
  nextTick(() => {
    if (feedContainerRef.value) {
      feedContainerRef.value.scrollTop = feedContainerRef.value.scrollHeight
    }
  })
}

watch(
  () => generateStore.generations.length,
  () => {
    scrollToBottom()
  }
)

onMounted(() => {
  scrollToBottom()
})
</script>

<template>
  <div
    ref="feedContainerRef"
    class="flex-1 overflow-y-auto space-y-6 pr-1 pb-4 scroll-smooth"
  >
    <!-- Loading spinner when loading session history -->
    <div v-if="generateStore.isLoadingHistory" class="py-20 flex justify-center">
      <Spinner size="lg" class="text-sky-500" />
    </div>

    <!-- Empty State -->
    <div
      v-else-if="generateStore.generations.length === 0"
      class="h-full min-h-[300px] flex flex-col items-center justify-center text-center p-8 space-y-4"
    >
      <div class="w-16 h-16 rounded-3xl bg-sky-500/10 dark:bg-sky-400/10 border border-sky-400/20 flex items-center justify-center text-3xl shadow-inner">
        ✨
      </div>
      <div class="space-y-1 max-w-sm">
        <h3 class="text-base font-bold text-slate-800 dark:text-white">
          Bereit für deine Kreationen
        </h3>
        <p class="text-xs text-slate-500 dark:text-slate-400">
          Wähle dein bevorzugtes Modell, passe das Seitenverhältnis an und starte mit deinem ersten Prompt.
        </p>
      </div>
    </div>

    <!-- Generation Cards List -->
    <div v-else class="space-y-6">
      <GenerationCard
        v-for="gen in generateStore.generations"
        :key="gen.id"
        :generation="gen"
      />
    </div>
  </div>
</template>
