import { useConfirmStore, type ConfirmOptions } from '@/stores/confirm'

/**
 * Returns a promise-based replacement for `window.confirm()` that renders the
 * app's ConfirmDialog.
 *
 * @example
 * const confirm = useConfirm()
 * if (!(await confirm({ message: 'Delete this item?', confirmText: 'Delete' }))) return
 */
export function useConfirm() {
  const store = useConfirmStore()
  return (options: ConfirmOptions | string) =>
    store.confirm(typeof options === 'string' ? { message: options } : options)
}
