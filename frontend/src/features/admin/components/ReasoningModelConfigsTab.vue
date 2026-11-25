<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { useAuthStore } from '@/stores/auth'
import { formatMoney } from '@/utils/format'
import { useToastStore } from '@/stores/toast'
import Button from '@/components/ui/Button.vue'
import Modal from '@/components/ui/Modal.vue'
import Input from '@/components/ui/Input.vue'
import Switch from '@/components/ui/Switch.vue'
import Select from '@/components/ui/Select.vue'
import Badge from '@/components/ui/Badge.vue'
import DataTable, { type DataTableColumn } from '@/components/ui/DataTable.vue'
import ModelDiscovery, { type DiscoveredModelItem } from './ModelDiscovery.vue'
import type { ReasoningModelConfig } from '@/types'
import { useConfirm } from '@/composables/useConfirm'

const adminStore = useAdminStore()
const confirm = useConfirm()
const authStore = useAuthStore()
const toastStore = useToastStore()

const currency = computed(() => authStore.uiSettings.cost_currency || 'USD')

const REASONING_PROVIDERS = [
  { value: 'openrouter', label: 'OpenRouter' },
  { value: 'openai', label: 'OpenAI' },
  { value: 'google', label: 'Google Gemini' },
  { value: 'anthropic', label: 'Anthropic' },
]

const columns = computed<DataTableColumn[]>(() => [
  { key: 'name', label: 'Name' },
  { key: 'provider', label: 'Provider' },
  { key: 'model_identifier', label: 'Identifier' },
  { key: 'pricing', label: `Pricing (${currency.value})` },
  { key: 'custom_key', label: 'Custom Key' },
  { key: 'is_active', label: 'Active' },
  { key: 'is_default', label: 'Default' },
  { key: 'actions', label: 'Actions', align: 'right' },
])

const isEditorOpen = ref(false)
const customApiKey = ref('')
const selectedDiscoveryProvider = ref('openrouter')
const configuredModelIds = computed(() => adminStore.reasoningModels.map((m) => m.model_identifier))
const editorProviderHasKey = computed(() => {
  const provider = editingConfig.value.provider || 'openrouter'
  if (editingConfig.value.use_custom_api_key && editingConfig.value.has_custom_api_key) return true
  if (provider === 'anthropic') return true
  return Boolean(adminStore.providerStatuses.find((p) => p.provider === provider)?.has_key)
})

function pickDiscoveredModel(item: DiscoveredModelItem) {
  editingConfig.value.model_identifier = item.id
  if (!editingConfig.value.name) {
    editingConfig.value.name = item.id.split('/').pop()?.slice(0, 50) || item.id
  }
}

function addDiscovered(item: DiscoveredModelItem) {
  openNew()
  editingConfig.value.provider = selectedDiscoveryProvider.value
  editingConfig.value.model_identifier = item.id
  editingConfig.value.name = item.id.split('/').pop()?.slice(0, 50) || item.id
}

const editingConfig = ref<Partial<ReasoningModelConfig>>({
  id: undefined,
  name: '',
  provider: 'openrouter',
  model_identifier: '',
  description: '',
  use_custom_api_key: false,
  is_default: false,
  is_active: true,
  price_input_per_mtok: null,
  price_output_per_mtok: null,
})

const priceInputPerMtok = ref('')
const priceOutputPerMtok = ref('')

onMounted(() => {
  adminStore.fetchReasoningModels()
  if (adminStore.providerStatuses.length === 0) adminStore.fetchProviderKeys()
})

function openNew() {
  editingConfig.value = {
    id: undefined,
    name: '',
    provider: 'openrouter',
    model_identifier: '',
    description: '',
    use_custom_api_key: false,
    is_default: false,
    is_active: true,
  }
  customApiKey.value = ''
  priceInputPerMtok.value = ''
  priceOutputPerMtok.value = ''
  isEditorOpen.value = true
}

function openEdit(config: ReasoningModelConfig) {
  editingConfig.value = { ...config }
  customApiKey.value = ''
  priceInputPerMtok.value = config.price_input_per_mtok != null ? String(config.price_input_per_mtok) : ''
  priceOutputPerMtok.value = config.price_output_per_mtok != null ? String(config.price_output_per_mtok) : ''
  isEditorOpen.value = true
}

