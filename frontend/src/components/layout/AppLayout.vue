<script setup lang="ts">
import AppHeader from './AppHeader.vue'
import ToastContainer from '@/components/ui/ToastContainer.vue'
</script>

<template>
  <div class="relative flex min-h-screen flex-col bg-slate-50 text-slate-900 dark:bg-slate-950 dark:text-slate-100 antialiased font-sans">
    <!-- Ambient glowing backgrounds -->
    <div aria-hidden="true" class="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div class="absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-sky-500/10 blur-3xl dark:bg-sky-400/10"></div>
      <div class="absolute bottom-0 right-0 h-[30rem] w-[30rem] rounded-full bg-blue-600/10 blur-3xl dark:bg-blue-600/10"></div>
      <div class="absolute left-0 top-1/3 h-80 w-80 rounded-full bg-indigo-500/10 blur-3xl dark:bg-indigo-500/10"></div>
    </div>

    <!-- Header -->
    <AppHeader />

    <!-- Main Content Area -->
    <main class="flex-1 w-full mx-auto max-w-7xl px-4 py-4 sm:px-6 sm:py-6 lg:px-8">
      <slot />
    </main>

    <!-- Global Toast Container -->
    <ToastContainer />
  </div>
</template>
