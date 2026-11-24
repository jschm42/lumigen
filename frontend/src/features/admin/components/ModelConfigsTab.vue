<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { useAuthStore } from '@/stores/auth'
import { formatMoney } from '@/utils/format'
import { adminApi } from '@/api/admin'
import { useToastStore } from '@/stores/toast'
import Button from '@/components/ui/Button.vue'
import Modal from '@/components/ui/Modal.vue'
import Input from '@/components/ui/Input.vue'
import Switch from '@/components/ui/Switch.vue'
import Select from '@/components/ui/Select.vue'
import Badge from '@/components/ui/Badge.vue'
import DataTable, { type DataTableColumn } from '@/components/ui/DataTable.vue'
import { useConfirm } from '@/composables/useConfirm'
import Textarea from '@/components/ui/Textarea.vue'
import type { EndpointKind, ModelConfig } from '@/types'

const adminStore = useAdminStore()
const authStore = useAuthStore()
const toastStore = useToastStore()
const confirm = useConfirm()

const columns = computed<DataTableColumn[]>(() => [
  { key: 'name', label: 'Name' },
  { key: 'provider', label: 'Provider' },
  { key: 'model_identifier', label: 'Identifier' },
  { key: 'pricing', label: `Pricing (${currency.value})` },
  { key: 'is_active', label: 'Active' },
  { key: 'is_default', label: 'Default' },
  { key: 'actions', label: 'Actions', align: 'right' },
])

async function handleDelete(model: ModelConfig) {
  const ok = await confirm({
    title: 'Delete model',
    message: `Delete the model configuration "${model.name}"? Existing images keep their metadata.`,
    confirmText: 'Delete',
  })
  if (ok) await adminStore.deleteModelConfig(model.id)
}

// Reference-image support: "auto" stores null so the backend detects it from the model ID.
const IMAGE_INPUT_OPTIONS = [
  { value: 'auto', label: 'Auto-detect from model ID' },
  { value: 'yes', label: 'Supported' },
  { value: 'no', label: 'Not supported' },
]
const imageInputChoice = computed({
  get: () => {
    const value = editingConfig.value.supports_image_input
    return value == null ? 'auto' : value ? 'yes' : 'no'
  },
  set: (choice: string | number) => {
    editingConfig.value.supports_image_input = choice === 'auto' ? null : choice === 'yes'
  },
})

const PRICE_FIELDS = ['price_input_per_mtok', 'price_output_per_mtok', 'price_per_image'] as const
type PriceField = (typeof PRICE_FIELDS)[number]

// Prices are edited as strings so an empty field clears the price.
const priceInputs = ref<Record<PriceField, string>>({
  price_input_per_mtok: '',
  price_output_per_mtok: '',
  price_per_image: '',
})
const priceError = ref('')

const currency = computed(() => authStore.uiSettings.cost_currency || 'USD')
const providerOptions = computed(() =>
  adminStore.providerStatuses.map((p) => ({ value: p.provider, label: p.display_name }))
)

function providerLabel(provider: string) {
  return adminStore.providerStatuses.find((p) => p.provider === provider)?.display_name || provider
}

// --- Custom endpoints (OpenAI-compatible APIs, ComfyUI) ---------------------
const ENDPOINT_KINDS: EndpointKind[] = ['openai_compatible', 'comfyui']
const ENDPOINT_PROVIDER_OPTIONS = [
  { value: 'openai_compatible', label: 'OpenAI-compatible API (custom endpoint)' },
  { value: 'comfyui', label: 'ComfyUI (custom endpoint)' },
]
const RESPONSE_FORMAT_OPTIONS = [
  { value: 'b64_json', label: 'b64_json (default)' },
  { value: 'url', label: 'url (server returns image links)' },
  { value: 'none', label: 'Do not send response_format' },
]
const COMFYUI_PLACEHOLDERS = [
  'prompt',
  'negative_prompt',
  'seed',
  'width',
  'height',
  'batch_size',
  'model',
  'input_image',
].map((name) => `{{${name}}}`)

