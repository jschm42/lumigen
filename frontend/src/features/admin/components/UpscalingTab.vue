<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { adminApi } from '@/api/admin'
import { useToastStore } from '@/stores/toast'
import Button from '@/components/ui/Button.vue'
import Modal from '@/components/ui/Modal.vue'
import Input from '@/components/ui/Input.vue'
import Switch from '@/components/ui/Switch.vue'
import Card from '@/components/ui/Card.vue'
import type { DiscoveredUpscaleModel, UpscaleModel } from '@/types'

const adminStore = useAdminStore()
const toastStore = useToastStore()

const isEditorOpen = ref(false)
const isDiscovering = ref(false)
const discoveredModels = ref<DiscoveredUpscaleModel[]>([])
const selectedPreset = ref<string>('custom')

const editingModel = ref<Partial<UpscaleModel>>({
  id: undefined,
  name: '',
  model_identifier: '',
  params_json: {},
  is_enabled: true,
  is_default: false,
})

const upscaleFactorInput = ref<number>(2)

const falStatus = computed(() => {
  return adminStore.providerStatuses.find((p) => p.provider === 'fal')
})

onMounted(async () => {
  adminStore.fetchProviderKeys()
  adminStore.fetchUpscaleModels()
  handleDiscover()
})

function openNew() {
  selectedPreset.value = discoveredModels.value.length > 0 ? discoveredModels.value[0].endpoint_id : 'custom'
  const first = discoveredModels.value[0]
  editingModel.value = {
    id: undefined,
    name: first ? first.name : '',
    model_identifier: first ? first.endpoint_id : '',
    params_json: {},
    is_enabled: true,
    is_default: false,
  }
  upscaleFactorInput.value = 2
  isEditorOpen.value = true
}

function openEdit(model: UpscaleModel) {
  editingModel.value = { ...model }
  const match = discoveredModels.value.find((m) => m.endpoint_id === model.model_identifier)
  selectedPreset.value = match ? match.endpoint_id : 'custom'
  upscaleFactorInput.value = model.params_json?.upscale_factor || 2
  isEditorOpen.value = true
}

function onPresetChange() {
  if (selectedPreset.value === 'custom') {
    return
  }
  const found = discoveredModels.value.find((m) => m.endpoint_id === selectedPreset.value)
  if (found) {
    editingModel.value.model_identifier = found.endpoint_id
    if (!editingModel.value.name || editingModel.value.name === '') {
      editingModel.value.name = found.name
    }
  }
}

async function handleSave() {
  if (!editingModel.value.name?.trim() || !editingModel.value.model_identifier?.trim()) {
    toastStore.warning('Name and Model Identifier are required.')
    return
  }

  const params = { ...(editingModel.value.params_json || {}) }
  if (upscaleFactorInput.value) {
    params.upscale_factor = Number(upscaleFactorInput.value)
  }

  try {
    await adminStore.saveUpscaleModel({
      ...editingModel.value,
      name: editingModel.value.name.trim(),
      model_identifier: editingModel.value.model_identifier.trim(),
      params_json: params,
    })
    isEditorOpen.value = false
  } catch (_e) {
    // Handled in store toast
  }
}

async function handleDiscover() {
  isDiscovering.value = true
  try {
    const res = await adminApi.discoverUpscaleModels()
    discoveredModels.value = res.models || []
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Failed to discover models from FAL.ai.')
  } finally {
    isDiscovering.value = false
  }
}

async function handleSetDefault(id: number) {
  await adminStore.setDefaultUpscaleModel(id)
}

async function handleToggle(id: number) {
  await adminStore.toggleUpscaleModel(id)
}

async function handleDelete(id: number) {
  if (confirm('Are you sure you want to delete this upscale model configuration?')) {
    await adminStore.deleteUpscaleModel(id)
  }
}
</script>

