<script setup lang="ts">
import { ref, computed } from 'vue'
import { useGenerateStore } from '@/stores/generate'
import Modal from '@/components/ui/Modal.vue'
import Button from '@/components/ui/Button.vue'
import type { StylePreset } from '@/types'

interface Props {
  open: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

const generateStore = useGenerateStore()
const searchQuery = ref('')
const selectedCategory = ref('all')

const filteredStyles = computed(() => {
  return generateStore.styles.filter((style) => {
    const matchesQuery =
      !searchQuery.value ||
      style.name.toLowerCase().includes(searchQuery.value.toLowerCase()) ||
      style.description?.toLowerCase().includes(searchQuery.value.toLowerCase())
    const matchesCategory =
      selectedCategory.value === 'all' || style.category === selectedCategory.value
    return matchesQuery && matchesCategory
  })
})

function selectStyle(style: StylePreset | null) {
  generateStore.selectedStyleId = style ? style.id : null
  emit('update:open', false)
}
</script>

<template>
  <Modal :open="open" title="Select Style Preset" size="xl" @update:open="emit('update:open', $event)">
    <div class="space-y-4">
      <!-- Search & Filter bar -->
      <div class="flex items-center gap-3">
        <input
          type="text"
          v-model="searchQuery"
          placeholder="Search styles..."
          class="flex-1 rounded-xl border border-slate-300/80 bg-white/70 px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500/40"
        />
        <Button
          variant="secondary"
          size="sm"
          @click="selectStyle(null)"
          :class="generateStore.selectedStyleId === null ? 'ring-2 ring-sky-500' : ''"
        >
          No Style (Default)
        </Button>
      </div>

      <!-- Styles Grid -->
      <div
        class="grid gap-2 max-h-[65vh] overflow-y-auto pr-1"
        style="grid-template-columns: repeat(auto-fill, minmax(78px, 1fr));"
      >
        <div
          v-for="style in filteredStyles"
          :key="style.id"
          @click="selectStyle(style)"
          :class="[
            'group relative aspect-square rounded-lg border overflow-hidden transition-all duration-150 cursor-pointer text-left bg-slate-900',
            String(generateStore.selectedStyleId) === String(style.id)
              ? 'border-sky-500 ring-2 ring-sky-500/50 shadow-lg shadow-sky-500/20'
              : 'border-slate-300/60 dark:border-white/10 hover:border-sky-400 dark:hover:border-sky-400',
          ]"
        >
          <!-- Style Thumbnail or Gradient (Flush with top edge) -->
          <img
            v-if="style.image_url"
            :src="style.image_url"
            :alt="style.name"
            class="absolute inset-0 w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
          />
          <div
            v-else
            class="absolute inset-0 w-full h-full bg-gradient-to-tr from-slate-800 to-slate-900 flex items-center justify-center text-base text-slate-500"
          >
            🎨
          </div>

          <!-- Overlay Badge when active -->
          <div
            v-if="String(generateStore.selectedStyleId) === String(style.id)"
            class="absolute top-1 right-1 px-1.5 py-0.5 rounded-full text-[8px] font-bold bg-sky-500 text-white shadow-sm z-10"
          >
            ✓
          </div>

          <!-- Bottom Gradient Overlay & Style Info -->
          <div class="absolute inset-x-0 bottom-0 bg-gradient-to-t from-slate-950/95 via-slate-950/70 to-transparent pt-4 pb-1 px-1.5 flex flex-col justify-end z-10 pointer-events-none">
            <h4 class="font-semibold text-[10px] leading-tight text-white truncate drop-shadow-sm" :title="style.name">
              {{ style.name }}
            </h4>
            <p v-if="style.description" class="text-[8.5px] text-slate-300 line-clamp-1 mt-0.5 drop-shadow-sm leading-none" :title="style.description">
              {{ style.description }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </Modal>
</template>
