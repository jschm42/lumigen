<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { adminApi } from '@/api/admin'
import { useToastStore } from '@/stores/toast'
import Button from '@/components/ui/Button.vue'
import Modal from '@/components/ui/Modal.vue'
import Input from '@/components/ui/Input.vue'
import Switch from '@/components/ui/Switch.vue'
import type { ModelConfig } from '@/types'

const adminStore = useAdminStore()
const toastStore = useToastStore()

const isEditorOpen = ref(false)
const isDiscovering = ref(false)
const selectedProvider = ref('openrouter')
const discoveredModels = ref<string[]>([])

const editingConfig = ref<Partial<ModelConfig>>({
  id: undefined,
  name: '',
  provider: 'openrouter',
  model_identifier: '',
  is_active: true,
  is_default: false,
  supported_aspect_ratios: ['1:1', '16:9', '9:16'],
  supported_resolutions: ['1K', '2K'],
})

onMounted(() => {
  adminStore.fetchModelConfigs()
})

function openNew() {
  editingConfig.value = {
    id: undefined,
    name: '',
    provider: 'openrouter',
    model_identifier: '',
    is_active: true,
    is_default: false,
    supported_aspect_ratios: ['1:1', '16:9', '9:16'],
    supported_resolutions: ['1K', '2K'],
  }
  isEditorOpen.value = true
}

function openEdit(config: ModelConfig) {
  editingConfig.value = { ...config }
  isEditorOpen.value = true
}

async function handleSave() {
  if (!editingConfig.value.name || !editingConfig.value.model_identifier) return
  await adminStore.saveModelConfig(editingConfig.value)
  isEditorOpen.value = false
}

async function handleDiscover() {
  isDiscovering.value = true
  try {
    const res = await adminApi.discoverModels(selectedProvider.value)
    discoveredModels.value = res.models
    toastStore.success(`${res.count} Modelle vom Provider gefunden.`)
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Modell-Erkennung fehlgeschlagen.')
  } finally {
    isDiscovering.value = false
  }
}
</script>

<template>
  <div class="space-y-6 text-xs">
    <!-- Top Action Row -->
    <div class="flex items-center justify-between">
      <div class="space-y-0.5">
        <h3 class="text-sm font-bold text-slate-900 dark:text-white">Modell-Konfigurationen</h3>
        <p class="text-slate-500">Definiere, welche Modelle im Studio zur Verfügung stehen.</p>
      </div>

      <Button variant="primary" size="sm" @click="openNew">
        <template #icon>+</template>
        Modell hinzufügen
      </Button>
    </div>

    <!-- Models List -->
    <div class="rounded-2xl border border-slate-200/80 bg-white/70 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/70 overflow-hidden shadow-sm">
      <table class="w-full text-left border-collapse">
        <thead>
          <tr class="border-b border-slate-200 dark:border-white/10 text-slate-500 text-[11px] font-semibold uppercase tracking-wider bg-slate-50/50 dark:bg-slate-950/40">
            <th class="p-3.5">Name</th>
            <th class="p-3.5">Provider</th>
            <th class="p-3.5">Identifier</th>
            <th class="p-3.5">Aktiv</th>
            <th class="p-3.5">Standard</th>
            <th class="p-3.5 text-right">Aktionen</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-200/60 dark:divide-white/10">
          <tr
            v-for="model in adminStore.modelConfigs"
            :key="model.id"
            class="hover:bg-slate-50/50 dark:hover:bg-white/5 transition-colors"
          >
            <td class="p-3.5 font-bold text-slate-900 dark:text-white">{{ model.name }}</td>
            <td class="p-3.5 uppercase font-mono text-[10px] text-slate-500">{{ model.provider }}</td>
            <td class="p-3.5 font-mono text-slate-700 dark:text-slate-300">{{ model.model_identifier }}</td>
            <td class="p-3.5">
              <span :class="model.is_active ? 'text-emerald-500 font-bold' : 'text-slate-400'">
                {{ model.is_active ? 'Ja' : 'Nein' }}
              </span>
            </td>
            <td class="p-3.5">
              <span v-if="model.is_default" class="px-2 py-0.5 rounded-full text-[10px] bg-sky-500 text-white font-bold">
                Default
              </span>
            </td>
            <td class="p-3.5 text-right space-x-2">
              <button
                type="button"
                @click="openEdit(model)"
                class="text-sky-500 hover:text-sky-400 font-semibold"
              >
                Bearbeiten
              </button>
              <button
                type="button"
                @click="adminStore.deleteModelConfig(model.id)"
                class="text-rose-500 hover:text-rose-400 font-semibold"
              >
                Löschen
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Provider Model Discovery Box -->
    <div class="p-4 rounded-2xl border border-slate-200/80 bg-white/70 dark:border-white/10 dark:bg-slate-900/70 space-y-3">
      <h4 class="font-bold text-slate-900 dark:text-white">Modelle vom Provider abfragen</h4>
      <div class="flex items-center gap-3">
        <select
          v-model="selectedProvider"
          class="rounded-xl border border-slate-300/80 bg-white px-3 py-1.5 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="openrouter">OpenRouter</option>
          <option value="fal">FAL.AI</option>
          <option value="openai">OpenAI</option>
          <option value="google">Google Gemini</option>
        </select>
        <Button
          variant="secondary"
          size="sm"
          :loading="isDiscovering"
          @click="handleDiscover"
        >
          Verfügbare Modelle suchen
        </Button>
      </div>

      <div v-if="discoveredModels.length > 0" class="max-h-40 overflow-y-auto space-y-1 p-2 bg-slate-100 dark:bg-slate-800 rounded-xl">
        <div
          v-for="m in discoveredModels"
          :key="m"
          class="flex items-center justify-between px-2 py-1 text-slate-700 dark:text-slate-300 hover:bg-white dark:hover:bg-slate-700 rounded cursor-pointer"
          @click="editingConfig.model_identifier = m; editingConfig.name = m; isEditorOpen = true"
        >
          <span class="font-mono">{{ m }}</span>
          <span class="text-sky-500 font-semibold text-[10px]">+ Als Konfiguration anlegen</span>
        </div>
      </div>
    </div>

    <!-- Model Config Edit Modal -->
    <Modal
      :open="isEditorOpen"
      :title="editingConfig.id ? 'Modell bearbeiten' : 'Neues Modell anlegen'"
      size="md"
      @update:open="isEditorOpen = $event"
    >
      <form @submit.prevent="handleSave" class="space-y-4">
        <Input
          label="Anzeigename"
          placeholder="z.B. FLUX.1 Schnell"
          v-model="editingConfig.name"
          required
        />

        <Input
          label="Modell Identifier"
          placeholder="z.B. fal-ai/flux/schnell"
          v-model="editingConfig.model_identifier"
          required
        />

        <div>
          <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500 mb-1.5">
            Provider
          </label>
          <select
            v-model="editingConfig.provider"
            class="w-full rounded-xl border border-slate-300/80 bg-white px-3 py-2 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="openrouter">OpenRouter</option>
            <option value="fal">FAL.AI</option>
            <option value="openai">OpenAI</option>
            <option value="bfl">Black Forest Labs</option>
            <option value="google">Google Gemini</option>
          </select>
        </div>

        <div class="space-y-2 pt-2 border-t border-slate-200 dark:border-white/10">
          <Switch
            label="Modell ist aktiv"
            description="Steht in der Modellauswahl zur Verfügung"
            v-model="editingConfig.is_active"
          />
          <Switch
            label="Standard-Modell"
            description="Wird standardmäßig für neue Sessions ausgewählt"
            v-model="editingConfig.is_default"
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
