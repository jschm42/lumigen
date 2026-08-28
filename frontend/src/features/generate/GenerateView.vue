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
  <div class="flex gap-4 h-[calc(100vh-6rem)]">
    <!-- Left Session/Artbook Sidebar -->
    <div :class="['transition-all duration-200', isSidebarOpen ? 'block' : 'hidden lg:block']">
      <SessionSidebar />
    </div>

    <!-- Main Generation Studio Workspace -->
    <div class="flex-1 flex flex-col min-w-0 rounded-2xl border border-slate-200/80 bg-white/70 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/70 p-4 shadow-sm overflow-hidden">
      <!-- Top Bar: Studio Controls (Model, Profile, Aspect Ratio, Seed) -->
      <div class="pb-3 mb-3 border-b border-slate-200/80 dark:border-white/10 shrink-0">
        <GenerationControls />
      </div>

      <!-- Center: Generation Chat/Feed -->
      <GenerationFeed />

      <!-- Bottom: Prompt Composer -->
      <div class="pt-2 shrink-0">
        <PromptComposer />
      </div>
    </div>

    <!-- Global Asset Detail Modal (can be opened from image actions) -->
    <AssetDetailModal />
  </div>
</template>
