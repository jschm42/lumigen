<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { adminApi } from '@/api/admin'
import { generationApi } from '@/api/generation'
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
const isRestoring = ref(false)
const isImporting = ref(false)
const styleFileInput = ref<HTMLInputElement | null>(null)
const previewModelId = ref<number | null>(null)

const editingStyle = ref<Partial<StylePreset>>({
  id: undefined,
  name: '',
  description: '',
  prompt_template: '{prompt}',
  negative_prompt: '',
  category: 'General',
})

onMounted(async () => {
  await Promise.all([
    adminStore.fetchStyles(),
    adminStore.fetchModelConfigs(),
  ])
  try {
    const settings = await adminApi.getStylePreviewSettings()
    if (settings.model_config_id) {
      previewModelId.value = settings.model_config_id
    } else if (adminStore.modelConfigs.length > 0) {
      previewModelId.value = adminStore.modelConfigs[0].id
    }
  } catch (_e) {
    if (adminStore.modelConfigs.length > 0) {
      previewModelId.value = adminStore.modelConfigs[0].id
    }
  }
})

async function handleModelChange() {
  if (!previewModelId.value) return
  try {
    const res = await adminApi.updateStylePreviewSettings(previewModelId.value)
    toastStore.success(`Preview-Modell auf "${res.name}" gesetzt.`)
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Fehler beim Speichern des Preview-Modells.')
  }
}

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

