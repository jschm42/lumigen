import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Toast } from '@/types'

export const useToastStore = defineStore('toast', () => {
  const toasts = ref<Toast[]>([])

  function show(toast: Omit<Toast, 'id'>) {
    const id = Math.random().toString(36).substring(2, 9)
    const newToast: Toast = {
      ...toast,
      id,
      duration: toast.duration ?? 4000,
    }
    toasts.value.push(newToast)

    if (newToast.duration && newToast.duration > 0) {
      setTimeout(() => {
        dismiss(id)
      }, newToast.duration)
    }
    return id
  }

  function success(message: string, title?: string) {
    return show({ type: 'success', message, title })
  }

  function error(message: string, title?: string) {
    return show({ type: 'error', message, title, duration: 6000 })
  }

  function info(message: string, title?: string) {
    return show({ type: 'info', message, title })
  }

  function warning(message: string, title?: string) {
    return show({ type: 'warning', message, title })
  }

  function dismiss(id: string) {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  return {
    toasts,
    show,
    success,
    error,
    info,
    warning,
    dismiss,
  }
})
