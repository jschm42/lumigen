<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { adminApi } from '@/api/admin'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import Switch from '@/components/ui/Switch.vue'
import Spinner from '@/components/ui/Spinner.vue'
import type { UiSettings } from '@/types'

const authStore = useAuthStore()
const toastStore = useToastStore()

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

    <div v-if="!settings" class="flex justify-center py-10">
      <Spinner size="lg" class="text-sky-500" />
    </div>

    <div
      v-else
      class="divide-y divide-slate-200/60 rounded-2xl border border-slate-200/80 bg-white/70 shadow-sm backdrop-blur-xl dark:divide-white/10 dark:border-white/10 dark:bg-slate-900/70"
    >
      <div class="flex items-start justify-between gap-6 p-4">
        <div class="space-y-1">
          <div class="text-sm font-semibold text-slate-800 dark:text-slate-100">Show token usage</div>
          <p class="max-w-xl text-slate-500">
            Display consumed tokens and provider cost on every generation and as a session total.
            Available for providers that report usage (OpenRouter, OpenAI GPT-Image, Google Gemini; BFL reports credits).
          </p>
        </div>
        <div class="flex items-center gap-2 pt-0.5">
          <Spinner v-if="savingKey === 'show_token_usage'" size="sm" class="text-sky-500" />
          <Switch
            :modelValue="settings.show_token_usage"
            :disabled="savingKey !== null"
            @update:modelValue="update('show_token_usage', $event)"
            data-testid="setting-show-token-usage"
          />
        </div>
      </div>
    </div>
  </div>
</template>
