<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ChevronDown, ChevronUp } from 'lucide-vue-next'
import Button from '@/components/ui/Button.vue'
import IconButton from '@/components/ui/IconButton.vue'
import Input from '@/components/ui/Input.vue'
import Modal from '@/components/ui/Modal.vue'
import { useGenerateStore } from '@/stores/generate'
import type { Generation } from '@/types'

/** Dialog to reorder the frames of an agentic animation and edit their durations. */
const props = defineProps<{
  open: boolean
  generation: Generation
}>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

interface FrameRow {
  id: number
  title: string
  thumbnail: string
  duration: string
}

const generateStore = useGenerateStore()
const rows = ref<FrameRow[]>([])
const isSaving = ref(false)
const durationError = ref('')
const assembles = computed(() => props.generation.animation?.output !== 'none')

function loadRows() {
  rows.value = (props.generation.assets || [])
    .filter((a) => a.metadata?.role === 'frame')
    .sort((a, b) => (a.stack_order ?? 0) - (b.stack_order ?? 0))
    .map((a) => ({
      id: a.id,
      title: a.metadata?.item_title || `Frame ${a.id}`,
      thumbnail: a.thumbnail_url || a.image_url || '',
      duration: a.metadata?.duration_ms != null ? String(a.metadata.duration_ms) : '',
    }))
  durationError.value = ''
}

watch(
  () => props.open,
  (open) => {
    if (open) loadRows()
  },
  { immediate: true }
)

function move(index: number, delta: number) {
  const target = index + delta
  if (target < 0 || target >= rows.value.length) return
  const next = [...rows.value]
  ;[next[index], next[target]] = [next[target], next[index]]
  rows.value = next
}

/** Parse a duration field: empty keeps the current value, otherwise 20–10000 ms. */
function parseDuration(value: string): number | null | undefined {
  const text = value.trim()
  if (!text) return null
  const parsed = Number.parseInt(text, 10)
  return Number.isFinite(parsed) && parsed >= 20 && parsed <= 10000 ? parsed : undefined
}

async function save() {
  const frames = rows.value.map((row) => ({ id: row.id, duration_ms: parseDuration(row.duration) }))
  if (frames.some((f) => f.duration_ms === undefined)) {
    durationError.value = 'Durations must be whole numbers between 20 and 10000 ms.'
    return
  }
  durationError.value = ''
  isSaving.value = true
  try {
    const ok = await generateStore.updateAnimationFrames(
      props.generation,
      frames as Array<{ id: number; duration_ms: number | null }>
    )
    if (ok) emit('update:open', false)
  } finally {
    isSaving.value = false
  }
}
</script>

<template>
  <Modal :open="open" title="Edit frames" size="lg" @update:open="emit('update:open', $event)">
    <p class="mb-4 text-xs text-slate-600 dark:text-slate-300">
      {{ assembles ? 'Change the order and duration of the frames. The animation is rebuilt when you save.' : 'Change the order of the frames.' }}
    </p>
    <ol class="space-y-2" data-testid="frame-editor-list">
      <li
        v-for="(row, index) in rows"
        :key="row.id"
        class="flex items-center gap-3 rounded-xl bg-slate-100 p-2 dark:bg-slate-800/60"
        :data-frame-id="row.id"
      >
        <span class="w-6 text-center font-mono text-2xs text-slate-500 dark:text-slate-400">{{ index + 1 }}</span>
        <img :src="row.thumbnail" :alt="row.title" class="size-12 rounded-lg bg-slate-950 object-contain" />
        <span class="min-w-0 flex-1 truncate text-xs font-semibold text-slate-900 dark:text-white">{{ row.title }}</span>
        <Input
          v-if="assembles"
          v-model="row.duration"
          type="number"
          size="sm"
          class="w-28"
          min="20"
          max="10000"
          step="10"
          placeholder="Default ms"
          :aria-label="`Duration of ${row.title} in milliseconds`"
        />
        <IconButton size="xs" :label="`Move ${row.title} up`" :disabled="index === 0" @click="move(index, -1)">
          <ChevronUp class="size-4" aria-hidden="true" />
        </IconButton>
        <IconButton
          size="xs"
          :label="`Move ${row.title} down`"
          :disabled="index === rows.length - 1"
          @click="move(index, 1)"
        >
          <ChevronDown class="size-4" aria-hidden="true" />
        </IconButton>
      </li>
    </ol>
    <p v-if="durationError" class="mt-3 text-xs font-medium text-rose-600 dark:text-rose-400" role="alert">
      {{ durationError }}
    </p>
    <template #footer>
      <Button variant="ghost" @click="emit('update:open', false)">Cancel</Button>
      <Button :loading="isSaving" @click="save">{{ assembles ? 'Save & rebuild' : 'Save order' }}</Button>
    </template>
  </Modal>
</template>
