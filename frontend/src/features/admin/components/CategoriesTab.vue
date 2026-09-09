<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { galleryApi } from '@/api/gallery'
import { useToastStore } from '@/stores/toast'
import Button from '@/components/ui/Button.vue'
import Modal from '@/components/ui/Modal.vue'
import Input from '@/components/ui/Input.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import Spinner from '@/components/ui/Spinner.vue'
import type { Category } from '@/types'

const router = useRouter()
const toastStore = useToastStore()

const categories = ref<Category[]>([])
const isLoading = ref(false)
const isEditorOpen = ref(false)
const isDeleteConfirmOpen = ref(false)
const categoryToDelete = ref<Category | null>(null)
const isSubmitting = ref(false)

const editingCategory = ref<{
  id?: number
  name: string
}>({
  id: undefined,
  name: '',
})

async function fetchCategories() {
  isLoading.value = true
  try {
    categories.value = await galleryApi.listCategories()
  } catch (_error) {
    toastStore.error('Kategorien konnten nicht geladen werden.')
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  fetchCategories()
})

function openNew() {
  editingCategory.value = {
    id: undefined,
    name: '',
  }
  isEditorOpen.value = true
}

function openEdit(cat: Category) {
  editingCategory.value = {
    id: cat.id,
    name: cat.name,
  }
  isEditorOpen.value = true
}

async function handleSave() {
  const name = editingCategory.value.name.trim()
  if (!name) {
    toastStore.warning('Bitte einen Kategorienamen angeben.')
    return
  }

  isSubmitting.value = true
  try {
    if (editingCategory.value.id) {
      await galleryApi.updateCategory(editingCategory.value.id, name)
      toastStore.success('Kategorie aktualisiert!')
    } else {
      await galleryApi.createCategory(name)
      toastStore.success(`Kategorie "${name}" erstellt!`)
    }
    isEditorOpen.value = false
    await fetchCategories()
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Fehler beim Speichern der Kategorie.')
  } finally {
    isSubmitting.value = false
  }
}

function promptDelete(cat: Category) {
  categoryToDelete.value = cat
  isDeleteConfirmOpen.value = true
}

async function confirmDelete() {
  if (!categoryToDelete.value) return
  try {
    await galleryApi.deleteCategory(categoryToDelete.value.id)
    toastStore.success('Kategorie gelöscht!')
    isDeleteConfirmOpen.value = false
    categoryToDelete.value = null
    await fetchCategories()
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Fehler beim Löschen der Kategorie.')
  }
}

function navigateToGallery(cat: Category) {
  router.push({ path: '/gallery', query: { category: String(cat.id) } })
}
</script>

