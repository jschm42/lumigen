<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { CheckCircle2, Plug, Plus, XCircle } from 'lucide-vue-next'
import { adminApi } from '@/api/admin'
import { useAdminStore } from '@/stores/admin'
import { useConfirm } from '@/composables/useConfirm'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import DataTable, { type DataTableColumn } from '@/components/ui/DataTable.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import Input from '@/components/ui/Input.vue'
import Modal from '@/components/ui/Modal.vue'
import Select from '@/components/ui/Select.vue'
import Switch from '@/components/ui/Switch.vue'
import type { CustomEndpoint, CustomEndpointInput, EndpointKind, EndpointTestResult } from '@/types'

const adminStore = useAdminStore()
const confirm = useConfirm()

const KIND_OPTIONS: { value: EndpointKind; label: string }[] = [
  { value: 'openai_compatible', label: 'OpenAI-compatible API' },
  { value: 'comfyui', label: 'ComfyUI' },
]

const KIND_HINTS: Record<EndpointKind, { placeholder: string; hint: string }> = {
  openai_compatible: {
    placeholder: 'http://localhost:8080/v1',
    hint: 'Base URL including the version path, e.g. /v1. Lumigen calls /images/generations and /models on it.',
  },
  comfyui: {
    placeholder: 'http://127.0.0.1:8188',
    hint: 'Address of the ComfyUI server (the URL you open in the browser).',
  },
}

const columns: DataTableColumn[] = [
  { key: 'name', label: 'Name' },
  { key: 'kind', label: 'Type' },
  { key: 'base_url', label: 'Base URL' },
  { key: 'has_api_key', label: 'API Key' },
  { key: 'model_count', label: 'Models' },
  { key: 'is_active', label: 'Status' },
  { key: 'actions', label: 'Actions', align: 'right' },
]

const isEditorOpen = ref(false)
const isSaving = ref(false)
const isTesting = ref(false)
const testResult = ref<EndpointTestResult | null>(null)
const form = ref<CustomEndpointInput>(emptyForm())
const storedKey = ref(false)

const kindHint = computed(() => KIND_HINTS[form.value.kind])
const isKindLocked = computed(
  () => !!form.value.id && (adminStore.endpoints.find((e) => e.id === form.value.id)?.model_count ?? 0) > 0,
)
const canSave = computed(() => form.value.name.trim() !== '' && form.value.base_url.trim() !== '')

function emptyForm(): CustomEndpointInput {
  return { name: '', kind: 'openai_compatible', base_url: '', api_key: '', clear_api_key: false, is_active: true }
}

onMounted(() => {
  adminStore.fetchEndpoints()
})

function openNew() {
  form.value = emptyForm()
  storedKey.value = false
  testResult.value = null
  isEditorOpen.value = true
}

function openEdit(endpoint: CustomEndpoint) {
  form.value = {
    id: endpoint.id,
    name: endpoint.name,
    kind: endpoint.kind,
    base_url: endpoint.base_url,
    api_key: '',
    clear_api_key: false,
    is_active: endpoint.is_active,
  }
  storedKey.value = endpoint.has_api_key
  testResult.value = null
  isEditorOpen.value = true
}

async function handleTest() {
  isTesting.value = true
  testResult.value = null
  try {
    testResult.value = await adminApi.testEndpoint(form.value)
  } catch (error: any) {
    testResult.value = {
      success: false,
      message: error?.response?.data?.detail || 'Connection test failed.',
      models: [],
    }
  } finally {
    isTesting.value = false
  }
}

async function handleSave() {
  if (!canSave.value) return
  isSaving.value = true
  try {
    await adminStore.saveEndpoint(form.value)
    isEditorOpen.value = false
  } catch (_error) {
    // Error toast is shown by the store; keep the editor open for corrections.
  } finally {
    isSaving.value = false
  }
}

async function handleToggleActive(endpoint: CustomEndpoint, active: boolean) {
  await adminStore.saveEndpoint({
    id: endpoint.id,
    name: endpoint.name,
    kind: endpoint.kind,
    base_url: endpoint.base_url,
    is_active: active,
  })
}

async function handleDelete(endpoint: CustomEndpoint) {
  const ok = await confirm({
    title: 'Delete endpoint',
    message: `Delete the endpoint "${endpoint.name}"? Models that use it must be deleted or moved first.`,
    confirmText: 'Delete',
  })
  if (ok) await adminStore.deleteEndpoint(endpoint.id)
}
</script>

