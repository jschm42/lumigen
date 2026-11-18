<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, provide, ref, useId, watch } from 'vue'
import { DROPDOWN_CLOSE_KEY } from './dropdown'

/**
 * Popup menu anchored to a trigger. Closes on outside click, Escape and item
 * selection; Arrow keys move between `DropdownMenuItem`s.
 *
 * The `#trigger` slot receives `{ open, toggle, triggerAttrs }`; bind `triggerAttrs`
 * onto the trigger button for correct ARIA wiring.
 */
interface Props {
  align?: 'left' | 'right'
  /** Width utility for the menu panel. */
  widthClass?: string
}

withDefaults(defineProps<Props>(), {
  align: 'right',
  widthClass: 'w-56',
})

const isOpen = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const menuRef = ref<HTMLElement | null>(null)
const menuId = `menu-${useId()}`

function items(): HTMLElement[] {
  return Array.from(menuRef.value?.querySelectorAll<HTMLElement>('[role="menuitem"]') ?? [])
}

function close(returnFocus = false) {
  if (!isOpen.value) return
  isOpen.value = false
  if (returnFocus) {
    rootRef.value?.querySelector<HTMLElement>('[aria-haspopup="menu"]')?.focus()
  }
}

function toggle() {
  isOpen.value = !isOpen.value
}

function handleDocumentClick(event: MouseEvent) {
  // composedPath() survives re-renders of the clicked element.
  if (!event.composedPath().includes(rootRef.value as EventTarget)) close()
}

function handleKeydown(event: KeyboardEvent) {
  if (!isOpen.value) return
  if (event.key === 'Escape') {
    event.preventDefault()
    event.stopPropagation()
    close(true)
    return
  }
  if (event.key !== 'ArrowDown' && event.key !== 'ArrowUp') return
  event.preventDefault()
  const list = items()
  if (!list.length) return
  const current = list.indexOf(document.activeElement as HTMLElement)
  const delta = event.key === 'ArrowDown' ? 1 : -1
  list[(current + delta + list.length) % list.length].focus()
}

watch(isOpen, (open) => {
  if (open) {
    document.addEventListener('click', handleDocumentClick)
    nextTick(() => items()[0]?.focus({ preventScroll: true }))
  } else {
    document.removeEventListener('click', handleDocumentClick)
  }
})

onBeforeUnmount(() => document.removeEventListener('click', handleDocumentClick))

provide(DROPDOWN_CLOSE_KEY, () => close(false))

const triggerAttrs = computed(() => ({
  'aria-haspopup': 'menu' as const,
  'aria-expanded': isOpen.value,
  'aria-controls': menuId,
}))
</script>

<template>
  <div ref="rootRef" class="relative" @keydown="handleKeydown">
    <slot
      name="trigger"
      :open="isOpen"
      :toggle="toggle"
      :trigger-attrs="triggerAttrs"
    />
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0 -translate-y-1"
      leave-active-class="transition duration-100 ease-in"
      leave-to-class="opacity-0 -translate-y-1"
    >
      <div
        v-if="isOpen"
        :id="menuId"
        ref="menuRef"
        role="menu"
        :class="[
          'absolute z-50 mt-2 rounded-2xl border border-slate-200 bg-white/95 p-1.5 text-xs shadow-xl backdrop-blur-md dark:border-white/10 dark:bg-slate-900/95',
          align === 'right' ? 'right-0' : 'left-0',
          widthClass,
        ]"
      >
        <slot :close="() => close(false)" />
      </div>
    </Transition>
  </div>
</template>
