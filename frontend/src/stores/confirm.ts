import { defineStore } from 'pinia'
import { ref } from 'vue'

export interface ConfirmOptions {
  message: string
  title?: string
  confirmText?: string
  cancelText?: string
  variant?: 'danger' | 'primary'
}

/**
 * Backing store for the app-wide confirmation dialog rendered by `ConfirmHost`.
 * Use it through the `useConfirm()` composable instead of `window.confirm()`.
 */
export const useConfirmStore = defineStore('confirm', () => {
  const isOpen = ref(false)
  const options = ref<ConfirmOptions>({ message: '' })
  let resolver: ((result: boolean) => void) | null = null

  /** Opens the dialog and resolves to true (confirmed) or false (cancelled/dismissed). */
  function confirm(next: ConfirmOptions): Promise<boolean> {
    resolver?.(false)
    options.value = next
    isOpen.value = true
    return new Promise<boolean>((resolve) => {
      resolver = resolve
    })
  }

  /** Closes the dialog and resolves the pending promise; later calls are no-ops. */
  function settle(result: boolean) {
    isOpen.value = false
    const resolve = resolver
    resolver = null
    resolve?.(result)
  }

  return { isOpen, options, confirm, settle }
})
