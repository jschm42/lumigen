/**
 * Shared class maps for form controls (Input, Select, Textarea) and field labels,
 * so every control renders with identical sizing, borders and focus states.
 */

export type ControlSize = 'sm' | 'md'

/** Size-dependent padding, radius and font size. `sm` is the dense variant for toolbars and grids. */
export const controlSizeClasses: Record<ControlSize, string> = {
  sm: 'rounded-lg px-2.5 py-1.5 text-xs',
  md: 'rounded-xl px-3.5 py-2 text-sm',
}

/** Base look shared by every text-like control. */
export const controlBaseClasses =
  'w-full border bg-white/70 text-slate-900 placeholder-slate-400 transition-colors duration-150 ' +
  'focus:outline-none focus:ring-2 focus:ring-sky-500/40 focus:border-sky-500 ' +
  'dark:bg-slate-900/70 dark:text-slate-100 dark:placeholder-slate-500 ' +
  'disabled:cursor-not-allowed disabled:opacity-50'

/** Border colours for the normal and invalid state. */
export function controlStateClasses(invalid: boolean): string {
  return invalid
    ? 'border-rose-500 focus:ring-rose-500/40 focus:border-rose-500'
    : 'border-slate-300/80 hover:border-slate-400 dark:border-white/10 dark:hover:border-white/20'
}

/** Overline label used above every form control. */
export const fieldLabelClasses =
  'block text-2xs font-semibold uppercase tracking-wider text-slate-500 dark:text-slate-400'
