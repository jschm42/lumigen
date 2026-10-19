<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useGenerateStore } from '@/stores/generate'
import { useProfilesStore } from '@/stores/profiles'
import { useSessionsStore } from '@/stores/sessions'
import { useAuthStore } from '@/stores/auth'
import SessionSidebar from './components/SessionSidebar.vue'
import GenerationControls from './components/GenerationControls.vue'
import GenerationFeed from './components/GenerationFeed.vue'
import PromptComposer from './components/PromptComposer.vue'
import AssetDetailModal from '@/features/gallery/components/AssetDetailModal.vue'
import { describeUsage, formatUsage } from '@/utils/format'

const SIDEBAR_KEY = 'lumigen_generate_sidebar_collapsed'

const generateStore = useGenerateStore()
const profilesStore = useProfilesStore()
const sessionsStore = useSessionsStore()
const authStore = useAuthStore()

function readCollapsed(): boolean {
  try {
    const stored = localStorage.getItem(SIDEBAR_KEY)
    if (stored !== null) return stored === '1'
  } catch (_e) {
    // Storage may be unavailable; fall back to viewport width.
  }
  return typeof window !== 'undefined' && window.innerWidth < 1024
}

const isSidebarCollapsed = ref(readCollapsed())

watch(isSidebarCollapsed, (collapsed) => {
  try {
    localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0')
  } catch (_e) {
    // Ignore storage errors.
  }
})

const sessionTitle = computed(() => sessionsStore.activeSession?.title || (sessionsStore.activeSessionToken ? 'Session' : 'New session'))

const imageCount = computed(() =>
  generateStore.generations.reduce((sum, g) => sum + (g.assets?.length || 0), 0)
)

const sessionUsageText = computed(() =>
  authStore.uiSettings.show_token_usage ? formatUsage(generateStore.sessionUsageTotal) : null
)

onMounted(async () => {
  await Promise.all([
    generateStore.loadModelsAndStyles(),
    profilesStore.fetchProfiles(),
  ])
})
</script>

<template>
  <div class="flex gap-2.5 sm:gap-3 h-full w-full min-h-0 overflow-hidden">
    <!-- Session sidebar: full panel or slim rail -->
    <div class="h-full shrink-0">
      <SessionSidebar :collapsed="isSidebarCollapsed" @toggle="isSidebarCollapsed = !isSidebarCollapsed" />
    </div>

    <!-- Main Generation Studio Workspace -->
    <section class="flex-1 flex flex-col min-w-0 h-full rounded-2xl border border-slate-200/80 bg-white/75 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/75 shadow-sm overflow-hidden">
      <!-- Session header -->
      <div class="shrink-0 border-b border-slate-200/80 px-3 py-2.5 dark:border-white/10 sm:px-4">
        <div class="flex flex-wrap items-center gap-x-4 gap-y-2">
          <div class="min-w-0 flex-1 basis-48">
            <h2 class="truncate text-sm font-bold text-slate-900 dark:text-white" data-testid="session-title">{{ sessionTitle }}</h2>
            <p class="flex flex-wrap items-center gap-x-2 text-[11px] text-slate-500 dark:text-slate-400">
              <span>{{ generateStore.generations.length }} prompts · {{ imageCount }} images</span>
              <span v-if="generateStore.activeJobIds.length > 0" class="inline-flex items-center gap-1 font-medium text-sky-600 dark:text-sky-400">
                <span class="h-1.5 w-1.5 animate-pulse rounded-full bg-sky-500" />
                {{ generateStore.activeJobIds.length }} running
              </span>
              <span
                v-if="sessionUsageText"
                class="inline-flex items-center gap-1 font-medium text-amber-700 dark:text-amber-300"
                :title="describeUsage(generateStore.sessionUsageTotal)"
                data-testid="session-usage"
              >
                ⚡ {{ sessionUsageText }}
              </span>
            </p>
          </div>
          <div class="w-full min-w-0 lg:w-auto lg:flex-[2]">
            <GenerationControls />
          </div>
        </div>
      </div>

      <!-- Feed -->
      <div class="flex min-h-0 flex-1 flex-col px-2 pt-3 sm:px-4">
        <GenerationFeed />
      </div>

      <!-- Prompt Composer -->
      <div class="shrink-0 px-2 pb-2 sm:px-4 sm:pb-3">
        <div class="mx-auto w-full max-w-5xl">
          <PromptComposer />
        </div>
      </div>
    </section>

    <!-- Global Asset Detail Modal -->
    <AssetDetailModal />
  </div>
</template>