async function handleSave() {
  if (!editingConfig.value.name?.trim() || !editingConfig.value.model_identifier?.trim()) {
    toastStore.warning('Name and Model Identifier are required.')
    return
  }

  const inPrice = priceInputPerMtok.value.trim().replace(',', '.')
  const outPrice = priceOutputPerMtok.value.trim().replace(',', '.')

  const payload: Partial<ReasoningModelConfig> & { custom_api_key?: string } = {
    ...editingConfig.value,
    name: editingConfig.value.name.trim(),
    model_identifier: editingConfig.value.model_identifier.trim(),
    description: editingConfig.value.description?.trim() || undefined,
    price_input_per_mtok: inPrice ? Number(inPrice) : null,
    price_output_per_mtok: outPrice ? Number(outPrice) : null,
  }

  if (editingConfig.value.use_custom_api_key && customApiKey.value.trim()) {
    payload.custom_api_key = customApiKey.value.trim()
  }

  await adminStore.saveReasoningModel(payload)
  isEditorOpen.value = false
}

async function handleDelete(id: number) {
  const ok = await confirm({
    title: 'Delete reasoning model',
    message: 'Are you sure you want to delete this reasoning model configuration?',
    confirmText: 'Delete',
  })
  if (!ok) return
  await adminStore.deleteReasoningModel(id)
}

function priceSummary(model: ReasoningModelConfig): string {
  const parts: string[] = []
  if (model.price_input_per_mtok != null) parts.push(`in ${formatMoney(model.price_input_per_mtok, currency.value)}`)
  if (model.price_output_per_mtok != null) parts.push(`out ${formatMoney(model.price_output_per_mtok, currency.value)}`)
  return parts.length ? `${parts.join(' / ')} per 1M tok` : '—'
}
</script>

