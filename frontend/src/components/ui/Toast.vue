<script setup lang="ts">
import { computed } from 'vue'
import type { Toast } from '@/types'

interface Props {
  toast: Toast
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'dismiss', id: string): void
}>()

const iconClasses = computed(() => {
  switch (props.toast.type) {
    case 'success':
      return 'text-emerald-500 bg-emerald-100 dark:bg-emerald-950/60'
    case 'error':
      return 'text-rose-500 bg-rose-100 dark:bg-rose-950/60'
    case 'warning':
      return 'text-amber-500 bg-amber-100 dark:bg-amber-950/60'
    case 'info':
    default:
      return 'text-sky-500 bg-sky-100 dark:bg-sky-950/60'
  }
})
</script>

<template>
  <div
    class="flex items-start gap-3 w-full max-w-sm rounded-2xl p-4 bg-white/95 shadow-xl border border-slate-200/80 backdrop-blur-md dark:bg-slate-900/95 dark:border-white/10 text-slate-900 dark:text-white pointer-events-auto transition-all"
  >
    <div :class="['w-8 h-8 rounded-xl flex items-center justify-center shrink-0 text-sm font-bold', iconClasses]">
      <span v-if="toast.type === 'success'">✓</span>
      <span v-else-if="toast.type === 'error'">✕</span>
      <span v-else-if="toast.type === 'warning'">!</span>
      <span v-else>ℹ</span>
    </div>

    <div class="flex-1 min-w-0 pt-0.5">
      <h5 v-if="toast.title" class="text-sm font-semibold leading-tight mb-0.5">
        {{ toast.title }}
      </h5>
      <p class="text-xs text-slate-600 dark:text-slate-300 leading-relaxed break-words">
        {{ toast.message }}
      </p>
    </div>

    <button
      type="button"
      @click="emit('dismiss', toast.id)"
      class="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded-lg p-1 transition-colors"
    >
      <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
      </svg>
    </button>
  </div>
</template>
