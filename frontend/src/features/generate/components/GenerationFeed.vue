<script setup lang="ts">
import { ref, onMounted, watch, nextTick } from 'vue'
import { useGenerateStore } from '@/stores/generate'
import GenerationCard from './GenerationCard.vue'
import Spinner from '@/components/ui/Spinner.vue'

const generateStore = useGenerateStore()
const feedContainerRef = ref<HTMLDivElement | null>(null)
const isNearBottom = ref(true)
const showJumpButton = ref(false)

const NEAR_BOTTOM_PX = 160

const PROMPT_IDEAS = [
  'A cozy reading nook in a treehouse, warm lantern light, rainy evening',
  'Isometric pixel-art city block at night with neon signs',
  'Macro photo of a dew-covered spider web at sunrise, shallow depth of field',
]

// After a session load or submit, images still arrive and grow the feed. Keep it pinned
// to the bottom for a short while unless the user scrolls up themselves.
const PIN_DURATION_MS = 4000
let pinnedUntil = 0

function unpin() {
  pinnedUntil = 0
}

function updateScrollState() {
  const el = feedContainerRef.value
  if (!el) return
  const distance = el.scrollHeight - el.scrollTop - el.clientHeight
  isNearBottom.value = distance < NEAR_BOTTOM_PX
  showJumpButton.value = distance > NEAR_BOTTOM_PX * 2 && Date.now() > pinnedUntil
}

function scrollToBottom(smooth = true) {
  nextTick(() => {
    const el = feedContainerRef.value
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
  })
}

function pinToBottom(smooth: boolean) {
  pinnedUntil = Date.now() + PIN_DURATION_MS
  scrollToBottom(smooth)
}

// New submit: always bring the pending job into view.
watch(() => generateStore.lastSubmittedAt, () => pinToBottom(true))

// Session switch: jump to the latest result without animation.
watch(
  () => generateStore.isLoadingHistory,
  (loading) => {
    if (!loading) pinToBottom(false)
  }
)

// Job updates (e.g. images arriving): only follow if the user is already at the bottom,
// so reading older results is never interrupted.
watch(
  () => generateStore.generations.map((g) => `${g.id}:${g.status}:${g.assets?.length || 0}`).join('|'),
  () => {
    if (Date.now() < pinnedUntil || isNearBottom.value) scrollToBottom()
  }
)

function handleImageLoaded() {
  if (Date.now() < pinnedUntil || isNearBottom.value) scrollToBottom(false)
}

function useIdea(idea: string) {
  generateStore.prompt = idea
}

onMounted(() => {
  pinToBottom(false)
})
</script>

<template>
  <div class="relative flex-1 min-h-0">
    <div
      ref="feedContainerRef"
      class="h-full overflow-y-auto px-1 pb-4"
      @scroll.passive="updateScrollState"
      @wheel.passive="unpin"
      @touchmove.passive="unpin"
      data-testid="generation-feed"
    >
      <div class="mx-auto w-full max-w-5xl">
        <!-- Loading spinner when loading session history -->
        <div v-if="generateStore.isLoadingHistory" class="py-20 flex justify-center">
          <Spinner size="lg" class="text-sky-500" />
        </div>

        <!-- Empty State -->
        <div
          v-else-if="!generateStore.generations || generateStore.generations.length === 0"
          class="min-h-[320px] flex flex-col items-center justify-center text-center p-8 space-y-5"
        >
          <div class="w-16 h-16 rounded-3xl bg-sky-500/10 dark:bg-sky-400/10 border border-sky-400/20 flex items-center justify-center text-3xl shadow-inner">
            ✨
          </div>
          <div class="space-y-1 max-w-md">
            <h3 class="text-base font-bold text-slate-800 dark:text-white">
              Ready for your creations
            </h3>
            <p class="text-xs text-slate-500 dark:text-slate-400">
              Pick a model above, describe your image below and press <kbd class="rounded border border-slate-300 px-1 font-mono text-[10px] dark:border-slate-700">Enter</kbd>.
              Every prompt in this session stays here as a visual history.
            </p>
          </div>
          <div class="flex max-w-2xl flex-wrap justify-center gap-2">
            <button
              v-for="idea in PROMPT_IDEAS"
              :key="idea"
              type="button"
              @click="useIdea(idea)"
              class="cursor-pointer rounded-xl border border-slate-200 bg-white/70 px-3 py-2 text-left text-[11px] text-slate-600 transition-colors hover:border-sky-400 hover:text-sky-700 dark:border-white/10 dark:bg-slate-900/60 dark:text-slate-300 dark:hover:text-sky-300"
            >
              {{ idea }}
            </button>
          </div>
        </div>

        <!-- Generation Cards List -->
        <div v-else class="space-y-4 pt-1">
          <GenerationCard
            v-for="gen in (generateStore.generations || [])"
            :key="gen.id"
            :generation="gen"
            @image-loaded="handleImageLoaded"
          />
        </div>
      </div>
    </div>

    <!-- Jump to latest -->
    <Transition
      enter-active-class="transition duration-150"
      enter-from-class="opacity-0 translate-y-2"
      leave-active-class="transition duration-100"
      leave-to-class="opacity-0 translate-y-2"
    >
      <button
        v-if="showJumpButton"
        type="button"
        @click="scrollToBottom()"
        class="absolute bottom-3 left-1/2 -translate-x-1/2 inline-flex cursor-pointer items-center gap-1.5 rounded-full border border-slate-200 bg-white/95 px-3 py-1.5 text-[11px] font-semibold text-slate-700 shadow-lg backdrop-blur hover:text-sky-600 dark:border-white/10 dark:bg-slate-800/95 dark:text-slate-200"
      >
        <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 14l-7 7m0 0l-7-7m7 7V3" />
        </svg>
        Latest
        <span
          v-if="generateStore.activeJobIds.length > 0"
          class="rounded-full bg-sky-500 px-1.5 text-[10px] text-white"
        >
          {{ generateStore.activeJobIds.length }} running
        </span>
      </button>
    </Transition>
  </div>
</template>