const editorProviderOptions = computed(() => [...providerOptions.value, ...ENDPOINT_PROVIDER_OPTIONS])
const isEndpointProvider = computed(() => ENDPOINT_KINDS.includes(editingConfig.value.provider as EndpointKind))
const endpointOptions = computed(() =>
  adminStore.endpoints
    .filter((e) => e.kind === editingConfig.value.provider)
    .map((e) => ({ value: e.id, label: e.is_active ? e.name : `${e.name} (inactive)` })),
)
const modelIdentifierPlaceholder = computed(() => {
  if (editingConfig.value.provider === 'comfyui') return 'Checkpoint file, e.g. sd_xl_base_1.0.safetensors'
  if (editingConfig.value.provider === 'openai_compatible') return 'Model name on the server, e.g. flux-dev'
  return 'e.g. fal-ai/flux/schnell'
})

const useCustomWorkflow = ref(false)
const workflowText = ref('')
const responseFormat = ref('b64_json')
const endpointModels = ref<string[]>([])
const isLoadingEndpointModels = ref(false)

function modelLabel(model: ModelConfig): string {
  if (model.endpoint_name) return `${providerLabel(model.provider)} · ${model.endpoint_name}`
  if (model.provider === 'comfyui') return 'ComfyUI'
  if (model.provider === 'openai_compatible') return 'OpenAI-compatible API'
  return providerLabel(model.provider)
}

function fillEndpointOptions(config: Partial<ModelConfig>) {
  const options = config.provider_options || {}
  useCustomWorkflow.value = !!options.workflow
  workflowText.value = options.workflow ? JSON.stringify(options.workflow, null, 2) : ''
  if (!('response_format' in options)) responseFormat.value = 'b64_json'
  else responseFormat.value = options.response_format ? String(options.response_format) : 'none'
  endpointModels.value = []
}

function buildProviderOptions(): Record<string, any> | null {
  if (editingConfig.value.provider === 'comfyui') {
    return useCustomWorkflow.value ? { workflow: workflowText.value } : {}
  }
  if (editingConfig.value.provider === 'openai_compatible') {
    if (responseFormat.value === 'b64_json') return {}
    return { response_format: responseFormat.value === 'none' ? '' : responseFormat.value }
  }
  return null
}

async function loadEndpointModels() {
  const endpointId = editingConfig.value.endpoint_id
  if (!endpointId) return
  isLoadingEndpointModels.value = true
  try {
    endpointModels.value = await adminApi.listEndpointModels(endpointId)
    if (endpointModels.value.length === 0) toastStore.info('The endpoint reported no models.')
  } catch (error: any) {
    endpointModels.value = []
    toastStore.error(error?.response?.data?.detail || 'Could not load models from the endpoint.')
  } finally {
    isLoadingEndpointModels.value = false
  }
}

function pickEndpointModel(model: string | number) {
  const id = String(model)
  editingConfig.value.model_identifier = id
  if (!editingConfig.value.name) editingConfig.value.name = id.split('/').pop()?.slice(0, 50) || id
}

function fillPrices(config: Partial<ModelConfig>) {
  PRICE_FIELDS.forEach((field) => {
    const value = config[field]
    priceInputs.value[field] = value == null ? '' : String(value)
  })
  priceError.value = ''
}

function priceSummary(model: ModelConfig): string {
  const parts: string[] = []
  if (model.price_input_per_mtok != null) parts.push(`in ${formatMoney(model.price_input_per_mtok, currency.value)}`)
  if (model.price_output_per_mtok != null) parts.push(`out ${formatMoney(model.price_output_per_mtok, currency.value)}`)
  const tokenPart = parts.length ? `${parts.join(' / ')} per 1M tokens` : ''
  const imagePart = model.price_per_image != null ? `${formatMoney(model.price_per_image, currency.value)} per image` : ''
  return [tokenPart, imagePart].filter(Boolean).join(' · ') || '—'
}

