<script setup lang="ts">
/**
 * Circular initials badge for a user.
 */
type Size = 'xs' | 'sm' | 'md'

interface Props {
  initials: string
  size?: Size
}

withDefaults(defineProps<Props>(), {
  size: 'sm',
})

const sizeClasses: Record<Size, string> = {
  xs: 'size-6 text-2xs',
  sm: 'size-8 text-xs',
  md: 'size-10 text-sm',
}
</script>

<template>
  <span
    aria-hidden="true"
    :class="[
      'inline-flex shrink-0 items-center justify-center rounded-full bg-gradient-to-tr from-sky-400 to-blue-600 font-bold text-white shadow-sm',
      sizeClasses[size],
    ]"
  >
    {{ initials }}
  </span>
</template>
