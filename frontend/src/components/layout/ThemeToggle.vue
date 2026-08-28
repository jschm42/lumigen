<script setup lang="ts">
import { useThemeStore } from '@/stores/theme'

const themeStore = useThemeStore()
</script>

<template>
  <button
    type="button"
    @click="themeStore.toggle"
    class="relative p-2 rounded-xl border border-slate-300/60 bg-white/70 text-slate-700 hover:bg-slate-100 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-300 dark:hover:bg-white/10 transition-colors cursor-pointer"
    :title="themeStore.isDark ? 'Zum Hell-Modus wechseln' : 'Zum Dunkel-Modus wechseln'"
    aria-label="Theme umschalten"
  >
    <!-- Sun icon for dark mode (click to switch to light) -->
    <svg v-if="themeStore.isDark" class="w-4 h-4 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3v1m0 16v1m9-9h-1M4 9h-1m15.364 6.364l-.707-.707M6.343 6.343l-.707-.707m12.728 0l-.707.707M6.343 17.657l-.707.707M16 12a4 4 0 11-8 0 4 4 0 018 0z" />
    </svg>
    <!-- Moon icon for light mode (click to switch to dark) -->
    <svg v-else class="w-4 h-4 text-slate-700" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M20.354 15.354A9 9 0 018.646 3.646 9.003 9.003 0 0012 21a9.003 9.003 0 008.354-5.646z" />
    </svg>
  </button>
</template>
