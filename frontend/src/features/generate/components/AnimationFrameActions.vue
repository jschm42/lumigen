<script setup lang="ts">
import { computed } from 'vue'
import { Eye, EyeOff, RefreshCw, Trash2 } from 'lucide-vue-next'
import IconButton from '@/components/ui/IconButton.vue'
import { useConfirm } from '@/composables/useConfirm'
import { useGenerateStore } from '@/stores/generate'
import type { Asset, Generation } from '@/types'

/** Per-frame actions of an agentic animation: include/exclude, regenerate or remove the frame. */
const props = withDefaults(
  defineProps<{
    generation: Generation
    asset: Asset
    disabled?: boolean
    enabledCount?: number
    beforeAction?: () => Promise<void>
  }>(),
  {
    disabled: false,
    enabledCount: undefined,
    beforeAction: undefined,
  }
)

const emit = defineEmits<{
  (e: 'toggle-disabled'): void
}>()

const generateStore = useGenerateStore()
const confirm = useConfirm()

const frameAssets = computed(() =>
  (props.generation.assets || []).filter((a) => a.metadata?.role === 'frame')
)
const frameCount = computed(() => frameAssets.value.length)
const activeCount = computed(
  () =>
    props.enabledCount ??
    frameAssets.value.filter((a) => !a.metadata?.disabled).length
)
const isBusy = computed(() => ['queued', 'running', 'pending'].includes(props.generation.status))
const assembles = computed(() => props.generation.animation?.output !== 'none')
// At least two frames must stay enabled so an animation can always be built.
const canToggleDisabled = computed(() => props.disabled || activeCount.value > 2)
const remainingActiveIfRemoved = computed(() => (props.disabled ? activeCount.value : activeCount.value - 1))
const canRemove = computed(
  () => frameCount.value > 1 && remainingActiveIfRemoved.value >= (assembles.value ? 2 : 1)
)
const title = computed(() => props.asset.metadata?.item_title || 'this frame')

const toggleLabel = computed(() => {
  if (props.disabled) return `Include ${title.value} in animation`
  if (!canToggleDisabled.value) return 'At least two frames must stay enabled'
  return `Disable ${title.value} in animation`
})

async function handleRegenerate() {
  if (props.beforeAction) await props.beforeAction()
  await generateStore.regenerateAnimationFrame(props.generation, props.asset.id)
}

async function handleRemove() {
  const ok = await confirm({
    title: 'Remove frame',
    message: assembles.value
      ? `Permanently delete "${title.value}" and rebuild the animation? (Tip: use the eye button to temporarily disable it instead.)`
      : `Permanently delete "${title.value}" from the frame series?`,
    confirmText: 'Remove',
  })
  if (!ok) return
  if (props.beforeAction) await props.beforeAction()
  await generateStore.removeAnimationFrame(props.generation, props.asset.id)
}
</script>

<template>
  <div class="flex items-center gap-0.5" data-testid="frame-actions">
    <IconButton
      size="xs"
      :pressed="disabled"
      :label="toggleLabel"
      :disabled="isBusy || !canToggleDisabled"
      data-testid="toggle-frame-btn"
      @click="emit('toggle-disabled')"
    >
      <EyeOff v-if="disabled" class="size-3.5" aria-hidden="true" />
      <Eye v-else class="size-3.5" aria-hidden="true" />
    </IconButton>
    <IconButton
      size="xs"
      :label="`Regenerate ${title}`"
      :disabled="isBusy"
      @click="handleRegenerate"
    >
      <RefreshCw class="size-3.5" aria-hidden="true" />
    </IconButton>
    <IconButton
      size="xs"
      variant="danger"
      :label="canRemove ? `Remove ${title}` : 'An animation needs at least two frames'"
      :disabled="isBusy || !canRemove"
      @click="handleRemove"
    >
      <Trash2 class="size-3.5" aria-hidden="true" />
    </IconButton>
  </div>
</template>
