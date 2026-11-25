<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, useId, watch } from 'vue'
import { AlertCircle, Check, ChevronDown, Film, Plus, RefreshCw, Search } from 'lucide-vue-next'
import { adminApi } from '@/api/admin'
import { useToastStore } from '@/stores/toast'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import FormField from '@/components/ui/FormField.vue'
import Input from '@/components/ui/Input.vue'
import Select, { type SelectOption } from '@/components/ui/Select.vue'
import { controlBaseClasses, controlSizeClasses, controlStateClasses } from '@/components/ui/controlStyles'

export interface DiscoveredModelItem {
  id: string
  label?: string
  mediaType?: string
}

interface Props {
  mode?: 'combobox' | 'catalog'
  provider: string
  providers?: SelectOption[]
  endpointId?: number | null
  purpose?: 'image' | 'reasoning' | 'upscale'
  reasoningModelId?: number
  modelValue?: string
  label?: string
  placeholder?: string
  required?: boolean
  id?: string
  configuredIds?: string[]
  autoDiscover?: boolean
  canAutoDiscover?: boolean
  title?: string
  description?: string
  buttonLabel?: string
}

const props = withDefaults(defineProps<Props>(), {
  mode: 'combobox',
  endpointId: null,
  purpose: 'image',
  label: 'Model Identifier',
  required: false,
  configuredIds: () => [],
  autoDiscover: false,
  canAutoDiscover: true,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'select', item: DiscoveredModelItem): void
  (e: 'update:provider', value: string): void
  (e: 'loaded', items: DiscoveredModelItem[]): void
}>()

const toastStore = useToastStore()

const isLoading = ref(false)
const hasLoaded = ref(false)
const errorMessage = ref('')
const searchQuery = ref('')
const items = ref<DiscoveredModelItem[]>([])

// Combobox state
const comboboxRootRef = ref<HTMLElement | null>(null)
const isDropdownOpen = ref(false)
const isFiltering = ref(false)
const activeIndex = ref(-1)
const listboxId = `model-combobox-list-${useId()}`

const configuredSet = computed(() => new Set(props.configuredIds))

const filteredItems = computed(() => {
  const rawQuery = props.mode === 'combobox'
    ? (isFiltering.value ? (props.modelValue || '') : '')
    : searchQuery.value
  const q = rawQuery.trim().toLowerCase()
  if (!q) return items.value
  return items.value.filter(
    (item) =>
      item.id.toLowerCase().includes(q) ||
      (item.label && item.label.toLowerCase().includes(q)),
  )
})

const resolvedButtonLabel = computed(() => {
  if (props.buttonLabel) return props.buttonLabel
  if (props.endpointId) {
    return props.provider === 'comfyui' ? 'Load checkpoints' : 'Load models'
  }
  return hasLoaded.value ? 'Refresh' : 'Discover'
})

async function discover(silent = false) {
  if (!props.provider && props.purpose !== 'upscale') return
  isLoading.value = true
  errorMessage.value = ''
  try {
    let loaded: DiscoveredModelItem[] = []
    if (props.purpose === 'upscale') {
      const res = await adminApi.discoverUpscaleModels()
      loaded = (res.models || []).map((m) => ({
        id: m.endpoint_id,
        label: m.name,
      }))
    } else if (props.endpointId) {
      const models = await adminApi.listEndpointModels(props.endpointId)
      loaded = models.map((id) => ({ id }))
    } else {
      const res = await adminApi.discoverModels(props.provider, {
        purpose: props.purpose === 'reasoning' ? 'reasoning' : 'image',
        reasoningModelId: props.reasoningModelId,
      })
      loaded = (res.models || []).map((id) => ({
        id,
        mediaType: res.media_types?.[id],
      }))
    }

    items.value = loaded
    hasLoaded.value = true
    emit('loaded', loaded)

    if (!silent) {
      if (loaded.length === 0) {
        toastStore.info('No models were returned by the provider.')
      } else if (props.mode === 'combobox') {
        isFiltering.value = false
        isDropdownOpen.value = true
        activeIndex.value = 0
      } else {
        const videoCount = loaded.filter((m) => m.mediaType === 'video').length
        toastStore.success(
          videoCount > 0
            ? `Found ${loaded.length} models (${videoCount} video).`
            : `Found ${loaded.length} available models.`,
        )
      }
    }
  } catch (error: any) {
    items.value = []
    hasLoaded.value = true
    const detail = error?.response?.data?.detail || 'Could not load available models.'
    errorMessage.value = detail
    if (!silent) toastStore.error(detail)
  } finally {
    isLoading.value = false
  }
}

