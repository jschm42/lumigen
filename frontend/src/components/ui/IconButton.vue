<script setup lang="ts">
/**
 * Icon-only button. `label` is required and becomes both the accessible name
 * (aria-label) and the tooltip. Pass the icon (lucide component) via the default slot.
 */
type Variant = 'ghost' | 'surface' | 'primary' | 'danger' | 'overlay'
type Size = 'xs' | 'sm' | 'md'

interface Props {
  label: string
  variant?: Variant
  size?: Size
  type?: 'button' | 'submit' | 'reset'
  disabled?: boolean
  /** Toggle state for on/off buttons; rendered as aria-pressed. */
  pressed?: boolean
  /** Show the native tooltip (default true). */
  tooltip?: boolean
}

withDefaults(defineProps<Props>(), {
  variant: 'ghost',
  size: 'sm',
  type: 'button',
  disabled: false,
  pressed: undefined,
  tooltip: true,
})

const sizeClasses: Record<Size, string> = {
  xs: 'p-1 rounded-lg',
  sm: 'p-1.5 rounded-lg',
  md: 'p-2 rounded-xl',
}

const variantClasses: Record<Variant, string> = {
  ghost:
    'text-slate-500 hover:bg-slate-200/60 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-white',
  surface:
    'border border-slate-300/60 bg-white/70 text-slate-700 hover:bg-white dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-200 dark:hover:bg-slate-800',
  primary: 'bg-sky-500 text-white hover:bg-sky-600 shadow-sm',
  danger:
    'text-rose-600 hover:bg-rose-50 hover:text-rose-700 dark:text-rose-400 dark:hover:bg-rose-950/40 dark:hover:text-rose-300',
  overlay: 'bg-slate-950/55 text-white backdrop-blur-sm hover:bg-slate-950/75',
}

const pressedClasses = 'bg-sky-500/15 text-sky-700 dark:bg-sky-400/20 dark:text-sky-300'
</script>

<template>
  <button
    :type="type"
    :disabled="disabled"
    :aria-label="label"
    :aria-pressed="pressed"
    :title="tooltip ? label : undefined"
    :class="[
      'inline-flex shrink-0 cursor-pointer items-center justify-center transition-colors duration-150',
      'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40',
      'disabled:pointer-events-none disabled:opacity-50',
      sizeClasses[size],
      pressed ? pressedClasses : variantClasses[variant],
    ]"
  >
    <slot />
  </button>
</template>
