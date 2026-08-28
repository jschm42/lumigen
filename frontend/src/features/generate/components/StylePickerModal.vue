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
  <Modal :open="open" title="Style Preset wählen" size="xl" @update:open="emit('update:open', $event)">
    <div class="space-y-4">
      <!-- Search & Filter bar -->
      <div class="flex items-center gap-3">
        <input
          type="text"
          v-model="searchQuery"
          placeholder="Styles durchsuchen..."
          class="flex-1 rounded-xl border border-slate-300/80 bg-white/70 px-3.5 py-2 text-xs text-slate-900 placeholder-slate-400 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500/40"
        />
        <Button
          variant="secondary"
          size="sm"
          @click="selectStyle(null)"
          :class="generateStore.selectedStyleId === null ? 'ring-2 ring-sky-500' : ''"
        >
          Kein Style (Standard)
        </Button>
      </div>

      <!-- Styles Grid -->
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 max-h-[60vh] overflow-y-auto pr-1">
        <div
          v-for="style in filteredStyles"
          :key="style.id"
          @click="selectStyle(style)"
          :class="[
            'group relative rounded-2xl border overflow-hidden transition-all duration-150 cursor-pointer text-left',
            String(generateStore.selectedStyleId) === String(style.id)
              ? 'border-sky-500 ring-2 ring-sky-500/50 shadow-lg shadow-sky-500/20'
              : 'border-slate-300/60 dark:border-white/10 hover:border-sky-400 dark:hover:border-sky-400',
          ]"
        >
          <!-- Style Thumbnail or Gradient -->
          <div class="aspect-square w-full bg-slate-800 overflow-hidden relative">
            <img
              v-if="style.image_url"
              :src="style.image_url"
              :alt="style.name"
              class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
            />
            <div
              v-else
              class="w-full h-full bg-gradient-to-tr from-slate-800 to-slate-900 flex items-center justify-center text-2xl text-slate-500"
            >
              🎨
            </div>

            <!-- Overlay Badge when active -->
            <div
              v-if="String(generateStore.selectedStyleId) === String(style.id)"
              class="absolute top-2 right-2 px-2 py-0.5 rounded-full text-[10px] font-bold bg-sky-500 text-white shadow-md"
            >
              Aktiv
            </div>
          </div>

          <!-- Style Info -->
          <div class="p-3 bg-white/90 dark:bg-slate-900/90">
            <h4 class="font-semibold text-xs text-slate-900 dark:text-white truncate">
              {{ style.name }}
            </h4>
            <p v-if="style.description" class="text-[11px] text-slate-500 dark:text-slate-400 line-clamp-2 mt-0.5">
              {{ style.description }}
            </p>
          </div>
        </div>
      </div>
    </div>
  </Modal>
</template>