function selectComboboxItem(item: DiscoveredModelItem) {
  emit('update:modelValue', item.id)
  emit('select', item)
  isFiltering.value = false
  isDropdownOpen.value = false
  activeIndex.value = -1
}

function handleComboboxInput(event: Event) {
  const val = (event.target as HTMLInputElement).value
  emit('update:modelValue', val)
  isFiltering.value = true
  if (items.value.length > 0) {
    isDropdownOpen.value = true
    activeIndex.value = 0
  }
}

function handleComboboxFocus() {
  if (items.value.length > 0) {
    isFiltering.value = false
    isDropdownOpen.value = true
  }
}

function toggleDropdown() {
  if (isDropdownOpen.value) {
    isDropdownOpen.value = false
    return
  }
  if (items.value.length > 0) {
    isFiltering.value = false
    isDropdownOpen.value = true
    activeIndex.value = Math.max(
      0,
      filteredItems.value.findIndex((i) => i.id === props.modelValue),
    )
  } else {
    void discover(false)
  }
}

function handleComboboxKeydown(event: KeyboardEvent) {
  if (!isDropdownOpen.value) {
    if (event.key === 'ArrowDown' && items.value.length > 0) {
      event.preventDefault()
      isFiltering.value = false
      isDropdownOpen.value = true
      activeIndex.value = 0
    }
    return
  }

  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    isDropdownOpen.value = false
    return
  }

  if (event.key === 'ArrowDown') {
    event.preventDefault()
    if (filteredItems.value.length > 0) {
      activeIndex.value = (activeIndex.value + 1) % filteredItems.value.length
    }
    return
  }

  if (event.key === 'ArrowUp') {
    event.preventDefault()
    if (filteredItems.value.length > 0) {
      activeIndex.value =
        (activeIndex.value - 1 + filteredItems.value.length) % filteredItems.value.length
    }
    return
  }

  if (event.key === 'Enter' && activeIndex.value >= 0 && activeIndex.value < filteredItems.value.length) {
    event.preventDefault()
    selectComboboxItem(filteredItems.value[activeIndex.value])
  }
}

function handleDocumentPointerDown(event: PointerEvent) {
  if (!isDropdownOpen.value || !comboboxRootRef.value) return
  if (!comboboxRootRef.value.contains(event.target as Node)) {
    isDropdownOpen.value = false
  }
}

function handleProviderChange(value: string | number) {
  items.value = []
  hasLoaded.value = false
  errorMessage.value = ''
  searchQuery.value = ''
  emit('update:provider', String(value))
}

function maybeAutoDiscover() {
  if (props.autoDiscover && props.canAutoDiscover) {
    void discover(true)
  }
}

watch(
  () => [props.provider, props.endpointId, props.purpose],
  () => {
    items.value = []
    hasLoaded.value = false
    errorMessage.value = ''
    searchQuery.value = ''
    isDropdownOpen.value = false
    isFiltering.value = false
    maybeAutoDiscover()
  },
)

onMounted(() => {
  document.addEventListener('pointerdown', handleDocumentPointerDown)
  maybeAutoDiscover()
})

onBeforeUnmount(() => {
  document.removeEventListener('pointerdown', handleDocumentPointerDown)
})

defineExpose({ discover })
</script>