const isEditorOpen = ref(false)
const isDiscovering = ref(false)
const selectedProvider = ref('openrouter')
const discoveredModels = ref<string[]>([])
// Provider-reported media type per discovered model (image/video).
const discoveredMediaTypes = ref<Record<string, string>>({})

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
  adminStore.fetchEndpoints()
  if (adminStore.providerStatuses.length === 0) adminStore.fetchProviderKeys()
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
  fillPrices({})
  fillEndpointOptions({})
  isEditorOpen.value = true
}

function openEdit(config: ModelConfig) {
  editingConfig.value = { ...config }
  fillPrices(config)
  fillEndpointOptions(config)
  isEditorOpen.value = true
}

// Switching the provider drops an endpoint of the wrong kind and stale discoveries.
watch(
  () => editingConfig.value.provider,
  (provider) => {
    const current = adminStore.endpoints.find((e) => e.id === editingConfig.value.endpoint_id)
    if (!current || current.kind !== provider) {
      const candidates = adminStore.endpoints.filter((e) => e.kind === provider)
      editingConfig.value.endpoint_id = candidates.length === 1 ? candidates[0].id : null
    }
    endpointModels.value = []
  },
)

function addDiscovered(model: string) {
  openNew()
  editingConfig.value.provider = selectedProvider.value
  editingConfig.value.model_identifier = model
  editingConfig.value.name = model.split('/').pop()?.slice(0, 50) || model
}

async function handleSave() {
  if (!editingConfig.value.name || !editingConfig.value.model_identifier) return
  const prices: Partial<Record<PriceField, number | null>> = {}
  for (const field of PRICE_FIELDS) {
    const raw = priceInputs.value[field].trim().replace(',', '.')
    if (!raw) {
      prices[field] = null
      continue
    }
    const value = Number(raw)
    if (!Number.isFinite(value) || value < 0) {
      priceError.value = 'Prices must be non-negative numbers.'
      return
    }
    prices[field] = value
  }
  priceError.value = ''
  try {
    await adminStore.saveModelConfig({
      ...editingConfig.value,
      ...prices,
      endpoint_id: isEndpointProvider.value ? editingConfig.value.endpoint_id ?? null : null,
      provider_options: buildProviderOptions() ?? undefined,
    })
    isEditorOpen.value = false
  } catch (_error) {
    // The store shows the API error (e.g. invalid workflow); keep the editor open.
  }
}

