<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  size?: 'xs' | 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
})

const sizeClasses = computed(() => {
  switch (props.size) {
    case 'xs':
      return 'w-3 h-3 border'
    case 'sm':
      return 'w-4 h-4 border-2'
    case 'lg':
      return 'w-8 h-8 border-3'
    case 'md':
    default:
      return 'w-5 h-5 border-2'
  }
})
</script>

<template>
  <div
    :class="[
      'inline-block animate-spin rounded-full border-current border-t-transparent text-current',
      sizeClasses,
    ]"
    role="status"
    aria-label="loading"
  >
    <span class="sr-only">Loading...</span>
  </div>
</template>
