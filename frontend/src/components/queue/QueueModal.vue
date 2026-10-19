<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useQueueStore } from '@/stores/queue'
import { useImageViewerStore } from '@/stores/imageViewer'
import Spinner from '@/components/ui/Spinner.vue'
import Badge from '@/components/ui/Badge.vue'
import type { Generation } from '@/types'

const queueStore = useQueueStore()
const imageViewerStore = useImageViewerStore()

const activeTab = ref<'active' | 'recent'>('active')

const displayList = computed(() => {
  if (activeTab.value === 'active') {
    return queueStore.activeJobs
  }
  return queueStore.recentJobs
})

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && queueStore.isOpen) {
    queueStore.closeQueue()
  }
}

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
    if (open) {
      document.body.style.overflow = 'hidden'
      // Default to active tab if there are active jobs, otherwise show recent
      if (queueStore.totalActive > 0) {
        activeTab.value = 'active'
      }
    } else {
      document.body.style.overflow = ''
    }
  }
)

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <!-- Backdrop -->
    <Transition
      enter-active-class="transition-opacity duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition-opacity duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="queueStore.isOpen"
        class="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm"
        @click="queueStore.closeQueue"
      />
    </Transition>

    <!-- Slide-over Drawer (From Left) -->
    <Transition
      enter-active-class="transition-transform duration-300 ease-out"
      enter-from-class="-translate-x-full"
      enter-to-class="translate-x-0"
      leave-active-class="transition-transform duration-200 ease-in"
      leave-from-class="translate-x-0"
      leave-to-class="-translate-x-full"
    >
      <aside
        v-if="queueStore.isOpen"
        class="fixed inset-y-0 left-0 z-50 flex w-full max-w-md sm:max-w-lg flex-col bg-white text-slate-900 shadow-2xl dark:bg-slate-900 dark:text-slate-100 border-r border-slate-200 dark:border-white/10 select-none overflow-hidden"
      >
        <!-- Drawer Header -->
        <div class="flex items-center justify-between px-5 py-4 border-b border-slate-200 dark:border-white/10 bg-slate-50/80 dark:bg-slate-950/50 shrink-0">
          <div class="flex items-center gap-2.5">
            <span class="flex h-8 w-8 items-center justify-center rounded-xl bg-sky-500/10 text-sky-600 dark:bg-sky-400/20 dark:text-sky-300 text-base">
              ⏳
            </span>
            <div>
              <div class="flex items-center gap-2">
                <h3 class="text-sm sm:text-base font-bold tracking-tight text-slate-900 dark:text-white">
                  Generation Queue
                </h3>
                <span
                  v-if="queueStore.totalActive > 0"
                  class="px-2 py-0.5 rounded-full text-[11px] font-semibold bg-sky-500 text-white shadow-sm"
                >
                  {{ queueStore.totalActive }} active
                </span>
              </div>
              <p class="text-[11px] text-slate-500 dark:text-slate-400">
                Progress & Job Management
              </p>
            </div>
          </div>

          <div class="flex items-center gap-1.5">
            <button
              type="button"
              @click="queueStore.fetchQueue"
              class="p-2 rounded-xl text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/10 transition-colors"
              title="Refresh"
            >
              <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
            </button>
            <button
              type="button"
              @click="queueStore.closeQueue"
              class="p-2 rounded-xl text-slate-400 hover:text-slate-700 dark:hover:text-slate-200 hover:bg-slate-100 dark:hover:bg-white/10 transition-colors"
              title="Close (Esc)"
            >
              <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        <!-- Navigation Tabs -->
        <div class="flex border-b border-slate-200 dark:border-white/10 px-5 pt-2 bg-slate-50/50 dark:bg-slate-950/30 shrink-0">
          <button
            type="button"
            @click="activeTab = 'active'"
            :class="[
              'flex items-center gap-2 px-3 py-2 border-b-2 text-xs font-semibold transition-all -mb-[1px]',
              activeTab === 'active'
                ? 'border-sky-500 text-sky-600 dark:text-sky-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200',
            ]"
          >
            <span>Active Jobs</span>
            <span
              :class="[
                'px-1.5 py-0.2 rounded-full text-[10px] font-mono leading-none',
                activeTab === 'active' ? 'bg-sky-100 dark:bg-sky-950 text-sky-600 dark:text-sky-300' : 'bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400',
              ]"
            >
              {{ queueStore.activeJobs.length }}
            </span>
          </button>

          <button
            type="button"
            @click="activeTab = 'recent'"
            :class="[
              'flex items-center gap-2 px-3 py-2 border-b-2 text-xs font-semibold transition-all -mb-[1px]',
              activeTab === 'recent'
                ? 'border-sky-500 text-sky-600 dark:text-sky-400'
                : 'border-transparent text-slate-500 hover:text-slate-800 dark:text-slate-400 dark:hover:text-slate-200',
            ]"
          >
            <span>History</span>
            <span class="px-1.5 py-0.2 rounded-full text-[10px] font-mono leading-none bg-slate-200 dark:bg-slate-800 text-slate-600 dark:text-slate-400">
              {{ queueStore.recentJobs.length }}
            </span>
          </button>
        </div>

        <!-- Drawer Content List -->
        <div class="flex-1 overflow-y-auto p-4 space-y-3">
          <!-- Empty State -->
          <div
            v-if="displayList.length === 0"
            class="flex flex-col items-center justify-center py-16 text-center text-slate-500 dark:text-slate-400 px-4"
          >
            <span class="text-3xl mb-2">📥</span>
            <p class="text-sm font-semibold text-slate-700 dark:text-slate-200">
              {{ activeTab === 'active' ? 'No active generations' : 'No recent jobs' }}
            </p>
            <p class="text-xs mt-1 max-w-xs">
              {{ activeTab === 'active' ? 'Start one or more generations in the prompt editor to track them here.' : 'Completed or failed generations will appear here.' }}
            </p>
          </div>

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

        <!-- Footer -->
        <div class="px-5 py-3 border-t border-slate-200 dark:border-white/10 bg-slate-50/60 dark:bg-slate-950/40 flex items-center justify-between text-[11px] text-slate-500 shrink-0">
          <span>Backend-driven pipeline</span>
          <button
            type="button"
            @click="queueStore.closeQueue"
            class="text-xs font-semibold text-slate-700 dark:text-slate-300 hover:underline"
          >
            Close
          </button>
        </div>
      </aside>
    </Transition>
  </Teleport>
</template>
