<script setup lang="ts">
/**
 * One line in a settings list: label + description on the left, control on the right.
 * Stack rows inside `<Card padding="none" class="divide-y …">`.
 */
interface Props {
  label: string
  description?: string
}

defineProps<Props>()
</script>

<template>
  <div class="flex flex-col gap-3 p-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
    <div class="min-w-0 space-y-1">
      <div class="text-sm font-semibold text-slate-800 dark:text-slate-100">{{ label }}</div>
      <p v-if="description || $slots.description" class="max-w-xl text-xs text-slate-500 dark:text-slate-400">
        <slot name="description">{{ description }}</slot>
      </p>
    </div>
    <div class="flex shrink-0 items-center gap-2">
      <slot />
    </div>
  </div>
</template>
