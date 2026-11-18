<script setup lang="ts">
/**
 * Placeholder block shown while content loads. Size it with utility classes, e.g. `class="aspect-square"`.
 */
interface Props {
  rounded?: 'lg' | 'xl' | '2xl' | 'full'
}

withDefaults(defineProps<Props>(), {
  rounded: '2xl',
})

const roundedClasses = {
  lg: 'rounded-lg',
  xl: 'rounded-xl',
  '2xl': 'rounded-2xl',
  full: 'rounded-full',
} as const
</script>

<template>
  <div
    aria-hidden="true"
    :class="['bg-slate-200/80 motion-safe:animate-pulse dark:bg-slate-800/60', roundedClasses[rounded]]"
  />
</template>
