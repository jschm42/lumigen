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
import Select from '@/components/ui/Select.vue'
import Badge from '@/components/ui/Badge.vue'
import DataTable, { type DataTableColumn } from '@/components/ui/DataTable.vue'
import type { DiscoveredUpscaleModel, UpscaleModel } from '@/types'
import { useConfirm } from '@/composables/useConfirm'

const adminStore = useAdminStore()
const confirm = useConfirm()
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

const UPSCALE_FACTORS = [
  { value: 2, label: '2x Resolution' },
  { value: 4, label: '4x Resolution' },
]

const columns: DataTableColumn[] = [
  { key: 'name', label: 'Name' },
  { key: 'model_identifier', label: 'FAL Model Identifier' },
  { key: 'is_enabled', label: 'Enabled' },
  { key: 'is_default', label: 'Default' },
  { key: 'actions', label: 'Actions', align: 'right' },
]

const presetOptions = computed(() => [
  { value: 'custom', label: 'Custom / Manual Input' },
  ...discoveredModels.value.map((m) => ({ value: m.endpoint_id, label: `${m.name} (${m.endpoint_id})` })),
])

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

function onPresetChange(value: string | number) {
  selectedPreset.value = String(value)
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
  const ok = await confirm({
    title: 'Delete upscale model',
    message: 'Are you sure you want to delete this upscale model configuration?',
    confirmText: 'Delete',
  })
  if (ok) await adminStore.deleteUpscaleModel(id)
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
    <DataTable
      :columns="columns"
      :rows="adminStore.upscaleModels"
      :row-key="(row) => row.id ?? row.model_identifier"
      caption="Upscale model configurations"
      empty-title="No upscale models configured yet"
      empty-description="Click &quot;Add Upscale Model&quot; or pick a model from the FAL.ai catalog below."
    >
      <template #cell-name="{ row }">
        <span class="font-bold text-slate-900 dark:text-white">{{ row.name }}</span>
      </template>
      <template #cell-model_identifier="{ row }">
        <span class="font-mono">{{ row.model_identifier }}</span>
      </template>
      <template #cell-is_enabled="{ row }">
        <Switch
          :model-value="row.is_enabled"
          :aria-label="`${row.is_enabled ? 'Disable' : 'Enable'} ${row.name}`"
          @update:model-value="row.id && handleToggle(row.id)"
        />
      </template>
      <template #cell-is_default="{ row }">
        <Badge v-if="row.is_default" variant="sky" size="xs">Default</Badge>
        <Button v-else variant="ghost" size="xs" @click="row.id && handleSetDefault(row.id)">Set default</Button>
      </template>
      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-1">
          <Button variant="ghost" size="xs" @click="openEdit(row)">Edit</Button>
          <Button variant="danger-ghost" size="xs" @click="row.id && handleDelete(row.id)">Delete</Button>
        </div>
      </template>
    </DataTable>


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
        <Select
          label="Model Template"
          :options="presetOptions"
          :model-value="selectedPreset"
          @update:model-value="onPresetChange"
        />

        <!-- Name Input -->
        <Input v-model="editingModel.name" label="Display Name" placeholder="e.g. Clarity Upscaler" />

        <!-- Identifier Input -->
        <Input
          v-model="editingModel.model_identifier"
          label="FAL Model Identifier"
          placeholder="e.g. fal-ai/clarity-upscaler"
          hint="The endpoint ID hosted on FAL.ai, e.g. fal-ai/clarity-upscaler or fal-ai/esrgan."
        />

        <!-- Upscale Factor -->
        <Select v-model="upscaleFactorInput" label="Upscale Factor" :options="UPSCALE_FACTORS" />

        <!-- Switches -->
        <div class="pt-2 space-y-3">
          <Switch v-model="editingModel.is_enabled" label="Active / Enabled" />
          <Switch v-model="editingModel.is_default" label="Studio Default Model" />
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
