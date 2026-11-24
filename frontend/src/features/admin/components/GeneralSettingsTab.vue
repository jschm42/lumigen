<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import Card from '@/components/ui/Card.vue'
import Input from '@/components/ui/Input.vue'
import LoadingState from '@/components/ui/LoadingState.vue'
import Select from '@/components/ui/Select.vue'
import SettingsRow from '@/components/ui/SettingsRow.vue'
import Spinner from '@/components/ui/Spinner.vue'
import Switch from '@/components/ui/Switch.vue'
import type { UiSettings } from '@/types'

const authStore = useAuthStore()
const toastStore = useToastStore()

const CURRENCIES = ['USD', 'EUR', 'GBP', 'CHF', 'JPY', 'CNY', 'CAD', 'AUD', 'SEK', 'NOK', 'DKK', 'PLN', 'INR', 'BRL']

type AnimationLimitKey =
  | 'animation_max_frames'
  | 'animation_max_dimension_px'
  | 'animation_max_file_size_mb'
  | 'animation_default_frame_ms'

/** Admin-configurable limits for agentic GIF animations; ranges mirror the backend hard caps. */
const ANIMATION_LIMITS: { key: AnimationLimitKey; label: string; description: string; min: number; max: number; unit: string }[] = [
  { key: 'animation_max_frames', label: 'Maximum frames', description: 'Upper bound for planned frames per animation (2–64).', min: 2, max: 64, unit: 'frames' },
  { key: 'animation_max_dimension_px', label: 'Maximum size', description: 'Longest side of the GIF; frames are downscaled before encoding (128–1024).', min: 128, max: 1024, unit: 'px' },
  { key: 'animation_max_file_size_mb', label: 'Maximum file size', description: 'Larger GIFs are reduced in colours and size; if that is not enough, assembly fails and the frames stay in the gallery (1–50).', min: 1, max: 50, unit: 'MB' },
  { key: 'animation_default_frame_ms', label: 'Default frame duration', description: 'Used when neither the plan nor the user sets a duration (20–1000).', min: 20, max: 1000, unit: 'ms' },
]

const settings = ref<UiSettings | null>(null)
const savingKey = ref<keyof UiSettings | null>(null)

onMounted(async () => {
  try {
    settings.value = await adminApi.getUiSettings()
  } catch (_error) {
    toastStore.error('Settings could not be loaded.')
  }
})

async function update<K extends keyof UiSettings>(key: K, value: UiSettings[K]) {
  if (!settings.value) return
  const previous = settings.value[key]
  settings.value = { ...settings.value, [key]: value }
  savingKey.value = key
  try {
    const saved = await adminApi.updateUiSettings({ [key]: value } as Partial<UiSettings>)
    settings.value = saved
    authStore.setUiSettings(saved)
    toastStore.success('Setting saved.')
  } catch (error: any) {
    settings.value = { ...settings.value, [key]: previous }
    toastStore.error(error?.response?.data?.detail || 'Setting could not be saved.')
  } finally {
    savingKey.value = null
  }
}

function updateLimit(key: AnimationLimitKey, event: Event, min: number, max: number) {
  const value = Number.parseInt((event.target as HTMLInputElement).value, 10)
  if (!Number.isFinite(value) || value < min || value > max) {
    toastStore.error(`Enter a whole number between ${min} and ${max}.`)
    return
  }
  if (settings.value && settings.value[key] !== value) update(key, value)
}
</script>

<template>
  <div class="space-y-5 text-xs">
    <div class="space-y-0.5">
      <h3 class="text-sm font-bold text-slate-900 dark:text-white">General</h3>
      <p class="text-slate-500">Studio-wide preferences that apply to all users.</p>
    </div>

    <LoadingState v-if="!settings" label="Loading settings…" />

    <Card v-else padding="none" class="divide-y divide-slate-200/60 dark:divide-white/10">
      <SettingsRow label="Show token usage">
        <template #description>
          Display consumed tokens on every generation and as a session total (reported by OpenRouter,
          OpenAI GPT-Image, Google Gemini, xAI and Seedream). If prices are configured for a model under
          <strong>Models</strong>, the cost is shown as well; otherwise only tokens are displayed.
        </template>
        <Spinner v-if="savingKey === 'show_token_usage'" size="sm" class="text-sky-500" />
        <Switch
          :model-value="settings.show_token_usage"
          :disabled="savingKey !== null"
          aria-label="Show token usage"
          data-testid="setting-show-token-usage"
          @update:model-value="update('show_token_usage', $event)"
        />
      </SettingsRow>

      <SettingsRow
        label="Cost currency"
        description="Currency of all model prices (per 1M tokens / per image) and of the displayed costs. Changing it does not convert existing prices."
      >
        <Spinner v-if="savingKey === 'cost_currency'" size="sm" class="text-sky-500" />
        <Select
          :model-value="settings.cost_currency"
          :disabled="savingKey !== null"
          size="sm"
          class="w-28"
          aria-label="Cost currency"
          data-testid="setting-cost-currency"
          @update:model-value="update('cost_currency', String($event))"
        >
          <option v-for="code in CURRENCIES" :key="code" :value="code">{{ code }}</option>
          <option v-if="!CURRENCIES.includes(settings.cost_currency)" :value="settings.cost_currency">
            {{ settings.cost_currency }}
          </option>
        </Select>
      </SettingsRow>
    </Card>

    <div v-if="settings" class="space-y-0.5">
      <h3 class="text-sm font-bold text-slate-900 dark:text-white">GIF animations</h3>
      <p class="text-slate-500 dark:text-slate-400">Limits for Agentic Mode animations. They protect disk space and the provider budget.</p>
    </div>

    <Card v-if="settings" padding="none" class="divide-y divide-slate-200/60 dark:divide-white/10">
      <SettingsRow v-for="limit in ANIMATION_LIMITS" :key="limit.key" :label="limit.label" :description="limit.description">
        <Spinner v-if="savingKey === limit.key" size="sm" class="text-sky-500" />
        <Input
          :model-value="settings[limit.key]"
          type="number"
          size="sm"
          class="w-24"
          :min="limit.min"
          :max="limit.max"
          :disabled="savingKey !== null"
          :aria-label="`${limit.label} (${limit.unit})`"
          :data-testid="`setting-${limit.key}`"
          @change="updateLimit(limit.key, $event, limit.min, limit.max)"
        />
        <span class="w-10 text-2xs text-slate-500 dark:text-slate-400">{{ limit.unit }}</span>
      </SettingsRow>
    </Card>
  </div>
</template>
