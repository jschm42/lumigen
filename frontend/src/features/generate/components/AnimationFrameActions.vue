<script setup lang="ts">
import { computed } from 'vue'
import { RefreshCw, Trash2 } from 'lucide-vue-next'
import IconButton from '@/components/ui/IconButton.vue'
import { useConfirm } from '@/composables/useConfirm'
import { useGenerateStore } from '@/stores/generate'
import type { Asset, Generation } from '@/types'

/** Per-frame actions of an agentic animation: regenerate or remove the frame (the GIF/WebP is rebuilt). */
const props = defineProps<{
  generation: Generation
  asset: Asset
}>()

const generateStore = useGenerateStore()
const confirm = useConfirm()

const frameCount = computed(
  () => (props.generation.assets || []).filter((a) => a.metadata?.role === 'frame').length
)
const isBusy = computed(() => ['queued', 'running', 'pending'].includes(props.generation.status))
const assembles = computed(() => props.generation.animation?.output !== 'none')
// An assembled animation needs at least two frames; a frame series at least one.
const canRemove = computed(() => frameCount.value > (assembles.value ? 2 : 1))
const title = computed(() => props.asset.metadata?.item_title || 'this frame')

async function handleRegenerate() {
  await generateStore.regenerateAnimationFrame(props.generation, props.asset.id)
}

async function handleRemove() {
  const ok = await confirm({
    title: 'Remove frame',
    message: assembles.value
      ? `Remove "${title.value}" and rebuild the animation from the remaining frames?`
      : `Remove "${title.value}" from the frame series?`,
    confirmText: 'Remove',
  })
  if (ok) await generateStore.removeAnimationFrame(props.generation, props.asset.id)
}
</script>

<template>
  <div class="flex items-center gap-0.5" data-testid="frame-actions">
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