<template>
  <div class="space-y-6 text-xs">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="space-y-0.5">
        <h3 class="text-sm font-bold text-slate-900 dark:text-white">Custom Endpoints</h3>
        <p class="max-w-2xl text-slate-500 dark:text-slate-400">
          Connect your own OpenAI-compatible image APIs (LocalAI, LiteLLM, vLLM, hosted gateways) and ComfyUI
          servers. Afterwards add models for them under <strong>Image Models</strong>.
        </p>
      </div>
      <Button variant="primary" size="sm" data-testid="add-endpoint" @click="openNew">
        <template #icon><Plus class="size-4" aria-hidden="true" /></template>
        Add Endpoint
      </Button>
    </div>

    <DataTable :columns="columns" :rows="adminStore.endpoints" row-key="id" caption="Custom endpoints">
      <template #empty>
        <EmptyState
          :icon="Plug"
          title="No custom endpoints yet"
          description="Add an OpenAI-compatible API or a ComfyUI server to generate images with your own models."
          size="sm"
        >
          <template #actions>
            <Button variant="surface" size="sm" @click="openNew">Add first endpoint</Button>
          </template>
        </EmptyState>
      </template>
      <template #cell-name="{ row }">
        <span class="font-bold text-slate-900 dark:text-white">{{ row.name }}</span>
      </template>
      <template #cell-kind="{ row }">
        <Badge :variant="row.kind === 'comfyui' ? 'violet' : 'sky'" size="xs">{{ row.kind_label }}</Badge>
      </template>
      <template #cell-base_url="{ row }">
        <span class="font-mono break-all">{{ row.base_url }}</span>
      </template>
      <template #cell-has_api_key="{ row }">
        <span class="text-slate-500 dark:text-slate-400">{{ row.has_api_key ? 'Stored' : 'None' }}</span>
      </template>
      <template #cell-is_active="{ row }">
        <Switch
          :model-value="row.is_active"
          :aria-label="`${row.is_active ? 'Deactivate' : 'Activate'} ${row.name}`"
          @update:model-value="handleToggleActive(row, $event)"
        />
      </template>
      <template #cell-actions="{ row }">
        <div class="flex justify-end gap-1">
          <Button variant="ghost" size="xs" @click="openEdit(row)">Edit</Button>
          <Button variant="danger-ghost" size="xs" @click="handleDelete(row)">Delete</Button>
        </div>
      </template>
    </DataTable>

    <Modal
      :open="isEditorOpen"
      :title="form.id ? `Edit ${form.name}` : 'Add Endpoint'"
      size="md"
      @update:open="isEditorOpen = $event"
    >
      <form class="space-y-4" @submit.prevent="handleSave">
        <Input id="endpoint-name" v-model="form.name" label="Name" placeholder="e.g. LocalAI or GPU workstation" />
        <Select
          id="endpoint-kind"
          v-model="form.kind"
          label="Type"
          :options="KIND_OPTIONS"
          :disabled="isKindLocked"
          :hint="isKindLocked ? 'The type cannot change while models use this endpoint.' : undefined"
        />
        <Input
          id="endpoint-base-url"
          v-model="form.base_url"
          label="Base URL"
          :placeholder="kindHint.placeholder"
          :hint="kindHint.hint"
        />
        <Input
          id="endpoint-api-key"
          v-model="form.api_key"
          type="password"
          autocomplete="off"
          label="API Key (optional)"
          :placeholder="storedKey && !form.clear_api_key ? 'Stored – leave empty to keep' : 'Only needed if the server requires one'"
          :disabled="form.clear_api_key"
          hint="Sent as Bearer token and stored encrypted."
        />
        <Switch
          v-if="storedKey"
          v-model="form.clear_api_key"
          label="Remove stored API key"
          description="The endpoint is then called without authentication."
        />
        <Switch v-model="form.is_active" label="Active" description="Inactive endpoints cannot be used for generation." />

        <div class="space-y-2 rounded-xl border border-slate-200 p-3 text-xs dark:border-white/10">
          <div class="flex items-center justify-between gap-2">
            <span class="text-slate-600 dark:text-slate-300">Check the connection before saving.</span>
            <Button
              variant="secondary"
              size="xs"
              :loading="isTesting"
              :disabled="!form.base_url.trim()"
              data-testid="test-endpoint"
              @click="handleTest"
            >
              Test connection
            </Button>
          </div>
          <div
            v-if="testResult"
            role="status"
            :class="[
              'flex items-start gap-2',
              testResult.success ? 'text-emerald-700 dark:text-emerald-300' : 'text-rose-600 dark:text-rose-400',
            ]"
          >
            <component :is="testResult.success ? CheckCircle2 : XCircle" class="mt-0.5 size-4 shrink-0" aria-hidden="true" />
            <div class="min-w-0 space-y-1">
              <p>{{ testResult.message }}</p>
              <p v-if="testResult.models.length" class="break-words text-2xs text-slate-500 dark:text-slate-400">
                {{ testResult.models.slice(0, 8).join(', ') }}<span v-if="testResult.models.length > 8"> …</span>
              </p>
            </div>
          </div>
        </div>
      </form>

      <template #footer>
        <Button variant="secondary" size="sm" @click="isEditorOpen = false">Cancel</Button>
        <Button variant="primary" size="sm" :loading="isSaving" :disabled="!canSave" @click="handleSave">Save</Button>
      </template>
    </Modal>
  </div>
</template>
