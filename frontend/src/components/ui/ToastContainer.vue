<script setup lang="ts">
import { useToastStore } from '@/stores/toast'
import ToastItem from './Toast.vue'

const toastStore = useToastStore()
</script>

<template>
  <div class="fixed bottom-4 right-4 z-50 flex flex-col gap-2 pointer-events-none max-w-sm w-full">
    <TransitionGroup
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="opacity-0 translate-y-4 scale-95"
      enter-to-class="opacity-100 translate-y-0 scale-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100 scale-100"
      leave-to-class="opacity-0 scale-95"
    >
      <ToastItem
        v-for="toast in toastStore.toasts"
        :key="toast.id"
        :toast="toast"
        @dismiss="toastStore.dismiss"
      />
    </TransitionGroup>
  </div>
</template>