function openEdit(style: StylePreset) {
  editingStyle.value = {
    id: style.id,
    name: style.name,
    description: style.description || '',
    prompt_template: style.prompt_template || '',
    negative_prompt: style.negative_prompt || '',
    category: style.category || 'General',
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

async function handleRestoreDefaults() {
  if (!confirm('Möchtest du die Standard-Styles wiederherstellen? Bestehende Standard-Styles werden auf ihre Standardwerte aktualisiert.')) {
    return
  }
  isRestoring.value = true
  try {
    await adminStore.restoreDefaultStyles()
  } finally {
    isRestoring.value = false
  }
}

async function handleImportFile(e: Event) {
  const target = e.target as HTMLInputElement
  if (!target.files || !target.files[0]) return

  const file = target.files[0]
  const formData = new FormData()
  formData.append('file', file)

  isImporting.value = true
  try {
    await adminApi.importData(formData)
    toastStore.success('Styles erfolgreich importiert!')
    await adminStore.fetchStyles()
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Import fehlgeschlagen.')
  } finally {
    isImporting.value = false
    target.value = ''
  }
}

async function generateAiPreview(style: StylePreset) {
  if (!style.id) return
  isGeneratingPreview.value = style.id
  try {
    const res = await adminApi.generateStylePreview(
      style.id,
      undefined,
      previewModelId.value || undefined,
    )
    const modelLabel = res.model_name ? ` (${res.model_name})` : ''
    toastStore.info(`AI Preview für "${style.name}" wird generiert${modelLabel}...`)
    const jobId = res.job_id

    const pollInterval = setInterval(async () => {
      try {
        const job = await generationApi.getJobStatus(jobId)
        if (job.status === 'succeeded') {
          clearInterval(pollInterval)
          toastStore.success(`Vorschaubild für "${style.name}" erfolgreich erstellt!`)
          await adminStore.fetchStyles()
          isGeneratingPreview.value = null
        } else if (job.status === 'failed' || job.status === 'cancelled') {
          clearInterval(pollInterval)
          toastStore.error(job.error_message || 'Preview-Generierung fehlgeschlagen.')
          isGeneratingPreview.value = null
        }
      } catch (_err) {
        clearInterval(pollInterval)
        isGeneratingPreview.value = null
      }
    }, 1500)
  } catch (error: any) {
    isGeneratingPreview.value = null
    toastStore.error(error?.response?.data?.detail || 'Preview-Generierung fehlgeschlagen.')
  }
}
</script>

<template>
  <div class="space-y-6 text-xs">
    <!-- Top Action Row -->
    <div class="flex items-center justify-between flex-wrap gap-3">
      <div class="space-y-0.5">
        <h3 class="text-sm font-bold text-slate-900 dark:text-white">Style Presets</h3>
        <p class="text-slate-500">Verwalte Voreinstellungen für visuelle Stile mit Prompt-Templates und Vorschaubildern.</p>
      </div>

      <div class="flex items-center gap-2 flex-wrap">
        <!-- Preview Model Selector -->
        <div
          v-if="adminStore.modelConfigs.length > 0"
          class="flex items-center gap-2 bg-slate-100 dark:bg-slate-800/90 px-3 py-1.5 rounded-xl border border-slate-200/80 dark:border-white/10 shadow-sm"
        >
          <span class="font-semibold text-[11px] text-slate-500 dark:text-slate-400 whitespace-nowrap">✨ Preview-Modell:</span>
          <select
            v-model="previewModelId"
            @change="handleModelChange"
            class="bg-transparent font-semibold text-slate-800 dark:text-slate-200 text-xs focus:outline-none cursor-pointer pr-1"
          >
            <option
              v-for="m in adminStore.modelConfigs"
              :key="m.id"
              :value="m.id"
              class="dark:bg-slate-900 text-slate-900 dark:text-white"
            >
              {{ m.name }} ({{ m.provider }})
            </option>
          </select>
        </div>

        <input
          ref="styleFileInput"
          type="file"
          accept=".json,.zip"
          class="hidden"
          @change="handleImportFile"
        />

        <Button
          variant="secondary"
          size="sm"
          :loading="isRestoring"
          @click="handleRestoreDefaults"
          title="Stellt die 12 offiziellen Standard-Styles wieder her"
        >
          <span>🔄</span> Defaults wiederherstellen
        </Button>

        <a
          href="/api/admin/export/styles-zip"
          download="lumigen_styles.zip"
          class="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-white/10 bg-slate-100 dark:bg-slate-800/80 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 font-semibold inline-flex items-center gap-1.5 transition-colors shadow-sm"
          title="Alle Styles inklusive Vorschaubilder als ZIP exportieren"
        >
          <span>📦</span> ZIP-Export
        </a>

        <a
          href="/api/admin/export/styles"
          download="lumigen_styles.json"
          class="px-3 py-1.5 rounded-xl border border-slate-200 dark:border-white/10 bg-slate-100 dark:bg-slate-800/80 text-slate-700 dark:text-slate-200 hover:bg-slate-200 dark:hover:bg-slate-700 font-semibold inline-flex items-center gap-1.5 transition-colors shadow-sm"
          title="Styles als JSON-Datei exportieren"
        >
          <span>📄</span> JSON-Export
        </a>

        <Button
          variant="secondary"
          size="sm"
          :loading="isImporting"
          @click="styleFileInput?.click()"
          title="Styles aus einer JSON- oder ZIP-Datei importieren"
        >
          <span>📥</span> Importieren
        </Button>

        <Button variant="primary" size="sm" @click="openNew">
          <template #icon>+</template>
          Style erstellen
        </Button>
      </div>
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
          <div v-if="isGeneratingPreview === style.id" class="flex flex-col items-center gap-2 text-sky-400">
            <div class="w-6 h-6 border-2 border-sky-400 border-t-transparent rounded-full animate-spin"></div>
            <span class="text-[11px] font-medium text-slate-300 animate-pulse">Generiere Preview...</span>
          </div>
          <img
            v-else-if="style.image_url"
            :src="style.image_url"
            :alt="style.name"
            class="w-full h-full object-cover transition-opacity duration-300"
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

          <div class="flex items-center gap-1">
            <Button
              variant="secondary"
              size="xs"
              @click="openEdit(style)"
              title="Style bearbeiten"
            >
              ✏️
            </Button>
            <Button
              variant="danger"
              size="xs"
              @click="adminStore.deleteStyle(style.id)"
              title="Style löschen"
            >
              🗑️
            </Button>
          </div>
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