<template>
  <div class="space-y-6 text-xs">
    <!-- Top Action Row -->
    <div class="flex items-center justify-between">
      <div class="space-y-0.5">
        <h3 class="text-sm font-bold text-slate-900 dark:text-white">Reasoning Model Configurations</h3>
        <p class="text-slate-500">
          Configure LLM models used for Agentic Mode set planning, decomposition, and prompt enhancement.
        </p>
      </div>

      <Button variant="primary" size="sm" @click="openNew">
        <template #icon>+</template>
        Add Reasoning Model
      </Button>
    </div>

    <!-- Models List Table -->
    <DataTable
      :columns="columns"
      :rows="adminStore.reasoningModels"
      row-key="id"
      caption="Reasoning model configurations"
      empty-title="No reasoning models configured"
      empty-description="Click &quot;Add Reasoning Model&quot; above to get started."
    >
      <template #cell-name="{ row }">
        <div class="font-bold text-slate-900 dark:text-white">{{ row.name }}</div>
        <div v-if="row.description" class="text-2xs text-slate-500 dark:text-slate-400">{{ row.description }}</div>
      </template>
      <template #cell-provider="{ row }">
        <Badge size="xs" class="font-mono">{{ row.provider }}</Badge>
      </template>
      <template #cell-model_identifier="{ row }">
        <span class="font-mono">{{ row.model_identifier }}</span>
      </template>
      <template #cell-pricing="{ row }">
        <span class="text-slate-500 dark:text-slate-400">{{ priceSummary(row) }}</span>
      </template>
      <template #cell-custom_key="{ row }">
        <Badge v-if="row.use_custom_api_key && row.has_custom_api_key" variant="emerald" size="xs">Custom</Badge>
        <span v-else class="text-slate-400">Default provider</span>
      </template>
      <template #cell-is_active="{ row }">
        <Badge :variant="row.is_active ? 'emerald' : 'slate'" size="xs" dot>{{ row.is_active ? 'Active' : 'Inactive' }}</Badge>
      </template>
      <template #cell-is_default="{ row }">
        <Badge v-if="row.is_default" variant="violet" size="xs">Default</Badge>
        <Button
          v-else
          variant="ghost"
          size="xs"
          title="Make this model the default reasoning model"
          @click="adminStore.setDefaultReasoningModel(row.id)"
        >
          Set default
        </Button>
      </template>
      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-1">
          <Button variant="ghost" size="xs" @click="openEdit(row)">Edit</Button>
          <Button variant="danger-ghost" size="xs" @click="handleDelete(row.id)">Delete</Button>
        </div>
      </template>
    </DataTable>

    <!-- Discover Reasoning Models -->
    <ModelDiscovery
      mode="catalog"
      v-model:provider="selectedDiscoveryProvider"
      :providers="REASONING_PROVIDERS"
      purpose="reasoning"
      :configured-ids="configuredModelIds"
      title="Discover Reasoning Models from Provider"
      description="Fetch available LLM and reasoning models from a provider and add them with one click."
      button-label="Search Available Models"
      @select="addDiscovered"
    />

    <!-- Edit / Add Modal -->
    <Modal
      :open="isEditorOpen"
      :title="editingConfig.id ? 'Edit Reasoning Model' : 'New Reasoning Model'"
      size="md"
      @update:open="isEditorOpen = $event"
    >
      <div class="space-y-4">
        <div class="grid grid-cols-2 gap-3">
          <Input
            label="Model Display Name"
            placeholder="e.g. My Reasoning Model"
            v-model="editingConfig.name"
            required
          />
          <Select v-model="editingConfig.provider" label="Provider" :options="REASONING_PROVIDERS" />
        </div>

        <ModelDiscovery
          id="reasoning-model-identifier"
          mode="combobox"
          label="Model Identifier"
          placeholder="e.g. anthropic/claude-3.7-sonnet"
          :required="true"
          v-model="editingConfig.model_identifier"
          :provider="editingConfig.provider || 'openrouter'"
          purpose="reasoning"
          :reasoning-model-id="editingConfig.id"
          :auto-discover="true"
          :can-auto-discover="editorProviderHasKey"
          @select="pickDiscoveredModel"
        />

        <Input
          label="Description (Optional)"
          placeholder="e.g. Reasoning model for image set decomposition"
          v-model="editingConfig.description"
        />

        <!-- Custom API Key Section -->
        <div class="rounded-xl border border-slate-200/80 bg-slate-50/50 p-3 space-y-3 dark:border-white/10 dark:bg-slate-900/40">
          <div class="flex items-center justify-between">
            <span class="text-xs font-medium text-slate-700 dark:text-slate-300">Use Dedicated Custom API Key</span>
            <Switch v-model="editingConfig.use_custom_api_key" />
          </div>
          <div v-if="editingConfig.use_custom_api_key" class="space-y-1 pt-1">
            <Input
              type="password"
              label="API Key"
              placeholder="Enter custom API key for this model..."
              v-model="customApiKey"
            />
            <p v-if="editingConfig.has_custom_api_key" class="text-[10px] text-emerald-600 dark:text-emerald-400">
              ✓ An encrypted API key is currently saved. Enter a new key only if you want to replace it.
            </p>
          </div>
        </div>

        <!-- Token Pricing -->
        <div class="grid grid-cols-2 gap-3">
          <Input
            :label="`Input Price / 1M tokens (${currency})`"
            placeholder="e.g. 0.15"
            v-model="priceInputPerMtok"
          />
          <Input
            :label="`Output Price / 1M tokens (${currency})`"
            placeholder="e.g. 0.60"
            v-model="priceOutputPerMtok"
          />
        </div>

        <!-- Flags -->
        <div class="flex items-center justify-between pt-2">
          <div class="flex items-center gap-2">
            <Switch v-model="editingConfig.is_active" />
            <span class="text-xs text-slate-700 dark:text-slate-300">Active</span>
          </div>

          <div class="flex items-center gap-2">
            <Switch v-model="editingConfig.is_default" />
            <span class="text-xs text-slate-700 dark:text-slate-300">Set as Studio Default</span>
          </div>
        </div>
      </div>

      <template #footer>
        <div class="flex justify-end gap-2">
          <Button variant="ghost" size="sm" @click="isEditorOpen = false">Cancel</Button>
          <Button variant="primary" size="sm" @click="handleSave">Save Configuration</Button>
        </div>
      </template>
    </Modal>
  </div>
</template>