async function handleDiscover() {
  isDiscovering.value = true
  try {
    const res = await adminApi.discoverModels(selectedProvider.value)
    discoveredModels.value = res.models
    discoveredMediaTypes.value = res.media_types || {}
    const videoCount = res.video_models?.length || 0
    toastStore.success(
      videoCount > 0
        ? `Found ${res.count} models from provider (${videoCount} video).`
        : `Found ${res.count} models from provider.`
    )
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Model discovery failed.')
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
        <h3 class="text-sm font-bold text-slate-900 dark:text-white">Model Configurations</h3>
        <p class="text-slate-500">Define which models are available in the studio.</p>
      </div>

      <Button variant="primary" size="sm" @click="openNew">
        <template #icon>+</template>
        Add Model
      </Button>
    </div>

    <!-- Models List -->
    <DataTable
      :columns="columns"
      :rows="adminStore.modelConfigs"
      row-key="id"
      caption="Image model configurations"
      empty-title="No models configured"
      empty-description="Add a model or discover available models from a provider below."
    >
      <template #cell-name="{ row }">
        <span class="font-bold text-slate-900 dark:text-white">{{ row.name }}</span>
      </template>
      <template #cell-provider="{ row }">
        <span class="text-slate-500 dark:text-slate-400">{{ modelLabel(row) }}</span>
      </template>
      <template #cell-model_identifier="{ row }">
        <span class="font-mono">{{ row.model_identifier }}</span>
        <Badge v-if="row.media_type === 'video'" variant="violet" size="xs" class="ml-1.5">Video</Badge>
      </template>
      <template #cell-pricing="{ row }">
        <span class="text-slate-500 dark:text-slate-400">{{ priceSummary(row) }}</span>
      </template>
      <template #cell-is_active="{ row }">
        <Badge :variant="row.is_active ? 'emerald' : 'slate'" size="xs" dot>{{ row.is_active ? 'Active' : 'Inactive' }}</Badge>
      </template>
      <template #cell-is_default="{ row }">
        <Badge v-if="row.is_default" variant="sky" size="xs">Default</Badge>
      </template>
      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-1">
          <Button variant="ghost" size="xs" @click="openEdit(row)">Edit</Button>
          <Button variant="danger-ghost" size="xs" @click="handleDelete(row)">Delete</Button>
        </div>
      </template>
    </DataTable>

    <!-- Provider Model Discovery Box -->
    <div class="p-4 rounded-2xl border border-slate-200/80 bg-white/70 dark:border-white/10 dark:bg-slate-900/70 space-y-3">
      <h4 class="font-bold text-slate-900 dark:text-white">Discover Models from Provider</h4>
      <div class="flex items-center gap-3">
        <Select
          v-model="selectedProvider"
          :options="providerOptions"
          size="sm"
          class="w-48"
          aria-label="Provider to discover models from"
        />
        <Button
          variant="secondary"
          size="sm"
          :loading="isDiscovering"
          @click="handleDiscover"
        >
          Search Available Models
        </Button>
      </div>

      <div v-if="discoveredModels.length > 0" class="max-h-40 overflow-y-auto space-y-1 p-2 bg-slate-100 dark:bg-slate-800 rounded-xl">
        <div
          v-for="m in discoveredModels"
          :key="m"
          class="flex items-center justify-between px-2 py-1 text-slate-700 dark:text-slate-300 hover:bg-white dark:hover:bg-slate-700 rounded cursor-pointer"
          @click="addDiscovered(m)"
        >
          <span class="font-mono flex items-center gap-1.5">
            {{ m }}
            <span
              v-if="discoveredMediaTypes[m] === 'video'"
              class="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-violet-100 text-violet-800 dark:bg-violet-950/60 dark:text-violet-300"
            >🎬 Video</span>
          </span>
          <span class="text-sky-500 font-semibold text-[10px]">+ Add as configuration</span>
        </div>
      </div>
    </div>

    <!-- Model Config Edit Modal -->
    <Modal
      :open="isEditorOpen"
      :title="editingConfig.id ? 'Edit Model' : 'Add New Model'"
      size="md"
      @update:open="isEditorOpen = $event"
    >
      <form @submit.prevent="handleSave" class="space-y-4">
        <Select id="model-provider" v-model="editingConfig.provider" label="Provider" :options="editorProviderOptions" />

        <template v-if="isEndpointProvider">
          <p
            v-if="endpointOptions.length === 0"
            role="alert"
            class="rounded-xl border border-amber-300/70 bg-amber-50 p-3 text-amber-800 dark:border-amber-500/30 dark:bg-amber-950/30 dark:text-amber-200"
          >
            No endpoint of this type exists yet. Add one under <strong>Endpoints</strong> first.
          </p>
          <Select
            v-else
            id="model-endpoint"
            v-model="editingConfig.endpoint_id"
            label="Endpoint"
            placeholder="Select endpoint…"
            :options="endpointOptions"
          />
        </template>

        <Input
          label="Display Name"
          placeholder="e.g. FLUX.1 Schnell"
          v-model="editingConfig.name"
          required
        />

        <div class="space-y-2">
          <Input
            id="model-identifier"
            label="Model Identifier"
            :placeholder="modelIdentifierPlaceholder"
            v-model="editingConfig.model_identifier"
            required
          />
          <div v-if="isEndpointProvider && editingConfig.endpoint_id" class="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="xs"
              :loading="isLoadingEndpointModels"
              data-testid="load-endpoint-models"
              @click="loadEndpointModels"
            >
              {{ editingConfig.provider === 'comfyui' ? 'Load checkpoints' : 'Load models' }}
            </Button>
            <Select
              v-if="endpointModels.length"
              :model-value="editingConfig.model_identifier || ''"
              size="sm"
              class="min-w-0 flex-1"
              aria-label="Pick a model from the endpoint"
              placeholder="Pick from endpoint…"
              :options="endpointModels.map((m) => ({ value: m, label: m }))"
              @update:model-value="pickEndpointModel"
            />
          </div>
        </div>

        <Select
          v-if="editingConfig.provider === 'openai_compatible'"
          v-model="responseFormat"
          label="Response format"
          :options="RESPONSE_FORMAT_OPTIONS"
          hint="Most servers support b64_json. Switch only if the server rejects it."
        />

        <div
          v-if="editingConfig.provider === 'comfyui'"
          class="space-y-3 rounded-xl border border-slate-200 p-3 dark:border-white/10"
        >
          <Switch
            v-model="useCustomWorkflow"
            label="Use a custom workflow"
            description="Off: built-in text-to-image graph with the model identifier as checkpoint."
          />
          <template v-if="useCustomWorkflow">
            <Textarea
              id="model-workflow"
              v-model="workflowText"
              label="Workflow (API format JSON)"
              :rows="10"
              mono
              placeholder='{"3": {"class_type": "KSampler", "inputs": {"seed": "{{seed}}", …}}, …}'
              hint="In ComfyUI use Workflow → Export (API). Put placeholders into the inputs Lumigen should fill."
            />
            <div class="flex flex-wrap gap-1" aria-label="Available placeholders">
              <Badge v-for="placeholder in COMFYUI_PLACEHOLDERS" :key="placeholder" size="xs" class="font-mono">
                {{ placeholder }}
              </Badge>
            </div>
          </template>
        </div>

        <Select
          v-model="imageInputChoice"
          :options="IMAGE_INPUT_OPTIONS"
          label="Reference images"
          hint="Whether the model accepts input images (edit / image-to-image). Required for Agentic GIF animations."
          data-testid="model-image-input"
        />

        <div class="space-y-2 rounded-xl border border-slate-200 p-3 dark:border-white/10">
          <div class="flex items-baseline justify-between gap-2">
            <label class="font-semibold uppercase tracking-wider text-[11px] text-slate-500">Pricing (optional)</label>
            <span class="text-[11px] text-slate-400">Currency: {{ currency }} · change under General</span>
          </div>
          <div class="grid grid-cols-1 gap-2 sm:grid-cols-3">
            <Input
              id="price-input"
              label="Input / 1M tokens"
              placeholder="e.g. 5.00"
              v-model="priceInputs.price_input_per_mtok"
            />
            <Input
              id="price-output"
              label="Output / 1M tokens"
              placeholder="e.g. 40.00"
              v-model="priceInputs.price_output_per_mtok"
            />
            <Input
              id="price-image"
              label="Per image"
              placeholder="e.g. 0.04"
              v-model="priceInputs.price_per_image"
            />
          </div>
          <p class="text-[11px] text-slate-400">
            Leave empty to show only token counts. Token prices apply to providers that report usage;
            the per-image price works for every provider.
          </p>
          <p v-if="priceError" class="text-xs font-medium text-rose-500">{{ priceError }}</p>
        </div>

        <div class="space-y-2 pt-2 border-t border-slate-200 dark:border-white/10">
          <Switch
            label="Model is active"
            description="Available in model selector"
            v-model="editingConfig.is_active"
          />
          <Switch
            label="Default Model"
            description="Selected by default for new sessions"
            v-model="editingConfig.is_default"
          />
        </div>
      </form>

      <template #footer>
        <Button variant="secondary" size="sm" @click="isEditorOpen = false">Cancel</Button>
        <Button variant="primary" size="sm" @click="handleSave">Save</Button>
      </template>
    </Modal>
  </div>
</template>
