<script setup lang="ts">
import Spinner from './Spinner.vue'

/**
 * Centered loading indicator for sections and pages (announced to screen readers).
 */
interface Props {
  label?: string
  size?: 'sm' | 'md'
}

withDefaults(defineProps<Props>(), {
  label: 'Loading…',
  size: 'md',
})
</script>

<template>
  <div
    role="status"
    aria-live="polite"
    :class="['flex flex-col items-center justify-center gap-2 text-sky-500', size === 'sm' ? 'py-6' : 'py-16']"
  >
    <Spinner :size="size === 'sm' ? 'md' : 'lg'" />
    <span :class="size === 'sm' ? 'sr-only' : 'text-xs text-slate-500 dark:text-slate-400'">{{ label }}</span>
  </div>
</template>
