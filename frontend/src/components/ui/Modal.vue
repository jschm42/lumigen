<script setup lang="ts">
import { computed, onMounted, onUnmounted, watch } from 'vue'

interface Props {
  open: boolean
  title?: string
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'full'
  persistent?: boolean
  hideCloseButton?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  open: false,
  size: 'md',
  persistent: false,
  hideCloseButton: false,
})

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'close'): void
}>()

const sizeClasses = computed(() => {
  switch (props.size) {
    case 'sm':
      return 'max-w-md'
    case 'lg':
      return 'max-w-3xl'
    case 'xl':
      return 'max-w-5xl'
    case '2xl':
      return 'max-w-7xl'
    case 'full':
      return 'max-w-[96vw] h-[92vh]'
    case 'md':
    default:
      return 'max-w-xl'
  }
})

function close() {
  emit('update:open', false)
  emit('close')
}

function handleBackdropClick() {
  if (!props.persistent) {
    close()
  }
}

function handleKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape' && props.open && !props.persistent) {
    close()
  }
}

watch(() => props.open, (isOpen) => {
  if (isOpen) {
    document.body.style.overflow = 'hidden'
  } else {
    document.body.style.overflow = ''
  }
})

onMounted(() => {
  window.addEventListener('keydown', handleKeydown)
})

onUnmounted(() => {
  window.removeEventListener('keydown', handleKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <Teleport to="body">
    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="open"
        class="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 overflow-y-auto bg-slate-950/70 backdrop-blur-sm"
        @click="handleBackdropClick"
      >
        <Transition
          enter-active-class="transition duration-200 ease-out"
          enter-from-class="opacity-0 scale-95 translate-y-2"
          enter-to-class="opacity-100 scale-100 translate-y-0"
          leave-active-class="transition duration-150 ease-in"
          leave-from-class="opacity-100 scale-100 translate-y-0"
          leave-to-class="opacity-0 scale-95 translate-y-2"
        >
          <div
            v-if="open"
            :class="[
              'relative w-full rounded-2xl bg-white text-slate-900 shadow-2xl dark:bg-slate-900 dark:text-slate-100 border border-slate-300/80 dark:border-white/10 overflow-hidden flex flex-col my-auto max-h-[92vh]',
              sizeClasses,
            ]"
            @click.stop
          >
            <!-- Header -->
            <div v-if="title || $slots.header" class="flex items-center justify-between px-6 py-4 border-b border-slate-200 dark:border-white/10 shrink-0">
              <slot name="header">
                <h3 class="text-lg font-semibold tracking-tight text-slate-900 dark:text-white">
                  {{ title }}
                </h3>
              </slot>
              <button
                v-if="!hideCloseButton"
                type="button"
                @click="close"
                class="rounded-xl p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700 dark:hover:bg-white/10 dark:hover:text-slate-200 transition-colors"
              >
                <svg class="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            <!-- Body -->
            <div class="p-6 overflow-y-auto flex-1">
              <slot />
            </div>

            <!-- Footer -->
            <div v-if="$slots.footer" class="flex items-center justify-end gap-3 px-6 py-4 border-t border-slate-200 dark:border-white/10 bg-slate-50/50 dark:bg-slate-950/40 shrink-0">
              <slot name="footer" />
            </div>
          </div>
        </Transition>
      </div>
    </Transition>
  </Teleport>
</template>