<template>
  <!-- Single Filterable Combobox Mode -->
  <div v-if="mode === 'combobox'" ref="comboboxRootRef" class="space-y-1.5">
    <FormField :id="id" :label="label" :error="errorMessage || undefined">
      <template #default="{ id: fieldId, describedBy, invalid }">
        <div class="flex items-center gap-2">
          <div class="relative flex-1 min-w-0">
            <input
              :id="fieldId"
              type="text"
              role="combobox"
              autocomplete="off"
              :value="modelValue ?? ''"
              :placeholder="placeholder"
              :required="required"
              :aria-expanded="isDropdownOpen"
              :aria-controls="listboxId"
              aria-autocomplete="list"
              :aria-invalid="invalid || undefined"
              :aria-describedby="describedBy"
              :class="[
                controlBaseClasses,
                controlSizeClasses.md,
                controlStateClasses(invalid),
                'pr-9 font-mono',
              ]"
              @input="handleComboboxInput"
              @focus="handleComboboxFocus"
              @keydown="handleComboboxKeydown"
            />
            <button
              type="button"
              aria-label="Toggle available models list"
              :aria-expanded="isDropdownOpen"
              class="absolute right-2 top-1/2 -translate-y-1/2 rounded-lg p-1 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40"
              @click="toggleDropdown"
            >
              <ChevronDown
                class="size-4 transition-transform duration-150"
                :class="isDropdownOpen ? 'rotate-180' : ''"
                aria-hidden="true"
              />
            </button>

            <!-- Filtered Dropdown Listbox -->
            <div
              v-if="isDropdownOpen"
              :id="listboxId"
              role="listbox"
              :aria-label="endpointId ? 'Available endpoint models' : 'Available models'"
              class="absolute left-0 right-0 top-full z-50 mt-1 max-h-56 overflow-y-auto rounded-xl border border-slate-200 bg-white p-1 shadow-xl dark:border-white/10 dark:bg-slate-900"
            >
              <button
                v-for="(item, idx) in filteredItems"
                :key="item.id"
                type="button"
                role="option"
                :aria-selected="item.id === modelValue"
                :class="[
                  'flex w-full items-center justify-between gap-2 rounded-lg px-2.5 py-1.5 text-left text-xs transition-colors',
                  idx === activeIndex
                    ? 'bg-sky-50 text-sky-700 dark:bg-sky-950/60 dark:text-sky-300'
                    : 'text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-slate-800',
                ]"
                @mousedown.prevent="selectComboboxItem(item)"
              >
                <span class="min-w-0 flex-1 truncate font-mono">
                  {{ item.label && item.label !== item.id ? `${item.label} (${item.id})` : item.id }}
                </span>
                <span class="flex shrink-0 items-center gap-1.5">
                  <Badge v-if="item.mediaType === 'video'" variant="violet" size="xs">
                    <Film class="mr-0.5 size-3" aria-hidden="true" />
                    Video
                  </Badge>
                  <Check
                    v-if="item.id === modelValue"
                    class="size-3.5 text-sky-500"
                    aria-hidden="true"
                  />
                </span>
              </button>

              <p
                v-if="filteredItems.length === 0"
                class="px-2.5 py-2 text-2xs text-slate-500 dark:text-slate-400"
              >
                {{ items.length > 0 ? 'No matching models — keep typing to use a custom identifier.' : 'No models discovered yet.' }}
              </p>
            </div>
          </div>

          <Button
            variant="secondary"
            size="md"
            :loading="isLoading"
            :data-testid="endpointId ? 'load-endpoint-models' : 'discover-provider-models'"
            @click="discover(false)"
          >
            <template #icon>
              <RefreshCw class="size-3.5" aria-hidden="true" />
            </template>
            {{ resolvedButtonLabel }}
          </Button>
        </div>
      </template>
    </FormField>

    <p v-if="!errorMessage && hasLoaded && items.length === 0" class="text-2xs text-slate-500 dark:text-slate-400">
      No models reported for this provider. You can still enter a model identifier manually.
    </p>
  </div>

  <!-- Standalone Catalog Panel Mode -->
  <Card v-else padding="sm" class="space-y-3">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div class="space-y-0.5">
        <h4 class="text-xs font-bold text-slate-900 dark:text-white">
          {{ title || 'Discover Available Models' }}
        </h4>
        <p v-if="description" class="text-2xs text-slate-500 dark:text-slate-400">
          {{ description }}
        </p>
      </div>
      <Badge v-if="items.length > 0" variant="slate" size="xs">
        {{ filteredItems.length }}<template v-if="searchQuery"> / {{ items.length }}</template> models
      </Badge>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <Select
        v-if="providers && providers.length > 0"
        :model-value="provider"
        :options="providers"
        size="sm"
        class="w-52"
        aria-label="Provider to discover models from"
        @update:model-value="handleProviderChange"
      />

      <Button
        variant="secondary"
        size="sm"
        :loading="isLoading"
        @click="discover(false)"
      >
        <template #icon>
          <RefreshCw class="size-3.5" aria-hidden="true" />
        </template>
        {{ resolvedButtonLabel }}
      </Button>

      <Input
        v-if="items.length > 5"
        v-model="searchQuery"
        size="sm"
        class="min-w-44 flex-1"
        placeholder="Search models…"
        aria-label="Search discovered models"
      >
        <template #prefix>
          <Search class="size-3.5 text-slate-400" aria-hidden="true" />
        </template>
      </Input>
    </div>

    <p v-if="errorMessage" role="alert" class="flex items-center gap-1.5 text-xs text-rose-600 dark:text-rose-400">
      <AlertCircle class="size-4 shrink-0" aria-hidden="true" />
      <span>{{ errorMessage }}</span>
    </p>

    <div
      v-if="filteredItems.length > 0"
      class="grid max-h-56 grid-cols-1 gap-1.5 overflow-y-auto rounded-xl bg-slate-100/80 p-2 dark:bg-slate-800/60 md:grid-cols-2"
    >
      <button
        v-for="item in filteredItems"
        :key="item.id"
        type="button"
        class="group flex items-center justify-between gap-2 rounded-lg border border-slate-200/70 bg-white/80 px-2.5 py-2 text-left transition-colors hover:border-sky-500/50 hover:bg-sky-50/50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 dark:border-white/5 dark:bg-slate-900/60 dark:hover:border-sky-400/40 dark:hover:bg-sky-950/30"
        @click="emit('select', item)"
      >
        <div class="min-w-0 flex-1 space-y-0.5">
          <div class="flex items-center gap-1.5">
            <span class="truncate font-medium text-slate-800 group-hover:text-sky-600 dark:text-slate-200 dark:group-hover:text-sky-400">
              {{ item.label || item.id }}
            </span>
            <Badge v-if="item.mediaType === 'video'" variant="violet" size="xs">
              <Film class="mr-0.5 size-3" aria-hidden="true" />
              Video
            </Badge>
            <Badge v-if="configuredSet.has(item.id)" variant="emerald" size="xs">
              <Check class="mr-0.5 size-3" aria-hidden="true" />
              Configured
            </Badge>
          </div>
          <div v-if="item.label && item.label !== item.id" class="truncate font-mono text-2xs text-slate-500 dark:text-slate-400">
            {{ item.id }}
          </div>
        </div>

        <span class="inline-flex shrink-0 items-center gap-0.5 text-2xs font-semibold text-sky-600 dark:text-sky-400">
          <Plus class="size-3.5" aria-hidden="true" />
          Add
        </span>
      </button>
    </div>

    <p v-else-if="hasLoaded && !errorMessage" class="text-2xs text-slate-500 dark:text-slate-400">
      {{ searchQuery ? 'No discovered models match your search.' : 'No models returned by this provider.' }}
    </p>
  </Card>
</template>
