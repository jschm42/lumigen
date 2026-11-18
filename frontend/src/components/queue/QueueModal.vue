<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useQueueStore } from '@/stores/queue'
import { useImageViewerStore } from '@/stores/imageViewer'
import Spinner from '@/components/ui/Spinner.vue'
import Badge from '@/components/ui/Badge.vue'
import type { Generation } from '@/types'
import { Inbox, RefreshCw } from 'lucide-vue-next'
import Drawer from '@/components/ui/Drawer.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import IconButton from '@/components/ui/IconButton.vue'
import Button from '@/components/ui/Button.vue'
import Tabs from '@/components/ui/Tabs.vue'

const queueStore = useQueueStore()
const imageViewerStore = useImageViewerStore()

const activeTab = ref<'active' | 'recent'>('active')

const displayList = computed(() => {
  if (activeTab.value === 'active') {
    return queueStore.activeJobs
  }
  return queueStore.recentJobs
})

const tabs = computed(() => [
  { id: 'active', label: 'Active Jobs', badge: queueStore.activeJobs.length },
  { id: 'recent', label: 'History', badge: queueStore.recentJobs.length },
])

function formatTime(isoString?: string | null) {
  if (!isoString) return ''
  try {
    const d = new Date(isoString)
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
  } catch {
    return ''
  }
}

function viewAsset(gen: Generation) {
  if (gen.assets && gen.assets.length > 0) {
    const first = gen.assets[0]
    imageViewerStore.openViewer({
      asset: first,
      generation: gen,
      url: first.image_url || first.thumbnail_url,
    })
  }
}

watch(
  () => queueStore.isOpen,
  (open) => {
    // Default to active tab if there are active jobs, otherwise show recent
    if (open && queueStore.totalActive > 0) {
      activeTab.value = 'active'
    }
  }
)
</script>

