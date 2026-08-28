<script setup lang="ts">
interface Props {
  hover?: boolean
  glass?: boolean
  padding?: 'none' | 'sm' | 'md' | 'lg'
}

withDefaults(defineProps<Props>(), {
  hover: false,
  glass: true,
  padding: 'md',
})
</script>

<template>
  <div
    :class="[
      'rounded-2xl transition-all duration-200',
      glass ? 'glass-panel' : 'bg-white border border-slate-200 shadow-sm dark:bg-slate-900 dark:border-white/10',
      hover ? 'hover:border-sky-500/50 hover:shadow-lg dark:hover:border-sky-400/40 hover:-translate-y-0.5' : '',
      padding === 'none' ? 'p-0' : '',
      padding === 'sm' ? 'p-3 sm:p-4' : '',
      padding === 'md' ? 'p-5 sm:p-6' : '',
      padding === 'lg' ? 'p-6 sm:p-8' : '',
    ]"
  >
    <div v-if="$slots.header" class="mb-4 pb-3 border-b border-slate-200/60 dark:border-white/10">
      <slot name="header" />
    </div>
    <slot />
    <div v-if="$slots.footer" class="mt-4 pt-3 border-t border-slate-200/60 dark:border-white/10">
      <slot name="footer" />
    </div>
  </div>
</template>
