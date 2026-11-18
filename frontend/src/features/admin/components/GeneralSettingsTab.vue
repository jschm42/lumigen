<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import Card from '@/components/ui/Card.vue'
import LoadingState from '@/components/ui/LoadingState.vue'
import Select from '@/components/ui/Select.vue'
import SettingsRow from '@/components/ui/SettingsRow.vue'
import Spinner from '@/components/ui/Spinner.vue'
import Switch from '@/components/ui/Switch.vue'
import type { UiSettings } from '@/types'

const authStore = useAuthStore()
const toastStore = useToastStore()

const CURRENCIES = ['USD', 'EUR', 'GBP', 'CHF', 'JPY', 'CNY', 'CAD', 'AUD', 'SEK', 'NOK', 'DKK', 'PLN', 'INR', 'BRL']

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
  </div>
</template>