<template>
  <Drawer
    :open="queueStore.isOpen"
    side="left"
    size="lg"
    class="select-none"
    @update:open="(open: boolean) => { if (!open) queueStore.closeQueue() }"
  >
    <template #header>
      <div class="flex items-center justify-between gap-2">
        <div class="min-w-0">
          <div class="flex items-center gap-2">
            <h2 class="text-sm sm:text-base font-bold tracking-tight text-slate-900 dark:text-white">Generation queue</h2>
            <Badge v-if="queueStore.totalActive > 0" variant="sky" size="xs">{{ queueStore.totalActive }} active</Badge>
          </div>
          <p class="text-2xs text-slate-500 dark:text-slate-400">Progress &amp; job management</p>
        </div>
        <IconButton label="Refresh queue" @click="queueStore.fetchQueue">
          <RefreshCw class="size-4" aria-hidden="true" />
        </IconButton>
      </div>
    </template>

    <template #toolbar>
      <div class="shrink-0 bg-slate-50/50 px-5 pt-3 dark:bg-slate-950/30">
        <Tabs :tabs="tabs" :model-value="activeTab" variant="underline" @update:model-value="activeTab = $event as 'active' | 'recent'" />
      </div>
    </template>

    <div class="space-y-3 p-4">

          <!-- Empty State -->
          <EmptyState
            v-if="displayList.length === 0"
            :icon="Inbox"
            :title="activeTab === 'active' ? 'No active generations' : 'No recent jobs'"
            :description="activeTab === 'active' ? 'Start one or more generations in the prompt editor to track them here.' : 'Completed or failed generations will appear here.'"
          />

          <!-- Job Cards -->
          <div
            v-for="job in displayList"
            :key="job.id"
            class="rounded-xl border border-slate-200/80 bg-white dark:border-white/10 dark:bg-slate-800/80 p-3.5 shadow-sm space-y-2.5 transition-all"
          >
            <!-- Job Header -->
            <div class="flex items-start justify-between gap-2">
              <div class="flex items-center gap-2 flex-wrap">
                <span class="text-xs font-bold text-slate-800 dark:text-slate-200 font-mono">
                  #{{ job.id }}
                </span>

                <!-- Status Badge -->
                <Badge
                  v-if="job.status === 'running'"
                  variant="sky"
                  size="xs"
                  class="animate-pulse"
                >
                  ⚡ Running...
                </Badge>
                <Badge
                  v-else-if="job.status === 'queued'"
                  variant="amber"
                  size="xs"
                >
                  ⏳ Queued
                </Badge>
                <Badge
                  v-else-if="job.status === 'succeeded'"
                  variant="emerald"
                  size="xs"
                >
                  ✓ Completed
                </Badge>
                <Badge
                  v-else-if="job.status === 'failed'"
                  variant="rose"
                  size="xs"
                >
                  ✕ Failed
                </Badge>
                <Badge
                  v-else-if="job.status === 'cancelled'"
                  variant="slate"
                  size="xs"
                >
                  ✕ Cancelled
                </Badge>

                <!-- Model Badge -->
                <span v-if="job.model_name" class="text-[10px] text-slate-500 dark:text-slate-400 font-medium truncate max-w-[140px]">
                  {{ job.model_name }}
                </span>
              </div>

              <!-- Time -->
              <span class="text-[10px] text-slate-400 dark:text-slate-500 font-mono shrink-0">
                {{ formatTime(job.created_at) }}
              </span>
            </div>

            <!-- Prompt Snippet -->
            <p class="text-xs text-slate-700 dark:text-slate-300 line-clamp-2 leading-relaxed">
              {{ job.prompt }}
            </p>

            <!-- Progress Bar (for running / queued jobs) -->
            <div v-if="job.status === 'running' || job.status === 'queued'" class="space-y-1">
              <div class="flex justify-between text-[10px] text-slate-500 dark:text-slate-400 font-mono">
                <span>{{ job.status === 'running' ? 'Processing' : 'Waiting in queue' }}</span>
                <span>{{ job.progress ?? (job.status === 'running' ? 50 : 0) }}%</span>
              </div>
              <div class="h-1.5 w-full bg-slate-100 dark:bg-slate-700 rounded-full overflow-hidden">
                <div
                  :class="[
                    'h-full rounded-full transition-all duration-300',
                    job.status === 'running' ? 'bg-sky-500 animate-pulse' : 'bg-amber-400',
                  ]"
                  :style="{ width: `${job.progress ?? (job.status === 'running' ? 50 : 15)}%` }"
                />
              </div>
            </div>

            <!-- Error message if failed -->
            <div
              v-if="job.status === 'failed' && job.error_message"
              class="rounded-lg bg-rose-50 dark:bg-rose-950/40 p-2 text-[11px] text-rose-700 dark:text-rose-300 border border-rose-200 dark:border-rose-900/50 break-words"
            >
              {{ job.error_message }}
            </div>

            <!-- Action buttons -->
            <div class="flex items-center justify-between pt-1 border-t border-slate-100 dark:border-white/5">
              <div class="flex items-center gap-2">
                <span v-if="job.aspect_ratio" class="text-[10px] font-mono text-slate-400 dark:text-slate-500">
                  {{ job.aspect_ratio }}
                </span>
              </div>

              <div class="flex items-center gap-2">
                <!-- Cancel Button for Active Jobs -->
                <button
                  v-if="job.status === 'queued' || job.status === 'running'"
                  type="button"
                  @click="queueStore.cancelJob(job.id)"
                  :disabled="queueStore.actionLoading[job.id]"
                  class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/40 text-[11px] font-semibold transition disabled:opacity-50"
                  title="Cancel job"
                >
                  <Spinner v-if="queueStore.actionLoading[job.id]" size="xs" />
                  <span v-else>✕</span>
                  <span>Cancel</span>
                </button>

                <!-- Retry Button for Failed or Cancelled Jobs -->
                <button
                  v-if="job.status === 'failed' || job.status === 'cancelled'"
                  type="button"
                  @click="queueStore.retryJob(job.id)"
                  :disabled="queueStore.actionLoading[job.id]"
                  class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-sky-500 hover:bg-sky-600 text-white text-[11px] font-semibold transition shadow-sm disabled:opacity-50"
                  title="Retry job"
                >
                  <Spinner v-if="queueStore.actionLoading[job.id]" size="xs" class="text-white" />
                  <span v-else>🔄</span>
                  <span>Retry</span>
                </button>

                <!-- View Asset Button for Succeeded Jobs -->
                <button
                  v-if="job.status === 'succeeded' && job.assets && job.assets.length > 0"
                  type="button"
                  @click="viewAsset(job)"
                  class="inline-flex items-center gap-1 px-2.5 py-1 rounded-lg bg-slate-100 hover:bg-slate-200 dark:bg-white/10 dark:hover:bg-white/20 text-slate-800 dark:text-slate-200 text-[11px] font-semibold transition"
                  title="View image"
                >
                  <span>🖼️</span>
                  <span>View</span>
                </button>
              </div>
            </div>
          </div>
    </div>

    <template #footer>
      <div class="flex items-center justify-between text-2xs text-slate-500 dark:text-slate-400">
        <span>Backend-driven pipeline</span>
        <Button variant="ghost" size="xs" @click="queueStore.closeQueue">Close</Button>
      </div>
    </template>
  </Drawer>
</template>
