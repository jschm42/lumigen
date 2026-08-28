<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAdminStore } from '@/stores/admin'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import Card from '@/components/ui/Card.vue'

const adminStore = useAdminStore()

const inputKeys = ref<Record<string, string>>({})
const testingProvider = ref<string | null>(null)
const savingProvider = ref<string | null>(null)

onMounted(() => {
  adminStore.fetchProviderKeys()
})

async function handleSaveKey(provider: string) {
  const key = inputKeys.value[provider]?.trim()
  if (!key) return
  savingProvider.value = provider
  try {
    await adminStore.updateProviderKey(provider, key)
    inputKeys.value[provider] = ''
  } finally {
    savingProvider.value = null
  }
}

async function handleTestKey(provider: string) {
  testingProvider.value = provider
  try {
    await adminStore.testProvider(provider)
  } finally {
    testingProvider.value = null
  }
}
</script>

<template>
  <div class="space-y-4 text-xs">
    <div class="space-y-1">
      <h3 class="text-sm font-bold text-slate-900 dark:text-white">Provider API-Keys</h3>
      <p class="text-slate-500">
        Hinterlege deine API-Schlüssel für die Bildgenerierungs-Provider. Alle Schlüssel werden sicher verschlüsselt gespeichert.
      </p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card
        v-for="provider in adminStore.providerStatuses"
        :key="provider.provider"
        padding="md"
        class="space-y-3"
      >
        <div class="flex items-center justify-between">
          <div class="flex items-center gap-2">
            <h4 class="font-bold text-sm text-slate-900 dark:text-white">
              {{ provider.display_name }}
            </h4>
            <span
              :class="[
                'px-2 py-0.5 rounded-full text-[10px] font-semibold',
                provider.has_key
                  ? 'bg-emerald-100 text-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300'
                  : 'bg-slate-100 text-slate-500 dark:bg-slate-800 dark:text-slate-400',
              ]"
            >
              {{ provider.has_key ? 'Schlüssel konfiguriert' : 'Nicht konfiguriert' }}
            </span>
          </div>

          <Button
            v-if="provider.has_key"
            variant="secondary"
            size="xs"
            :loading="testingProvider === provider.provider"
            @click="handleTestKey(provider.provider)"
          >
            Verbindung testen
          </Button>
        </div>

        <!-- Input for new API Key -->
        <div class="flex gap-2">
          <Input
            type="password"
            :placeholder="provider.has_key ? '•••••••••••••••• (Neu setzen)' : 'API Key eingeben...'"
            v-model="inputKeys[provider.provider]"
            class="flex-1"
          />
          <Button
            variant="primary"
            size="sm"
            :disabled="!inputKeys[provider.provider]"
            :loading="savingProvider === provider.provider"
            @click="handleSaveKey(provider.provider)"
          >
            Speichern
          </Button>
        </div>
      </Card>
    </div>
  </div>
</template>
