<script setup lang="ts">
import { inject, type Component } from 'vue'
import type { RouteLocationRaw } from 'vue-router'
import { DROPDOWN_CLOSE_KEY } from './dropdown'

/**
 * Entry inside a DropdownMenu. Renders a router-link when `to` is set, otherwise a button.
 * Selecting an item closes the menu.
 */
interface Props {
  to?: RouteLocationRaw
  icon?: Component
  variant?: 'default' | 'danger'
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
})

const emit = defineEmits<{
  (e: 'select', event: MouseEvent): void
}>()

const closeMenu = inject(DROPDOWN_CLOSE_KEY, () => {})

function handleClick(event: MouseEvent) {
  emit('select', event)
  closeMenu()
}

const baseClasses =
  'flex w-full cursor-pointer items-center gap-2 rounded-xl px-3 py-2 text-left transition-colors focus-visible:outline-none'
const variantClasses = {
  default:
    'text-slate-700 hover:bg-slate-100 focus-visible:bg-slate-100 dark:text-slate-200 dark:hover:bg-white/10 dark:focus-visible:bg-white/10',
  danger:
    'text-rose-600 hover:bg-rose-50 focus-visible:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/40 dark:focus-visible:bg-rose-950/40',
} as const
</script>

<template>
  <router-link
    v-if="props.to"
    :to="props.to"
    role="menuitem"
    :class="[baseClasses, variantClasses[variant]]"
    @click="handleClick"
  >
    <component :is="icon" v-if="icon" class="size-4 shrink-0" aria-hidden="true" />
    <slot />
  </router-link>
  <button v-else type="button" role="menuitem" :class="[baseClasses, variantClasses[variant]]" @click="handleClick">
    <component :is="icon" v-if="icon" class="size-4 shrink-0" aria-hidden="true" />
    <slot />
  </button>
</template>
