<script setup lang="ts">
import { ref, useId } from 'vue'
import { X } from 'lucide-vue-next'
import { useOverlay } from '@/composables/useOverlay'
import IconButton from './IconButton.vue'

// Attributes (e.g. data-testid) belong on the panel, not on the Teleport root.
defineOptions({ inheritAttrs: false })

/**
 * Side panel overlay (slide-over). Shares the overlay stack with Modal:
 * focus trap, focus return, scroll lock and top-most-only Escape.
 */
interface Props {
  open: boolean
  title?: string
  side?: 'left' | 'right'
  size?: 'md' | 'lg'
  persistent?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  side: 'right',
  size: 'md',
  persistent: false,
})

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'close'): void
}>()

const panelRef = ref<HTMLElement | null>(null)
const titleId = `drawer-title-${useId()}`

function close() {
  emit('update:open', false)
  emit('close')
}

useOverlay(() => props.open, {
  container: panelRef,
  onEscape: () => {
    if (!props.persistent) close()
  },
})

const sizeClasses = { md: 'max-w-md', lg: 'max-w-md sm:max-w-lg' } as const
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition-opacity duration-200 ease-out"
      enter-from-class="opacity-0"
      leave-active-class="transition-opacity duration-150 ease-in"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-50 bg-slate-950/60 backdrop-blur-sm"
        aria-hidden="true"
        @click="!persistent && close()"
      />
    </Transition>

    <Transition
      enter-active-class="transition-transform duration-300 ease-out"
      :enter-from-class="side === 'left' ? '-translate-x-full' : 'translate-x-full'"
      leave-active-class="transition-transform duration-200 ease-in"
      :leave-to-class="side === 'left' ? '-translate-x-full' : 'translate-x-full'"
    >
      <aside
        v-if="open"
        ref="panelRef"
        role="dialog"
        aria-modal="true"
        :aria-labelledby="title || $slots.header ? titleId : undefined"
        tabindex="-1"
        v-bind="$attrs"
        :class="[
          'fixed inset-y-0 z-50 flex w-full flex-col overflow-hidden bg-white text-slate-900 shadow-2xl outline-none dark:bg-slate-900 dark:text-slate-100',
          side === 'left' ? 'left-0 border-r' : 'right-0 border-l',
          'border-slate-200 dark:border-white/10',
          sizeClasses[size],
        ]"
      >
        <header
          v-if="title || $slots.header"
          class="flex shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-slate-50/80 px-5 py-4 dark:border-white/10 dark:bg-slate-950/50"
        >
          <div :id="titleId" class="min-w-0 flex-1">
            <slot name="header">
              <h2 class="text-sm font-semibold text-slate-900 dark:text-white">{{ title }}</h2>
            </slot>
          </div>
          <IconButton label="Close panel" @click="close">
            <X class="size-4" aria-hidden="true" />
          </IconButton>
        </header>

        <slot name="toolbar" />

        <div class="min-h-0 flex-1 overflow-y-auto">
          <slot />
        </div>

        <footer
          v-if="$slots.footer"
          class="shrink-0 border-t border-slate-200 bg-slate-50/50 px-5 py-3 dark:border-white/10 dark:bg-slate-950/40"
        >
          <slot name="footer" />
        </footer>
      </aside>
    </Transition>
  </Teleport>
</template>
