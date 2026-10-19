<script setup lang="ts">
import { onMounted } from 'vue'
import AppHeader from './AppHeader.vue'
import ToastContainer from '@/components/ui/ToastContainer.vue'
import ImageViewerModal from '@/components/ui/ImageViewerModal.vue'
import QueueModal from '@/components/queue/QueueModal.vue'
import CreditsModal from '@/components/ui/CreditsModal.vue'
import { useQueueStore } from '@/stores/queue'

const queueStore = useQueueStore()

onMounted(() => {
  queueStore.fetchQueue()
})
</script>

<template>
  <div class="relative flex h-screen w-screen overflow-hidden flex-col bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 antialiased font-sans">
    <!-- Ambient glowing backgrounds -->
    <div aria-hidden="true" class="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div class="absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-sky-500/10 blur-3xl dark:bg-sky-400/10"></div>
      <div class="absolute bottom-0 right-0 h-[30rem] w-[30rem] rounded-full bg-blue-600/10 blur-3xl dark:bg-blue-600/10"></div>
      <div class="absolute left-0 top-1/3 h-80 w-80 rounded-full bg-indigo-500/10 blur-3xl dark:bg-indigo-500/10"></div>
    </div>

    <!-- Header -->
    <AppHeader />

    <!-- Main Content Area: Maximized on display with clean fluid padding -->
    <main class="flex-1 w-full min-h-0 flex flex-col overflow-hidden px-2 sm:px-4 py-2">
      <slot />
    </main>

    <!-- Global Image Zoom & Lightbox Viewer Modal -->
    <ImageViewerModal />

    <!-- Global Generation Queue Slide-over Drawer -->
    <QueueModal />

    <!-- Global Credits & Licenses Modal -->
    <CreditsModal />

    <!-- Global Toast Container -->
    <ToastContainer />
  </div>
</template>
