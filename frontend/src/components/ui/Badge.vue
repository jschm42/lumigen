<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  variant?: 'sky' | 'blue' | 'indigo' | 'emerald' | 'rose' | 'amber' | 'slate' | 'violet'
  size?: 'xs' | 'sm' | 'md'
  dot?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'slate',
  size: 'sm',
  dot: false,
})

const sizeClasses = computed(() => {
  switch (props.size) {
    case 'xs':
      return 'px-1.5 py-0.5 text-[10px]'
    case 'md':
      return 'px-3 py-1 text-xs'
    case 'sm':
    default:
      return 'px-2.5 py-0.5 text-xs'
  }
})

const variantClasses = computed(() => {
  switch (props.variant) {
    case 'sky':
      return 'bg-sky-100 text-sky-800 border-sky-200 dark:bg-sky-950/60 dark:text-sky-300 dark:border-sky-800/60'
    case 'blue':
      return 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:border-blue-800/60'
    case 'indigo':
      return 'bg-indigo-100 text-indigo-800 border-indigo-200 dark:bg-indigo-950/60 dark:text-indigo-300 dark:border-indigo-800/60'
    case 'emerald':
      return 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800/60'
    case 'rose':
      return 'bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800/60'
    case 'amber':
      return 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800/60'
    case 'violet':
      return 'bg-violet-100 text-violet-800 border-violet-200 dark:bg-violet-950/60 dark:text-violet-300 dark:border-violet-800/60'
    case 'slate':
    default:
      return 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800/80 dark:text-slate-300 dark:border-white/10'
  }
})
</script>

<template>
  <span
    :class="[
      'inline-flex items-center gap-1.5 font-medium rounded-full border shrink-0',
      sizeClasses,
      variantClasses,
    ]"
  >
    <span
      v-if="dot"
      :class="[
        'w-1.5 h-1.5 rounded-full',
        variant === 'emerald' ? 'bg-emerald-500' : '',
        variant === 'sky' ? 'bg-sky-500' : '',
        variant === 'rose' ? 'bg-rose-500' : '',
        variant === 'amber' ? 'bg-amber-500' : '',
        variant === 'slate' ? 'bg-slate-400' : '',
      ]"
    />
    <slot />
  </span>
</template>
