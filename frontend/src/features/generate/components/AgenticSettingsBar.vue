<script setup lang="ts">
import { computed, watch } from 'vue'
import { Bot, TriangleAlert } from 'lucide-vue-next'
import Input from '@/components/ui/Input.vue'
import Select, { type SelectOption } from '@/components/ui/Select.vue'
import Switch from '@/components/ui/Switch.vue'
import Tabs, { type TabItem } from '@/components/ui/Tabs.vue'
import { ANIMATION_UNSUPPORTED_MESSAGE, useGenerateStore } from '@/stores/generate'
import { useAuthStore } from '@/stores/auth'
import type { AgenticKind, AnimationLoop, AnimationOutput } from '@/types'

/** Agentic Mode options shown below the prompt: output kind, planner model, counts and GIF settings. */
const generateStore = useGenerateStore()
const authStore = useAuthStore()

const frameLimit = computed(() => authStore.uiSettings.animation_max_frames || 24)
const defaultFrameMs = computed(() => authStore.uiSettings.animation_default_frame_ms || 100)
const countMax = computed(() => (generateStore.isAnimationMode ? frameLimit.value : 16))
const countMin = computed(() => (generateStore.isAnimationMode ? 2 : 1))

const kindTabs = computed<TabItem[]>(() => [
  { id: 'set', label: 'Image set' },
  {
    id: 'animation',
    label: 'Animation',
    disabled: !generateStore.supportsAnimation,
    hint: generateStore.supportsAnimation ? undefined : ANIMATION_UNSUPPORTED_MESSAGE,
  },
])

// Switching to a model without image input leaves animation mode.
watch(
  () => generateStore.supportsAnimation,
  (supported) => {
    if (!supported && generateStore.agenticKind === 'animation') generateStore.agenticKind = 'set'
  }
)

const llmOptions = computed<SelectOption[]>(() => {
  const def = generateStore.availableLlmModels.find((m) => m.is_default)
  return [
    { value: '', label: `Auto (${def ? def.name : 'Default'})` },
    ...generateStore.availableLlmModels.map((m) => ({ value: m.id, label: `${m.name}${m.is_default ? ' ★' : ''}` })),
  ]
})

const outputOptions: SelectOption[] = [
  { value: 'gif', label: 'GIF' },
  { value: 'webp', label: 'Animated WebP' },
  { value: 'none', label: 'Frames only (no animation file)' },
]

const isFramesOnly = computed(() => generateStore.animationOutput === 'none')

function setOutput(value: string | number) {
  generateStore.animationOutput = value as AnimationOutput
}

const loopOptions: SelectOption[] = [
  { value: '', label: 'Auto (planner decides)' },
  { value: 'loop', label: 'Loop' },
  { value: 'pingpong', label: 'Ping-pong' },
  { value: 'once', label: 'Play once' },
]

/** Parse an optional positive integer from an input value. */
function toCount(value: string): number | null {
  const parsed = Number.parseInt(value, 10)
  return Number.isFinite(parsed) && parsed > 0 ? parsed : null
}

function setKind(id: string) {
  generateStore.agenticKind = id as AgenticKind
}

function setLoop(value: string | number) {
  generateStore.animationLoop = value as AnimationLoop | ''
}

const hint = computed(() => {
  if (!generateStore.isAnimationMode) return 'Generates a cohesive set into a single gallery stack'
  if (isFramesOnly.value) return 'Plans frames and generates a consistent image series from a keyframe'
  const format = generateStore.animationOutput === 'webp' ? 'an animated WebP' : 'a GIF'
  return `Plans frames, generates them from a keyframe and assembles ${format}`
})
</script>

<template>
  <div
    class="mt-2 space-y-2 rounded-xl border border-violet-200/80 bg-violet-50/70 px-3.5 py-2 dark:border-violet-900/40 dark:bg-violet-950/30"
    data-testid="agentic-settings"
  >
    <div class="flex flex-wrap items-center gap-3">
      <div class="flex shrink-0 select-none items-center gap-1.5 text-xs font-bold text-violet-700 dark:text-violet-300">
        <Bot class="size-4" aria-hidden="true" />
        <span>Agentic Mode</span>
      </div>
      <Tabs :tabs="kindTabs" :model-value="generateStore.agenticKind" @update:model-value="setKind" />
      <Select
        v-model="generateStore.agenticLlmModel"
        :options="llmOptions"
        size="sm"
        class="max-w-[210px]"
        aria-label="Reasoning model"
        title="LLM used to plan the set or the animation frames"
      />
      <Input
        :model-value="generateStore.agenticMinImages ?? ''"
        type="number"
        size="sm"
        class="w-24"
        :min="countMin"
        :max="countMax"
        placeholder="Min: auto"
        :aria-label="generateStore.isAnimationMode ? 'Minimum frames' : 'Minimum images'"
        @update:model-value="generateStore.agenticMinImages = toCount($event)"
      />
      <Input
        :model-value="generateStore.agenticMaxImages ?? ''"
        type="number"
        size="sm"
        class="w-24"
        :min="countMin"
        :max="countMax"
        placeholder="Max: auto"
        :aria-label="generateStore.isAnimationMode ? 'Maximum frames' : 'Maximum images'"
        @update:model-value="generateStore.agenticMaxImages = toCount($event)"
      />
      <span class="ml-auto hidden text-2xs italic text-violet-700/80 dark:text-violet-300/80 sm:inline">{{ hint }}</span>
    </div>

    <div
      v-if="generateStore.isAnimationMode"
      class="flex flex-wrap items-center gap-3"
      data-testid="animation-settings"
    >
      <Select
        :model-value="generateStore.animationOutput"
        :options="outputOptions"
        size="sm"
        class="w-56"
        aria-label="Output"
        @update:model-value="setOutput"
      />
      <Select
        v-if="!isFramesOnly"
        :model-value="generateStore.animationLoop"
        :options="loopOptions"
        size="sm"
        class="w-48"
        aria-label="Loop mode"
        @update:model-value="setLoop"
      />
      <Input
        v-if="!isFramesOnly"
        :model-value="generateStore.animationFrameMs ?? ''"
        type="number"
        size="sm"
        class="w-36"
        min="20"
        max="1000"
        step="10"
        :placeholder="`Frame ms: ${defaultFrameMs}`"
        aria-label="Frame duration in milliseconds"
        @update:model-value="generateStore.animationFrameMs = toCount($event)"
      />
      <Switch v-model="generateStore.animationTransparent" label="Transparent background" />
      <span class="text-2xs text-slate-500 dark:text-slate-400">Up to {{ frameLimit }} frames</span>
    </div>

    <p
      v-if="generateStore.isAnimationMode && !generateStore.supportsAnimation"
      class="flex items-center gap-1.5 text-2xs text-amber-700 dark:text-amber-300"
      role="alert"
    >
      <TriangleAlert class="size-3.5" aria-hidden="true" />
      {{ ANIMATION_UNSUPPORTED_MESSAGE }}
    </p>
  </div>
</template>
