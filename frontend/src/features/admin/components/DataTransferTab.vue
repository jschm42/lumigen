<script setup lang="ts">
import { ref } from 'vue'
import { adminApi } from '@/api/admin'
import { useToastStore } from '@/stores/toast'
import { downloadFile } from '@/utils/download'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'

const toastStore = useToastStore()
const importFileInput = ref<HTMLInputElement | null>(null)
const isImporting = ref(false)

async function handleFileSelect(e: Event) {
  const target = e.target as HTMLInputElement
  if (!target.files || !target.files[0]) return

  const file = target.files[0]
  const formData = new FormData()
  formData.append('file', file)

  isImporting.value = true
  try {
    await adminApi.importData(formData)
    toastStore.success('Import completed successfully!')
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Import failed.')
  } finally {
    isImporting.value = false
    target.value = ''
  }
}
</script>

<template>
  <div class="space-y-6 text-xs">
    <div class="space-y-0.5">
      <h3 class="text-sm font-bold text-slate-900 dark:text-white">Data Transfer & Backup</h3>
      <p class="text-slate-500">Export or import configurations, models, profiles, and styles.</p>
    </div>

    <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
      <!-- Export Card -->
      <Card padding="md" class="space-y-4">
        <h4 class="font-bold text-sm text-slate-900 dark:text-white">Export Data</h4>
        <p class="text-slate-500 leading-relaxed">
          Create a full JSON backup of all profiles, models, and styles.
        </p>

        <div class="flex flex-wrap gap-2">
          <button
            type="button"
            @click="downloadFile('/api/admin/export/all', 'lumigen_backup.json')"
            class="px-4 py-2 rounded-xl bg-sky-500 text-white hover:bg-sky-600 font-semibold shadow-sm inline-flex items-center gap-2 transition-colors"
          >
            <span>📦</span> Full Export
          </button>

          <button
            type="button"
            @click="downloadFile('/api/admin/export/styles-zip', 'lumigen_styles.zip')"
            class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-700 font-semibold inline-flex items-center gap-2 transition-colors"
          >
            <span>🎨</span> Styles as ZIP
          </button>

          <button
            type="button"
            @click="downloadFile('/api/admin/export/styles', 'lumigen_styles.json')"
            class="px-4 py-2 rounded-xl bg-slate-200 dark:bg-slate-800 text-slate-800 dark:text-slate-200 hover:bg-slate-300 dark:hover:bg-slate-700 font-semibold inline-flex items-center gap-2 transition-colors"
          >
            <span>📄</span> Styles as JSON
          </button>
        </div>
      </Card>

      <!-- Import Card -->
      <Card padding="md" class="space-y-4">
        <h4 class="font-bold text-sm text-slate-900 dark:text-white">Import Data</h4>
        <p class="text-slate-500 leading-relaxed">
          Restore or import exported JSON or ZIP backup files.
        </p>

        <input
          ref="importFileInput"
          type="file"
          accept=".json,.zip"
          class="hidden"
          @change="handleFileSelect"
        />

        <Button
          variant="secondary"
          size="md"
          :loading="isImporting"
          @click="importFileInput?.click()"
        >
          <span>📥</span> Select & import backup file
        </Button>
      </Card>
    </div>
  </div>
</template>