<template>
  <div class="space-y-6">
    <!-- Header Controls -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h3 class="text-sm font-bold text-slate-900 dark:text-white">Kategorien-Verwaltung</h3>
        <p class="text-xs text-slate-500">
          Kategorien dienen der flexiblen Strukturierung und Filterung von Bildern und Profilen.
        </p>
      </div>

      <Button variant="primary" size="sm" @click="openNew">
        <template #icon>
          <span>➕</span>
        </template>
        Neue Kategorie
      </Button>
    </div>

    <!-- Loading state -->
    <div v-if="isLoading" class="py-12 flex justify-center">
      <Spinner size="lg" class="text-sky-500" />
    </div>

    <!-- Empty state -->
    <div
      v-else-if="categories.length === 0"
      class="py-12 text-center rounded-2xl border border-dashed border-slate-300 dark:border-white/10 p-8 space-y-3"
    >
      <div class="text-3xl">🏷️</div>
      <p class="text-xs font-semibold text-slate-700 dark:text-slate-300">Noch keine Kategorien angelegt</p>
      <p class="text-xs text-slate-500 max-w-sm mx-auto">
        Erstelle Kategorien, um deine generierten Bilder in der Galerie zu organisieren.
      </p>
      <Button variant="surface" size="xs" @click="openNew">
        Erste Kategorie erstellen
      </Button>
    </div>

    <!-- Categories Grid / List -->
    <div v-else class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3.5">
      <div
        v-for="cat in categories"
        :key="cat.id"
        class="group relative flex flex-col justify-between p-4 rounded-2xl border border-slate-200/80 bg-white/80 dark:border-white/10 dark:bg-slate-900/80 shadow-sm hover:shadow-md transition-all"
      >
        <div class="space-y-2">
          <div class="flex items-start justify-between gap-2">
            <div class="flex items-center gap-2 min-w-0">
              <span class="text-base shrink-0">🏷️</span>
              <span class="font-bold text-sm text-slate-900 dark:text-white truncate">
                {{ cat.name }}
              </span>
            </div>
            <span class="text-[10px] font-mono text-slate-400 bg-slate-100 dark:bg-slate-800 px-2 py-0.5 rounded-full shrink-0">
              #{{ cat.id }}
            </span>
          </div>

          <!-- Stats Badges -->
          <div class="flex items-center gap-2 text-xs">
            <button
              type="button"
              @click="navigateToGallery(cat)"
              class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-sky-50 dark:bg-sky-950/50 text-sky-700 dark:text-sky-300 border border-sky-200 dark:border-sky-800/40 text-[11px] font-medium hover:bg-sky-100 transition-colors"
              title="Bilder dieser Kategorie in der Galerie öffnen"
            >
              <span>🖼️</span>
              <span>{{ cat.asset_count ?? 0 }} Bilder</span>
            </button>

            <span class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300 border border-slate-200 dark:border-white/10 text-[11px] font-medium">
              <span>👤</span>
              <span>{{ cat.profile_count ?? 0 }} Profile</span>
            </span>
          </div>
        </div>

        <!-- Action Row -->
        <div class="mt-4 pt-3 border-t border-slate-100 dark:border-white/5 flex items-center justify-end gap-1.5">
          <Button
            variant="ghost"
            size="xs"
            @click="openEdit(cat)"
            title="Kategorie umbenennen"
          >
            ✏️ Bearbeiten
          </Button>
          <Button
            variant="ghost"
            size="xs"
            class="text-rose-500 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/30"
            @click="promptDelete(cat)"
            title="Kategorie löschen"
          >
            🗑️ Löschen
          </Button>
        </div>
      </div>
    </div>

    <!-- Create / Edit Modal -->
    <Modal
      :open="isEditorOpen"
      size="md"
      @update:open="isEditorOpen = $event"
    >
      <template #header>
        <h3 class="text-sm font-bold text-slate-900 dark:text-white">
          {{ editingCategory.id ? 'Kategorie bearbeiten' : 'Neue Kategorie erstellen' }}
        </h3>
      </template>

      <form @submit.prevent="handleSave" class="space-y-4 text-xs">
        <div>
          <label class="block text-[11px] font-semibold text-slate-700 dark:text-slate-300 mb-1">
            Name der Kategorie <span class="text-rose-500">*</span>
          </label>
          <Input
            v-model="editingCategory.name"
            placeholder="z. B. Porträts, Landschaften, Fantasy..."
            required
            autofocus
          />
        </div>

        <div class="flex items-center justify-end gap-2 pt-3 border-t border-slate-200 dark:border-white/10">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            @click="isEditorOpen = false"
          >
            Abbrechen
          </Button>
          <Button
            type="submit"
            variant="primary"
            size="sm"
            :loading="isSubmitting"
          >
            {{ editingCategory.id ? 'Änderungen speichern' : 'Kategorie anlegen' }}
          </Button>
        </div>
      </form>
    </Modal>

    <!-- Delete Confirmation Dialog -->
    <ConfirmDialog
      :open="isDeleteConfirmOpen"
      :message="`Möchtest du die Kategorie &quot;${categoryToDelete?.name}&quot; wirklich löschen? Bilder bleiben erhalten, verlieren jedoch diese Kategorie-Zuordnung.`"
      @update:open="isDeleteConfirmOpen = $event"
      @confirm="confirmDelete"
    />
  </div>
</template>
