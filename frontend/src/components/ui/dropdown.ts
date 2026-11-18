import type { InjectionKey } from 'vue'

/** Provided by DropdownMenu so items can close the menu after selection. */
export const DROPDOWN_CLOSE_KEY: InjectionKey<() => void> = Symbol('dropdown-close')
