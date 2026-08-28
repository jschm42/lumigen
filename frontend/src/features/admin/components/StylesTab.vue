<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { adminApi } from '@/api/admin'
import { useToastStore } from '@/stores/toast'
import Button from '@/components/ui/Button.vue'
import Modal from '@/components/ui/Modal.vue'
import Input from '@/components/ui/Input.vue'
import Textarea from '@/components/ui/Textarea.vue'
import type { StylePreset } from '@/types'

const adminStore = useAdminStore()
const toastStore = useToastStore()

const isEditorOpen = ref(false)
const isGeneratingPreview = ref<string | number | null>(null)
const previewImageFile = ref<File | null>(null)

const editingStyle = ref<Partial<StylePreset>>({
  id: undefined,
  name: '',
  description: '',
  prompt_template: '{prompt}',
  negative_prompt: '',
  category: 'General',
})

onMounted(() => {
  adminStore.fetchStyles()
})

function openNew() {
  editingStyle.value = {
    id: undefined,
    name: '',
    description: '',
    prompt_template: '{prompt}, cinematic lighting, 8k',
    negative_prompt: '',
    category: 'General',
  }
  previewImageFile.value = null
  isEditorOpen.value = true
}

function handleFileChange(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files && target.files[0]) {
    previewImageFile.value = target.files[0]
  }
}

async function handleSave() {
  if (!editingStyle.value.name?.trim()) return

  const formData = new FormData()
  if (editingStyle.value.id) formData.append('id', String(editingStyle.value.id))
  formData.append('name', editingStyle.value.name)
  if (editingStyle.value.description) formData.append('description', editingStyle.value.description)
  if (editingStyle.value.prompt_template) formData.append('prompt_template', editingStyle.value.prompt_template)
  if (editingStyle.value.negative_prompt) formData.append('negative_prompt', editingStyle.value.negative_prompt)
  if (editingStyle.value.category) formData.append('category', editingStyle.value.category)
  if (previewImageFile.value) formData.append('image', previewImageFile.value)

  try {
    await adminApi.saveStyle(formData)
    toastStore.success('Style gespeichert!')
    adminStore.fetchStyles()
    isEditorOpen.value = false
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Fehler beim Speichern des Styles.')
  }
}

async function generateAiPreview(style: StylePreset) {
  isGeneratingPreview.value = style.id
  try {
    await adminApi.generateStylePreview(style.id)
    toastStore.success('Preview-Generierung gestartet!')
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Preview-Generierung fehlgeschlagen.')
  } finally {
    isGeneratingPreview.value = null
  }
}
</script>

<template>
  <div class="space-y-6 text-xs">
    <!-- Top Action Row -->
    <div class="flex items-center justify-between">
      <div class="space-y-0.5">
        <h3 class="text-sm font-bold text-slate-900 dark:text-white">Style Presets</h3>
        <p class="text-slate-500">Verwalte Voreinstellungen für visuelle Stile mit Prompt-Templates und Vorschaubildern.</p>
      </div>

      <Button variant="primary" size="sm" @click="openNew">
        <template #icon>+</template>
        Style erstellen
      </Button>
    </div>

    <!-- Styles Grid -->
    <div class="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4">
      <div
        v-for="style in adminStore.styles"
        :key="style.id"
        class="rounded-2xl border border-slate-200/80 bg-white/70 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/70 overflow-hidden shadow-sm flex flex-col justify-between"
      >
        <!-- Thumbnail -->
        <div class="aspect-video w-full bg-slate-900 relative overflow-hidden flex items-center justify-center">
          <img
            v-if="style.image_url"
            :src="style.image_url"
            :alt="style.name"
            class="w-full h-full object-cover"
          />
          <div v-else class="text-3xl text-slate-600">🎨</div>
        </div>

        <!-- Body -->
        <div class="p-4 space-y-2 flex-1">
          <h4 class="font-bold text-sm text-slate-900 dark:text-white truncate">{{ style.name }}</h4>
          <p v-if="style.description" class="text-slate-500 line-clamp-2">{{ style.description }}</p>
          <div class="p-2 rounded-lg bg-slate-100 dark:bg-slate-800/80 font-mono text-[10px] text-slate-700 dark:text-slate-300 break-words">
            {{ style.prompt_template }}
          </div>
        </div>

        <!-- Footer -->
        <div class="p-3 border-t border-slate-200/60 dark:border-white/10 flex items-center justify-between gap-2">
          <Button
            variant="secondary"
            size="xs"
            :loading="isGeneratingPreview === style.id"
            @click="generateAiPreview(style)"
            title="Generiert ein AI Vorschaubild für diesen Style"
          >
            ✨ AI Preview
          </Button>

          <Button
            variant="danger"
            size="xs"
            @click="adminStore.deleteStyle(style.id)"
          >
            🗑️
          </Button>
        </div>
      </div>
    </div>

    <!-- Style Editor Modal -->
    <Modal
      :open="isEditorOpen"
      :title="editingStyle.id ? 'Style bearbeiten' : 'Neuen Style erstellen'"
      size="md"
      @update:open="isEditorOpen = $event"
    >
      <form @submit.prevent="handleSave" class="space-y-4">
        <Input
          label="Style Name"
          placeholder="z.B. Cyberpunk Neon"
          v-model="editingStyle.name"
          required
        />

        <Input
          label="Beschreibung"
          placeholder="Kurze visuelle Beschreibung..."
          v-model="editingStyle.description"
        />

        <Textarea
          label="Prompt Template (Verwende {prompt})"
          placeholder="{prompt}, cyberpunk style, neon lights, 8k"
          v-model="editingStyle.prompt_template"
          :rows="3"
          required
        />

        <div>
          <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500 mb-1.5">
            Vorschaubild hochladen (Optional)
          </label>
          <input
            type="file"
            accept="image/*"
            @change="handleFileChange"
            class="text-xs text-slate-600 dark:text-slate-400 file:mr-3 file:py-1 file:px-3 file:rounded-xl file:border-0 file:text-xs file:font-semibold file:bg-sky-50 file:text-sky-700 hover:file:bg-sky-100"
          />
        </div>
      </form>

      <template #footer>
        <Button variant="secondary" size="sm" @click="isEditorOpen = false">Abbrechen</Button>
        <Button variant="primary" size="sm" @click="handleSave">Speichern</Button>
      </template>
    </Modal>
  </div>
</template>
