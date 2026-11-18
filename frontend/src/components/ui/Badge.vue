<script setup lang="ts">
/**
 * Small status/tag pill. `dot` adds a leading status dot in the variant colour.
 */
type Variant = 'sky' | 'blue' | 'indigo' | 'emerald' | 'rose' | 'amber' | 'slate' | 'violet'
type Size = 'xs' | 'sm' | 'md'

interface Props {
  variant?: Variant
  size?: Size
  dot?: boolean
}

withDefaults(defineProps<Props>(), {
  variant: 'slate',
  size: 'sm',
  dot: false,
})

const sizeClasses: Record<Size, string> = {
  xs: 'px-1.5 py-0.5 text-2xs',
  sm: 'px-2.5 py-0.5 text-xs',
  md: 'px-3 py-1 text-xs',
}

const variantClasses: Record<Variant, string> = {
  sky: 'bg-sky-100 text-sky-800 border-sky-200 dark:bg-sky-950/60 dark:text-sky-300 dark:border-sky-800/60',
  blue: 'bg-blue-100 text-blue-800 border-blue-200 dark:bg-blue-950/60 dark:text-blue-300 dark:border-blue-800/60',
  indigo: 'bg-indigo-100 text-indigo-800 border-indigo-200 dark:bg-indigo-950/60 dark:text-indigo-300 dark:border-indigo-800/60',
  emerald: 'bg-emerald-100 text-emerald-800 border-emerald-200 dark:bg-emerald-950/60 dark:text-emerald-300 dark:border-emerald-800/60',
  rose: 'bg-rose-100 text-rose-800 border-rose-200 dark:bg-rose-950/60 dark:text-rose-300 dark:border-rose-800/60',
  amber: 'bg-amber-100 text-amber-800 border-amber-200 dark:bg-amber-950/60 dark:text-amber-300 dark:border-amber-800/60',
  violet: 'bg-violet-100 text-violet-800 border-violet-200 dark:bg-violet-950/60 dark:text-violet-300 dark:border-violet-800/60',
  slate: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800/80 dark:text-slate-300 dark:border-white/10',
}

const dotClasses: Record<Variant, string> = {
  sky: 'bg-sky-500',
  blue: 'bg-blue-500',
  indigo: 'bg-indigo-500',
  emerald: 'bg-emerald-500',
  rose: 'bg-rose-500',
  amber: 'bg-amber-500',
  violet: 'bg-violet-500',
  slate: 'bg-slate-400',
}
</script>

<template>
  <span
    :class="[
      'inline-flex shrink-0 items-center gap-1.5 rounded-full border font-medium',
      sizeClasses[size],
      variantClasses[variant],
    ]"
  >
    <span v-if="dot" :class="['size-1.5 rounded-full', dotClasses[variant]]" aria-hidden="true" />
    <slot />
  </span>
</template>
