<script setup lang="ts">
import type { Component } from 'vue'

/**
 * Placeholder for lists and grids without content. Put calls to action into `#actions`.
 */
interface Props {
  title: string
  description?: string
  /** lucide icon component, e.g. `:icon="Images"`. */
  icon?: Component
  size?: 'sm' | 'md'
}

withDefaults(defineProps<Props>(), {
  size: 'md',
})
</script>

<template>
  <div :class="['flex flex-col items-center text-center', size === 'sm' ? 'gap-2 py-8' : 'gap-3 py-16']">
    <span
      v-if="icon"
      class="flex size-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400 dark:bg-slate-800/60 dark:text-slate-500"
    >
      <component :is="icon" class="size-6" aria-hidden="true" />
    </span>
    <h3 class="text-sm font-semibold text-slate-800 dark:text-white">{{ title }}</h3>
    <p v-if="description || $slots.description" class="max-w-sm text-xs text-slate-500 dark:text-slate-400">
      <slot name="description">{{ description }}</slot>
    </p>
    <div v-if="$slots.actions" class="flex flex-wrap justify-center gap-2 pt-1">
      <slot name="actions" />
    </div>
  </div>
</template>
