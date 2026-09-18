<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { generationApi } from '@/api/generation'
import { useToastStore } from '@/stores/toast'
import Modal from '@/components/ui/Modal.vue'
import Button from '@/components/ui/Button.vue'
import type { Asset } from '@/types'

interface Props {
  open: boolean
  asset: Asset | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'submitted', jobId: number): void
}>()

const toastStore = useToastStore()

interface UpscaleModelOption {
  value: string
  label: string
  id?: number
  name?: string
  model_identifier?: string
  is_default?: boolean
}

const mode = ref<'standard' | 'custom'>('standard')
const selectedModelId = ref<number | null>(null)
const availableModels = ref<UpscaleModelOption[]>([])
const isLoadingModels = ref(false)
const isSubmitting = ref(false)

const enabledDbModels = computed(() => {
  return availableModels.value.filter((m) => m.id != null)
})

const defaultModel = computed(() => {
  return enabledDbModels.value.find((m) => m.is_default) || enabledDbModels.value[0] || null
})

async function fetchModels() {
  isLoadingModels.value = true
  try {
    const data = await generationApi.getUpscaleModels()
    availableModels.value = data || []
    if (defaultModel.value && selectedModelId.value == null) {
      selectedModelId.value = defaultModel.value.id || null
    }
  } catch (_e) {
    // Handled gracefully
  } finally {
    isLoadingModels.value = false
  }
}

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      mode.value = 'standard'
      if (availableModels.value.length === 0) {
        fetchModels()
      } else if (defaultModel.value && selectedModelId.value == null) {
        selectedModelId.value = defaultModel.value.id || null
      }
    }
  }
)

onMounted(() => {
  if (props.open) {
    fetchModels()
  }
})

async function handleSubmit() {
  if (!props.asset) return

  isSubmitting.value = true
  try {
    const payload: { topaz_model_id?: number } = {}
    if (mode.value === 'custom' && selectedModelId.value != null) {
      payload.topaz_model_id = selectedModelId.value
    }

    const res = await generationApi.upscale(props.asset.id, payload)
    toastStore.success('Upscaling started!')
    emit('submitted', res.job_id)
    emit('update:open', false)
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Upscaling failed.')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <Modal
    :open="open"
    title="Upscale Image"
    size="md"
    @update:open="emit('update:open', $event)"
  >
    <div v-if="asset" class="space-y-4 text-xs">
      <!-- Preview Image & Meta -->
      <div class="relative flex flex-col items-center justify-center bg-slate-950 rounded-2xl p-3 border border-slate-200 dark:border-white/10 overflow-hidden">
        <img
          :src="asset.thumbnail_url || asset.image_url"
          :alt="asset.prompt || 'Asset preview'"
          class="max-h-48 w-auto object-contain rounded-xl shadow-lg"
        />
        <div class="mt-2 flex items-center gap-2">
          <span v-if="asset.width && asset.height" class="px-2 py-0.5 rounded-md bg-black/60 text-slate-300 text-[10px] font-mono border border-white/10">
            Original: {{ asset.width }} × {{ asset.height }}
          </span>
          <span v-if="asset.aspect_ratio" class="px-2 py-0.5 rounded-md bg-black/60 text-slate-300 text-[10px] font-mono border border-white/10">
            {{ asset.aspect_ratio }}
          </span>
        </div>
      </div>

      <!-- Mode Selection (Standard vs. Choose Model) -->
      <div class="space-y-2.5">
        <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500 dark:text-slate-400">
          Upscaling Model
        </label>

        <!-- Standard (Default) Option Card -->
        <label
          :class="[
            'flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all',
            mode === 'standard'
              ? 'border-sky-500 bg-sky-50/70 dark:bg-sky-950/40 dark:border-sky-500/70 shadow-sm'
              : 'border-slate-200 hover:border-slate-300 dark:border-white/10 dark:hover:border-white/20 bg-slate-50/50 dark:bg-slate-900/50',
          ]"
        >
          <input
            type="radio"
            name="upscale-mode"
            value="standard"
            v-model="mode"
            class="mt-0.5 text-sky-500 focus:ring-sky-400"
          />
          <div class="space-y-0.5 flex-1 min-w-0">
            <div class="flex items-center justify-between">
              <span class="font-semibold text-slate-900 dark:text-white">
                Standard (Default Model)
              </span>
              <span v-if="defaultModel" class="text-[10px] font-medium px-1.5 py-0.5 rounded bg-sky-100 text-sky-800 dark:bg-sky-900/60 dark:text-sky-300">
                Default
              </span>
            </div>
            <p class="text-[11px] text-slate-500 dark:text-slate-400">
              <template v-if="defaultModel">
                Uses configured default: <strong class="text-slate-700 dark:text-slate-200">{{ defaultModel.name }}</strong>
              </template>
              <template v-else>
                Uses configured system default upscale model.
              </template>
            </p>
          </div>
        </label>

        <!-- Custom Model Selection Option Card -->
        <label
          :class="[
            'flex items-start gap-3 p-3 rounded-xl border cursor-pointer transition-all',
            mode === 'custom'
              ? 'border-sky-500 bg-sky-50/70 dark:bg-sky-950/40 dark:border-sky-500/70 shadow-sm'
              : 'border-slate-200 hover:border-slate-300 dark:border-white/10 dark:hover:border-white/20 bg-slate-50/50 dark:bg-slate-900/50',
          ]"
        >
          <input
            type="radio"
            name="upscale-mode"
            value="custom"
            v-model="mode"
            class="mt-0.5 text-sky-500 focus:ring-sky-400"
          />
          <div class="space-y-2 flex-1 min-w-0">
            <div class="flex items-center justify-between">
              <span class="font-semibold text-slate-900 dark:text-white">
                Choose Model
              </span>
              <span class="text-[10px] text-slate-400">
                Custom Selection
              </span>
            </div>
            <p class="text-[11px] text-slate-500 dark:text-slate-400">
              Select an explicit upscale model for this operation.
            </p>

            <!-- Dropdown shown when Custom is active -->
            <div v-if="mode === 'custom'" class="pt-1">
              <select
                v-model="selectedModelId"
                class="w-full rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-800 focus:border-sky-500 focus:outline-none focus:ring-1 focus:ring-sky-400 dark:border-white/15 dark:bg-slate-950 dark:text-slate-200"
              >
                <option
                  v-for="m in enabledDbModels"
                  :key="m.id"
                  :value="m.id"
                >
                  {{ m.name }} {{ m.is_default ? '(Default)' : '' }}
                </option>
              </select>
            </div>
          </div>
        </label>
      </div>
    </div>

    <template #footer>
      <Button variant="secondary" size="sm" @click="emit('update:open', false)">
        Cancel
      </Button>
      <Button
        variant="primary"
        size="sm"
        :loading="isSubmitting"
        @click="handleSubmit"
      >
        <template #icon>
          <span>✨</span>
        </template>
        <span>Start Upscaling</span>
      </Button>
    </template>
  </Modal>
</template>
