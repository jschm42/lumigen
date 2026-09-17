<script setup lang="ts">
import { onMounted } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { useAuthStore } from '@/stores/auth'
import { useCreditsStore } from '@/stores/credits'
import Card from '@/components/ui/Card.vue'
import Button from '@/components/ui/Button.vue'

const adminStore = useAdminStore()
const authStore = useAuthStore()
const creditsStore = useCreditsStore()

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
      <h3 class="text-sm font-bold text-slate-900 dark:text-white">System & Diagnostics</h3>
      <p class="text-slate-500">Overview of disk usage, file system, and version information.</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
      <Card padding="md" class="space-y-1">
        <span class="text-[11px] text-slate-500 font-semibold uppercase">Version</span>
        <div class="text-lg font-bold text-slate-900 dark:text-white">
          {{ adminStore.systemInfo?.app_version || authStore.appVersion }}
        </div>
      </Card>

      <Card padding="md" class="space-y-1">
        <span class="text-[11px] text-slate-500 font-semibold uppercase">Generated Assets</span>
        <div class="text-lg font-bold text-slate-900 dark:text-white">
          {{ adminStore.systemInfo?.total_assets || 0 }}
        </div>
      </Card>

      <Card padding="md" class="space-y-1">
        <span class="text-[11px] text-slate-500 font-semibold uppercase">Storage Used</span>
        <div class="text-lg font-bold text-slate-900 dark:text-white">
          {{ formatBytes(adminStore.systemInfo?.storage_used_bytes) }}
        </div>
      </Card>
    </div>

    <Card padding="md" class="space-y-3">
      <h4 class="font-bold text-slate-900 dark:text-white">Environment Details</h4>
      <div class="grid grid-cols-1 sm:grid-cols-2 gap-3 text-[11px]">
        <div>
          <span class="text-slate-500 block">Storage Directory:</span>
          <span class="font-mono text-slate-700 dark:text-slate-300">{{ adminStore.systemInfo?.storage_dir || './data' }}</span>
        </div>
        <div>
          <span class="text-slate-500 block">Python Version:</span>
          <span class="font-mono text-slate-700 dark:text-slate-300">{{ adminStore.systemInfo?.python_version || '3.12+' }}</span>
        </div>
      </div>
    </Card>

    <!-- Credits & Licenses Card -->
    <Card padding="md" class="flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-gradient-to-r from-slate-50 to-sky-50/50 dark:from-slate-900/50 dark:to-sky-950/20 border border-slate-200/90 dark:border-white/10">
      <div class="space-y-1">
        <div class="flex items-center gap-2">
          <span class="text-base">📜</span>
          <h4 class="font-bold text-slate-900 dark:text-white">Credits, Attributions & Licenses</h4>
        </div>
        <p class="text-[11px] text-slate-500 dark:text-slate-400 max-w-xl leading-relaxed">
          Overview of integrated AI providers (Black Forest Labs, OpenAI, Google Imagen, fal.ai, MiniMax, etc.), attribution requirements, open-source licenses, and typography.
        </p>
      </div>
      <Button variant="secondary" size="sm" class="shrink-0 cursor-pointer" @click="creditsStore.open">
        View Credits & Licenses
      </Button>
    </Card>
  </div>
</template>
