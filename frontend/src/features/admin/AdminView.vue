<script setup lang="ts">
import { ref } from 'vue'
import Tabs, { type TabItem } from '@/components/ui/Tabs.vue'
import ApiKeysTab from './components/ApiKeysTab.vue'
import ModelConfigsTab from './components/ModelConfigsTab.vue'
import StylesTab from './components/StylesTab.vue'
import UsersTab from './components/UsersTab.vue'
import DataTransferTab from './components/DataTransferTab.vue'
import SystemInfoTab from './components/SystemInfoTab.vue'

const activeTab = ref('apikeys')

const tabs: TabItem[] = [
  { id: 'apikeys', label: 'API Keys' },
  { id: 'models', label: 'Modelle' },
  { id: 'styles', label: 'Styles' },
  { id: 'users', label: 'Benutzer' },
  { id: 'transfer', label: 'Transfer & Backup' },
  { id: 'system', label: 'System Info' },
]
</script>

<template>
  <div class="space-y-6 pb-20">
    <!-- Header with Tabs -->
    <div class="space-y-4">
      <div class="space-y-0.5">
        <h2 class="text-base font-bold text-slate-900 dark:text-white">Studio Administration</h2>
        <p class="text-xs text-slate-500">Konfiguration für Provider, Modelle, Styles und Zugriffsrechte.</p>
      </div>

      <Tabs :tabs="tabs" v-model="activeTab" variant="pills" />
    </div>

    <!-- Active Tab Component -->
    <div>
      <ApiKeysTab v-if="activeTab === 'apikeys'" />
      <ModelConfigsTab v-else-if="activeTab === 'models'" />
      <StylesTab v-else-if="activeTab === 'styles'" />
      <UsersTab v-else-if="activeTab === 'users'" />
      <DataTransferTab v-else-if="activeTab === 'transfer'" />
      <SystemInfoTab v-else-if="activeTab === 'system'" />
    </div>
  </div>
</template>
