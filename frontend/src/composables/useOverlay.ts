import { nextTick, onBeforeUnmount, watch, type Ref } from 'vue'

/**
 * Shared overlay stack for modals, drawers and full-screen viewers.
 *
 * Only the top-most overlay reacts to Escape and traps Tab focus, the page
 * scroll lock is held while any overlay is open, and focus returns to the
 * element that was focused before an overlay opened.
 */

interface OverlayEntry {
  id: number
  container?: Ref<HTMLElement | null>
  onEscape?: () => void
  trapFocus: boolean
  returnFocusTo: HTMLElement | null
}

export interface UseOverlayOptions {
  /** Element that holds the overlay content; used for initial focus and the focus trap. */
  container?: Ref<HTMLElement | null>
  /** Called when Escape is pressed while this overlay is top-most. Omit to ignore Escape (persistent). */
  onEscape?: () => void
  /** Keep Tab / Shift+Tab focus inside the container (default: true). */
  trapFocus?: boolean
}

const FOCUSABLE_SELECTOR = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  'video[controls]',
  '[tabindex]:not([tabindex="-1"])',
  '[contenteditable="true"]',
].join(',')

const stack: OverlayEntry[] = []
let nextId = 1
let previousBodyOverflow = ''
let listenerAttached = false

function topEntry(): OverlayEntry | undefined {
  return stack[stack.length - 1]
}

function focusableElements(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)).filter(
    (el) => el.offsetParent !== null || el === document.activeElement,
  )
}

function handleTab(event: KeyboardEvent, container: HTMLElement) {
  const items = focusableElements(container)
  if (items.length === 0) {
    event.preventDefault()
    container.focus()
    return
  }
  const first = items[0]
  const last = items[items.length - 1]
  const active = document.activeElement as HTMLElement | null
  const outside = !active || !container.contains(active)

  if (event.shiftKey && (outside || active === first || active === container)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && (outside || active === last)) {
    event.preventDefault()
    first.focus()
  }
}

function handleKeydown(event: KeyboardEvent) {
  const top = topEntry()
  if (!top || event.defaultPrevented) return

  if (event.key === 'Escape') {
    event.preventDefault()
    top.onEscape?.()
    return
  }

  const container = top.container?.value
  if (event.key === 'Tab' && top.trapFocus && container) {
    handleTab(event, container)
  }
}

function lockScroll() {
  if (stack.length === 1) {
    previousBodyOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'
  }
}

function unlockScroll() {
  if (stack.length === 0) {
    document.body.style.overflow = previousBodyOverflow
    previousBodyOverflow = ''
  }
}

function ensureListener() {
  if (listenerAttached || typeof window === 'undefined') return
  window.addEventListener('keydown', handleKeydown)
  listenerAttached = true
}

/** Returns true while at least one overlay registered via `useOverlay` is open. */
export function hasOpenOverlay(): boolean {
  return stack.length > 0
}

/**
 * Registers an overlay in the shared stack while `isOpen` is true.
 *
 * @param isOpen Getter for the overlay's open state.
 * @param options Container element, Escape handler and focus-trap behaviour.
 * @returns `isTopmost()` – true when this overlay is open and no other overlay is above it.
 */
export function useOverlay(isOpen: () => boolean, options: UseOverlayOptions = {}) {
  let entry: OverlayEntry | null = null

  function open() {
    if (entry) return
    ensureListener()
    entry = {
      id: nextId++,
      container: options.container,
      onEscape: options.onEscape,
      trapFocus: options.trapFocus ?? true,
      returnFocusTo: document.activeElement instanceof HTMLElement ? document.activeElement : null,
    }
    stack.push(entry)
    lockScroll()

    const opened = entry
    nextTick(() => {
      const container = opened.container?.value
      if (!container || topEntry() !== opened || container.contains(document.activeElement)) return
      const preferred = container.querySelector<HTMLElement>('[autofocus], [data-autofocus]')
      ;(preferred ?? container).focus({ preventScroll: true })
    })
  }

  function close() {
    if (!entry) return
    const index = stack.indexOf(entry)
    if (index !== -1) stack.splice(index, 1)
    const returnTo = entry.returnFocusTo
    entry = null
    unlockScroll()
    if (returnTo && returnTo.isConnected) {
      returnTo.focus({ preventScroll: true })
    }
  }

  watch(isOpen, (value) => (value ? open() : close()), { immediate: true })
  onBeforeUnmount(close)

  return {
    isTopmost: () => entry !== null && topEntry() === entry,
  }
}