<template>
  <div class="space-y-6 text-xs">
    <!-- Header & Action Row -->
    <div class="flex items-center justify-between">
      <div class="space-y-0.5">
        <h3 class="text-sm font-bold text-slate-900 dark:text-white">Upscaling Configuration</h3>
        <p class="text-slate-500">
          Configure FAL.ai image-to-image upscale models for high-resolution photo enhancement.
        </p>
      </div>

      <div class="flex items-center gap-2">
        <Button variant="secondary" size="sm" :loading="isDiscovering" @click="handleDiscover">
          <template #icon>🔄</template>
          Refresh FAL Models
        </Button>
        <Button variant="primary" size="sm" @click="openNew">
          <template #icon>+</template>
          Add Upscale Model
        </Button>
      </div>
    </div>

    <!-- FAL Key Status Banner -->
    <Card padding="sm" class="flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div
          class="w-2.5 h-2.5 rounded-full"
          :class="falStatus?.has_key ? 'bg-emerald-500 shadow-sm shadow-emerald-500/50' : 'bg-rose-500 shadow-sm shadow-rose-500/50'"
        />
        <div>
          <span class="font-bold text-slate-900 dark:text-white">FAL.ai API Key: </span>
          <span :class="falStatus?.has_key ? 'text-emerald-600 dark:text-emerald-400 font-semibold' : 'text-rose-600 dark:text-rose-400 font-semibold'">
            {{ falStatus?.has_key ? 'Configured & Ready' : 'Not configured' }}
          </span>
        </div>
      </div>
      <p v-if="!falStatus?.has_key" class="text-rose-500 text-[11px]">
        Upscaling requires a FAL.ai API key. Please save your key in the <strong>API Keys</strong> tab.
      </p>
    </Card>

    <!-- Configured Upscale Models Table -->
    <div class="rounded-2xl border border-slate-200/80 bg-white/70 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/70 overflow-hidden shadow-sm">
      <table class="w-full text-left border-collapse">
        <thead>
          <tr class="border-b border-slate-200 dark:border-white/10 text-slate-500 text-[11px] font-semibold uppercase tracking-wider bg-slate-50/50 dark:bg-slate-950/40">
            <th class="p-3.5">Name</th>
            <th class="p-3.5">FAL Model Identifier</th>
            <th class="p-3.5">Status</th>
            <th class="p-3.5">Default</th>
            <th class="p-3.5 text-right">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-200/60 dark:divide-white/10">
          <tr
            v-for="model in adminStore.upscaleModels"
            :key="model.id"
            class="hover:bg-slate-50/50 dark:hover:bg-white/5 transition-colors"
          >
            <td class="p-3.5 font-bold text-slate-900 dark:text-white">
              {{ model.name }}
            </td>
            <td class="p-3.5 font-mono text-slate-700 dark:text-slate-300">
              {{ model.model_identifier }}
            </td>
            <td class="p-3.5">
              <button
                type="button"
                @click="model.id && handleToggle(model.id)"
                class="px-2 py-0.5 rounded-full text-[10px] font-semibold transition-colors"
                :class="model.is_enabled ? 'bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-400' : 'bg-slate-200 text-slate-600 dark:bg-slate-800 dark:text-slate-400'"
              >
                {{ model.is_enabled ? 'Active' : 'Disabled' }}
              </button>
            </td>
            <td class="p-3.5">
              <span v-if="model.is_default" class="px-2 py-0.5 rounded-full text-[10px] bg-sky-500 text-white font-bold">
                Default
              </span>
              <button
                v-else
                type="button"
                @click="model.id && handleSetDefault(model.id)"
                class="text-[10px] text-slate-400 hover:text-sky-500 font-semibold"
              >
                Set Default
              </button>
            </td>
            <td class="p-3.5 text-right space-x-2">
              <button
                type="button"
                @click="openEdit(model)"
                class="text-sky-500 hover:text-sky-400 font-semibold"
              >
                Edit
              </button>
              <button
                type="button"
                @click="model.id && handleDelete(model.id)"
                class="text-rose-500 hover:text-rose-400 font-semibold"
              >
                Delete
              </button>
            </td>
          </tr>

          <tr v-if="adminStore.upscaleModels.length === 0">
            <td colspan="5" class="p-8 text-center text-slate-400">
              <div class="space-y-2">
                <p class="font-medium text-slate-600 dark:text-slate-300">No upscale models configured yet.</p>
                <p class="text-[11px] text-slate-400">
                  Click "+ Add Upscale Model" or pick a model from the FAL.ai catalog below.
                </p>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Quick Add from Discovered Models -->
    <div v-if="discoveredModels.length > 0" class="p-4 rounded-2xl border border-slate-200/80 bg-white/70 dark:border-white/10 dark:bg-slate-900/70 space-y-3">
      <div class="flex items-center justify-between">
        <div>
          <h4 class="font-bold text-slate-900 dark:text-white">Available FAL.ai Models</h4>
          <p class="text-slate-500 text-[11px]">Click on any model to configure it for upscaling in your studio.</p>
        </div>
        <span class="px-2 py-0.5 rounded-full text-[10px] bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-300">
          {{ discoveredModels.length }} models found
        </span>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-2 max-h-56 overflow-y-auto pr-1">
        <div
          v-for="m in discoveredModels"
          :key="m.endpoint_id"
          @click="editingModel = { id: undefined, name: m.name, model_identifier: m.endpoint_id, is_enabled: true, is_default: false, params_json: {} }; selectedPreset = m.endpoint_id; isEditorOpen = true"
          class="p-2.5 rounded-xl border border-slate-200/60 dark:border-white/5 bg-slate-50/50 dark:bg-slate-800/40 hover:border-sky-500/50 hover:bg-sky-500/5 transition-all cursor-pointer flex items-center justify-between group"
        >
          <div class="space-y-0.5 overflow-hidden pr-2">
            <div class="font-bold text-slate-800 dark:text-slate-200 truncate group-hover:text-sky-500 transition-colors">
              {{ m.name }}
            </div>
            <div class="font-mono text-[10px] text-slate-400 truncate">
              {{ m.endpoint_id }}
            </div>
          </div>
          <span class="text-xs text-sky-500 opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap">
            + Use
          </span>
        </div>
      </div>
    </div>

    <!-- Edit/Add Modal -->
    <Modal :open="isEditorOpen" :title="editingModel.id ? 'Edit Upscale Model' : 'Add Upscale Model'" @update:open="isEditorOpen = $event" @close="isEditorOpen = false">
      <div class="space-y-4">
        <!-- Preset Selector -->
        <div class="space-y-1">
          <label class="block text-slate-700 dark:text-slate-300 font-semibold">Select Model Template</label>
          <select
            v-model="selectedPreset"
            @change="onPresetChange"
            class="w-full rounded-xl border border-slate-300/80 bg-white px-3 py-2 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option value="custom">Custom / Manual Input</option>
            <option
              v-for="m in discoveredModels"
              :key="m.endpoint_id"
              :value="m.endpoint_id"
            >
              {{ m.name }} ({{ m.endpoint_id }})
            </option>
          </select>
        </div>

        <!-- Name Input -->
        <div class="space-y-1">
          <label class="block text-slate-700 dark:text-slate-300 font-semibold">Display Name</label>
          <Input
            v-model="editingModel.name"
            placeholder="e.g. Clarity Upscaler"
          />
        </div>

        <!-- Identifier Input -->
        <div class="space-y-1">
          <label class="block text-slate-700 dark:text-slate-300 font-semibold">FAL Model Identifier</label>
          <Input
            v-model="editingModel.model_identifier"
            placeholder="e.g. fal-ai/clarity-upscaler"
          />
          <p class="text-[10px] text-slate-400">
            The endpoint ID hosted on FAL.ai (e.g. <code>fal-ai/clarity-upscaler</code>, <code>fal-ai/esrgan</code>).
          </p>
        </div>

        <!-- Upscale Factor -->
        <div class="space-y-1">
          <label class="block text-slate-700 dark:text-slate-300 font-semibold">Upscale Factor</label>
          <select
            v-model="upscaleFactorInput"
            class="w-full rounded-xl border border-slate-300/80 bg-white px-3 py-2 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900 dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-sky-500"
          >
            <option :value="2">2x Resolution</option>
            <option :value="4">4x Resolution</option>
          </select>
        </div>

        <!-- Switches -->
        <div class="pt-2 space-y-3">
          <div class="flex items-center justify-between">
            <span class="text-slate-700 dark:text-slate-300 font-semibold">Active / Enabled</span>
            <Switch v-model="editingModel.is_enabled" />
          </div>

          <div class="flex items-center justify-between">
            <span class="text-slate-700 dark:text-slate-300 font-semibold">Studio Default Model</span>
            <Switch v-model="editingModel.is_default" />
          </div>
        </div>

        <!-- Actions -->
        <div class="flex justify-end gap-2 pt-4">
          <Button variant="secondary" @click="isEditorOpen = false">Cancel</Button>
          <Button variant="primary" @click="handleSave">Save Model</Button>
        </div>
      </div>
    </Modal>
  </div>
</template>
