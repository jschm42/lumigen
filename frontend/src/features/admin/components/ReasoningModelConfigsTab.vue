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
import type { ReasoningModelConfig } from '@/types'

const adminStore = useAdminStore()
const authStore = useAuthStore()
const toastStore = useToastStore()

const currency = computed(() => authStore.uiSettings.cost_currency || 'USD')

const isEditorOpen = ref(false)
const customApiKey = ref('')

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
  if (!confirm('Are you sure you want to delete this reasoning model configuration?')) return
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
    <div class="rounded-2xl border border-slate-200/80 bg-white/70 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/70 overflow-hidden shadow-sm">
      <table class="w-full text-left border-collapse">
        <thead>
          <tr class="border-b border-slate-200 dark:border-white/10 text-slate-500 text-[11px] font-semibold uppercase tracking-wider bg-slate-50/50 dark:bg-slate-950/40">
            <th class="p-3.5">Name</th>
            <th class="p-3.5">Provider</th>
            <th class="p-3.5">Identifier</th>
            <th class="p-3.5">Pricing ({{ currency }})</th>
            <th class="p-3.5">Custom Key</th>
            <th class="p-3.5">Active</th>
            <th class="p-3.5">Default</th>
            <th class="p-3.5 text-right">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-200/60 dark:divide-white/10">
          <tr v-if="adminStore.reasoningModels.length === 0">
            <td colspan="8" class="p-8 text-center text-slate-400">
              No reasoning models configured yet. Click "Add Reasoning Model" above to get started.
            </td>
          </tr>
          <tr
            v-for="model in adminStore.reasoningModels"
            :key="model.id"
            class="hover:bg-slate-50/50 dark:hover:bg-white/5 transition-colors"
          >
            <td class="p-3.5">
              <div class="font-bold text-slate-900 dark:text-white">{{ model.name }}</div>
              <div v-if="model.description" class="text-[11px] text-slate-500 dark:text-slate-400">
                {{ model.description }}
              </div>
            </td>
            <td class="p-3.5">
              <span class="px-2 py-0.5 rounded-md font-mono text-[11px] font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300">
                {{ model.provider }}
              </span>
            </td>
            <td class="p-3.5 font-mono text-slate-700 dark:text-slate-300">
              {{ model.model_identifier }}
            </td>
            <td class="p-3.5 text-[11px] text-slate-500">
              {{ priceSummary(model) }}
            </td>
            <td class="p-3.5 text-[11px]">
              <span v-if="model.use_custom_api_key && model.has_custom_api_key" class="text-emerald-600 font-semibold dark:text-emerald-400">
                Custom
              </span>
              <span v-else class="text-slate-400">
                Default provider
              </span>
            </td>
            <td class="p-3.5">
              <span :class="model.is_active ? 'text-emerald-500 font-bold' : 'text-slate-400'">
                {{ model.is_active ? 'Yes' : 'No' }}
              </span>
            </td>
            <td class="p-3.5">
              <span
                v-if="model.is_default"
                class="px-2 py-0.5 rounded-full text-[10px] bg-indigo-600 text-white font-bold"
              >
                Default
              </span>
              <button
                v-else
                type="button"
                @click="adminStore.setDefaultReasoningModel(model.id)"
                class="text-[11px] text-slate-400 hover:text-indigo-500 font-medium"
                title="Make this model the default reasoning model"
              >
                Set Default
              </button>
            </td>
            <td class="p-3.5 text-right space-x-2">
              <button
                type="button"
                @click="openEdit(model)"
                class="text-sky-500 hover:text-sky-400 font-semibold cursor-pointer"
              >
                Edit
              </button>
              <button
                type="button"
                @click="handleDelete(model.id)"
                class="text-rose-500 hover:text-rose-400 font-semibold cursor-pointer"
              >
                Delete
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

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
          <div class="space-y-1">
            <label class="block text-xs font-medium text-slate-700 dark:text-slate-300">Provider</label>
            <select
              v-model="editingConfig.provider"
              class="w-full rounded-xl border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 focus:outline-none dark:border-white/10 dark:bg-slate-900 dark:text-white"
            >
              <option value="openrouter">OpenRouter</option>
              <option value="openai">OpenAI</option>
              <option value="google">Google Gemini</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </div>
        </div>

        <Input
          label="Model Identifier"
          placeholder="e.g. anthropic/claude-3.7-sonnet"
          v-model="editingConfig.model_identifier"
          required
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
