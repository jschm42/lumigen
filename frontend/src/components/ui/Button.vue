<script setup lang="ts">
import { computed } from 'vue'
import Spinner from './Spinner.vue'

interface Props {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline' | 'surface'
  size?: 'xs' | 'sm' | 'md' | 'lg'
  disabled?: boolean
  loading?: boolean
  type?: 'button' | 'submit' | 'reset'
  fullWidth?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  disabled: false,
  loading: false,
  type: 'button',
  fullWidth: false,
})

const sizeClasses = computed(() => {
  switch (props.size) {
    case 'xs':
      return 'px-2 py-1 text-xs rounded-lg gap-1.5'
    case 'sm':
      return 'px-3 py-1.5 text-xs font-medium rounded-xl gap-1.5'
    case 'lg':
      return 'px-5 py-3 text-base font-semibold rounded-2xl gap-2.5'
    case 'md':
    default:
      return 'px-4 py-2 text-sm font-semibold rounded-xl gap-2'
  }
})

const variantClasses = computed(() => {
  switch (props.variant) {
    case 'secondary':
      return 'bg-slate-200/80 hover:bg-slate-300/80 text-slate-800 dark:bg-slate-800/80 dark:hover:bg-slate-700 dark:text-slate-100 border border-slate-300/60 dark:border-white/10 shadow-sm'
    case 'ghost':
      return 'bg-transparent hover:bg-slate-200/60 text-slate-700 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white'
    case 'danger':
      return 'bg-rose-500 hover:bg-rose-600 text-white shadow-md shadow-rose-500/20 active:scale-[0.98]'
    case 'outline':
      return 'bg-transparent border border-slate-300 hover:border-slate-400 text-slate-700 dark:border-white/20 dark:hover:border-white/40 dark:text-slate-200'
    case 'surface':
      return 'bg-white/80 hover:bg-white text-slate-800 dark:bg-slate-900/80 dark:hover:bg-slate-800 dark:text-slate-200 border border-slate-300/60 dark:border-white/10 shadow-sm'
    case 'primary':
    default:
      return 'bg-gradient-to-r from-sky-500 to-blue-600 hover:from-sky-400 hover:to-blue-500 text-white shadow-md shadow-sky-500/25 active:scale-[0.98]'
  }
})
</script>

<template>
  <button
    :type="type"
    :disabled="disabled || loading"
    :class="[
      'inline-flex items-center justify-center transition-all duration-150 cursor-pointer select-none focus:outline-none focus:ring-2 focus:ring-sky-500/40 disabled:opacity-50 disabled:cursor-not-allowed disabled:pointer-events-none',
      sizeClasses,
      variantClasses,
      fullWidth ? 'w-full' : '',
    ]"
  >
    <Spinner v-if="loading" size="sm" class="shrink-0" />
    <slot name="icon" v-else />
    <slot />
    <slot name="right-icon" />
  </button>
</template>
