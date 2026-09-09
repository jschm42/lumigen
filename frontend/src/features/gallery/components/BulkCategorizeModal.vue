<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useGalleryStore } from '@/stores/gallery'
import { useToastStore } from '@/stores/toast'
import Modal from '@/components/ui/Modal.vue'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'

interface Props {
  open: boolean
}

const props = defineProps<Props>()
const emit = defineEmits<{
  'update:open': [value: boolean]
}>()

const galleryStore = useGalleryStore()
const toastStore = useToastStore()

const selectedCategoryIds = ref<number[]>([])
const mode = ref<'replace' | 'append'>('replace')
const newCategoryName = ref('')
const isCreatingCategory = ref(false)
const isSubmitting = ref(false)

onMounted(() => {
  galleryStore.loadCategories()
})

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      selectedCategoryIds.value = []
      mode.value = 'replace'
      newCategoryName.value = ''
      galleryStore.loadCategories()
    }
  }
)

function toggleCategory(catId: number) {
  const index = selectedCategoryIds.value.indexOf(catId)
  if (index !== -1) {
    selectedCategoryIds.value.splice(index, 1)
  } else {
    selectedCategoryIds.value.push(catId)
  }
}

async function handleQuickCreate() {
  const name = newCategoryName.value.trim()
  if (!name) return

  isCreatingCategory.value = true
  try {
    const created = await galleryStore.createCategory(name)
    if (created && !selectedCategoryIds.value.includes(created.id)) {
      selectedCategoryIds.value.push(created.id)
    }
    newCategoryName.value = ''
  } catch (_error) {
    // handled by store toast
  } finally {
    isCreatingCategory.value = false
  }
}

async function handleSave() {
  isSubmitting.value = true
  try {
    await galleryStore.bulkCategorize(selectedCategoryIds.value, mode.value)
    emit('update:open', false)
  } catch (_error) {
    toastStore.error('Fehler beim Zuweisen der Kategorien.')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <Modal
    :open="open"
    size="md"
    @update:open="emit('update:open', $event)"
  >
    <template #header>
      <div class="flex items-center gap-2">
        <span class="text-base">🏷️</span>
        <h3 class="text-sm font-bold text-slate-900 dark:text-white">
          Kategorien zuweisen
        </h3>
      </div>
    </template>

    <div class="space-y-4 text-xs">
      <div class="p-3 rounded-xl bg-sky-50 dark:bg-sky-950/40 border border-sky-200 dark:border-sky-900/40 text-sky-800 dark:text-sky-300 font-medium">
        <span>Für </span>
        <span class="font-bold underline">{{ galleryStore.selectedAssetIds.length }} ausgewählte Bilder</span>
        <span> Kategorien festlegen:</span>
      </div>

      <!-- Categories Picker Pills -->
      <div>
        <label class="block text-[11px] font-semibold uppercase tracking-wider text-slate-500 mb-2">
          Kategorien auswählen
        </label>

        <div v-if="galleryStore.categories.length === 0" class="py-4 text-center text-slate-400">
          Noch keine Kategorien vorhanden. Erstelle unten eine neue!
        </div>

        <div v-else class="flex flex-wrap gap-2 max-h-48 overflow-y-auto p-1">
          <button
            v-for="cat in galleryStore.categories"
            :key="cat.id"
            type="button"
            @click="toggleCategory(cat.id)"
            :class="[
              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer shadow-sm',
              selectedCategoryIds.includes(cat.id)
                ? 'bg-sky-500 border-sky-500 text-white shadow-sky-500/20'
                : 'bg-white border-slate-300/80 text-slate-700 hover:border-sky-400 dark:bg-slate-800 dark:border-white/10 dark:text-slate-200 dark:hover:border-white/30',
            ]"
          >
            <span>🏷️</span>
            <span>{{ cat.name }}</span>
            <span v-if="selectedCategoryIds.includes(cat.id)" class="text-[10px]">✓</span>
          </button>
        </div>
      </div>

      <!-- Quick create new category input -->
      <div class="pt-2 border-t border-slate-200 dark:border-white/10">
        <label class="block text-[11px] font-semibold text-slate-600 dark:text-slate-300 mb-1.5">
          Neue Kategorie schnell anlegen
        </label>
        <div class="flex items-center gap-2">
          <Input
            v-model="newCategoryName"
            placeholder="Kategoriename..."
            @keydown.enter.prevent="handleQuickCreate"
            class="flex-1"
          />
          <Button
            type="button"
            variant="surface"
            size="sm"
            :loading="isCreatingCategory"
            :disabled="!newCategoryName.trim()"
            @click="handleQuickCreate"
          >
            + Hinzufügen
          </Button>
        </div>
      </div>

      <!-- Mode selection (replace vs append) -->
      <div class="pt-3 border-t border-slate-200 dark:border-white/10 space-y-2">
        <label class="block text-[11px] font-semibold uppercase tracking-wider text-slate-500">
          Zuweisungsmodus
        </label>
        <div class="grid grid-cols-2 gap-2">
          <label
            :class="[
              'flex items-center gap-2 p-2.5 rounded-xl border cursor-pointer transition-colors text-xs font-medium',
              mode === 'replace'
                ? 'border-sky-500 bg-sky-50/70 text-sky-900 dark:bg-sky-950/40 dark:text-sky-200 dark:border-sky-500'
                : 'border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50',
            ]"
          >
            <input
              type="radio"
              v-model="mode"
              value="replace"
              class="text-sky-500 focus:ring-sky-500"
            />
            <span>Ersetzen (exakt diese)</span>
          </label>

          <label
            :class="[
              'flex items-center gap-2 p-2.5 rounded-xl border cursor-pointer transition-colors text-xs font-medium',
              mode === 'append'
                ? 'border-sky-500 bg-sky-50/70 text-sky-900 dark:bg-sky-950/40 dark:text-sky-200 dark:border-sky-500'
                : 'border-slate-200 dark:border-white/10 text-slate-600 dark:text-slate-400 hover:bg-slate-50 dark:hover:bg-slate-800/50',
            ]"
          >
            <input
              type="radio"
              v-model="mode"
              value="append"
              class="text-sky-500 focus:ring-sky-500"
            />
            <span>Zu bestehenden addieren</span>
          </label>
        </div>
      </div>

      <!-- Action buttons -->
      <div class="flex items-center justify-end gap-2 pt-3 border-t border-slate-200 dark:border-white/10">
        <Button
          type="button"
          variant="ghost"
          size="sm"
          @click="emit('update:open', false)"
        >
          Abbrechen
        </Button>
        <Button
          type="button"
          variant="primary"
          size="sm"
          :loading="isSubmitting"
          @click="handleSave"
        >
          Zuweisen
        </Button>
      </div>
    </div>
  </Modal>
</template>
