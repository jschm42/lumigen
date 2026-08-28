<script setup lang="ts">
import { onMounted } from 'vue'
import { useAdminStore } from '@/stores/admin'
import Card from '@/components/ui/Card.vue'

const adminStore = useAdminStore()

onMounted(() => {
  adminStore.fetchSystemInfo()
})

function formatBytes(bytes?: number): string {
  if (!bytes) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
}
</script>

<template>
  <div class="space-y-6 text-xs">
    <div class="space-y-0.5">
      <h3 class="text-sm font-bold text-slate-900 dark:text-white">System & Diagnose</h3>
      <p class="text-slate-500">Übersicht über Speicherplatz, Dateisystem und Versionsinformationen.</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Card padding="md" class="space-y-1">
        <span class="text-[11px] text-slate-500 font-semibold uppercase">Version</span>
        <div class="text-lg font-bold text-slate-900 dark:text-white">
          {{ adminStore.systemInfo?.app_version || '0.1.0' }}
        </div>
      </Card>

      <Card padding="md" class="space-y-1">
        <span class="text-[11px] text-slate-500 font-semibold uppercase">Generierte Assets</span>
        <div class="text-lg font-bold text-slate-900 dark:text-white">
          {{ adminStore.systemInfo?.total_assets || 0 }}
        </div>
      </Card>

      <Card padding="md" class="space-y-1">
        <span class="text-[11px] text-slate-500 font-semibold uppercase">Speicherplatz belegt</span>
        <div class="text-lg font-bold text-slate-900 dark:text-white">
          {{ formatBytes(adminStore.systemInfo?.storage_used_bytes) }}
        </div>
      </Card>
    </div>

    <Card padding="md" class="space-y-3">
      <h4 class="font-bold text-slate-900 dark:text-white">Umgebungsdetails</h4>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[11px]">
        <div>
          <span class="text-slate-500 block">Speicherort:</span>
          <span class="font-mono text-slate-700 dark:text-slate-300">{{ adminStore.systemInfo?.storage_dir || './data' }}</span>
        </div>
        <div>
          <span class="text-slate-500 block">Python Version:</span>
          <span class="font-mono text-slate-700 dark:text-slate-300">{{ adminStore.systemInfo?.python_version || '3.12+' }}</span>
        </div>
      </div>
    </Card>
  </div>
</template>
