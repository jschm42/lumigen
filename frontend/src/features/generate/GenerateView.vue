<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useGenerateStore } from '@/stores/generate'
import { useProfilesStore } from '@/stores/profiles'
import SessionSidebar from './components/SessionSidebar.vue'
import GenerationControls from './components/GenerationControls.vue'
import GenerationFeed from './components/GenerationFeed.vue'
import PromptComposer from './components/PromptComposer.vue'
import AssetDetailModal from '@/features/gallery/components/AssetDetailModal.vue'

const generateStore = useGenerateStore()
const profilesStore = useProfilesStore()
const isSidebarOpen = ref(true)

onMounted(async () => {
  await Promise.all([
    generateStore.loadModelsAndStyles(),
    profilesStore.fetchProfiles(),
  ])
})
</script>

<template>
  <div class="flex gap-2.5 sm:gap-3.5 h-full w-full min-h-0 overflow-hidden">
    <!-- Left Session/Artbook Sidebar (Collapsible for display maximization) -->
    <div
      v-if="isSidebarOpen"
      class="transition-all duration-200 shrink-0 h-full"
    >
      <SessionSidebar />
    </div>

    <!-- Main Generation Studio Workspace -->
    <div class="flex-1 flex flex-col min-w-0 h-full rounded-2xl border border-slate-200/80 bg-white/75 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/75 p-3 sm:p-4 shadow-sm overflow-hidden">
      <!-- Top Bar: Studio Controls with Sidebar Toggle -->
      <div class="pb-2.5 mb-2 border-b border-slate-200/80 dark:border-white/10 shrink-0 flex items-center gap-2">
        <!-- Sidebar Toggle Button -->
        <button
          type="button"
          @click="isSidebarOpen = !isSidebarOpen"
          :class="[
            'inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-xl border text-xs font-semibold transition-all shadow-sm shrink-0 cursor-pointer',
            isSidebarOpen
              ? 'border-slate-300/80 bg-white text-slate-700 hover:bg-slate-100 dark:border-white/10 dark:bg-slate-800 dark:text-slate-200'
              : 'border-sky-400 bg-sky-50 text-sky-700 dark:border-sky-500/40 dark:bg-sky-950/60 dark:text-sky-300',
          ]"
          :title="isSidebarOpen ? 'Collapse artbook sidebar (for maximum image display)' : 'Show artbook sidebar'"
        >
          <span class="text-xs">{{ isSidebarOpen ? '◀' : '▶' }}</span>
          <span class="hidden md:inline">{{ isSidebarOpen ? 'Hide Sidebar' : 'Artbooks' }}</span>
        </button>

        <!-- Generation Controls Bar -->
        <div class="flex-1 min-w-0">
          <GenerationControls />
        </div>
      </div>

      <!-- Center: Generation Chat/Feed -->
      <GenerationFeed />

      <!-- Bottom: Prompt Composer -->
      <div class="pt-2 shrink-0">
        <PromptComposer />
      </div>
    </div>

    <!-- Global Asset Detail Modal -->
    <AssetDetailModal />
  </div>
</template>
