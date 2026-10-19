import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export type ThemeMode = 'light' | 'dark' | 'system'

export const useThemeStore = defineStore('theme', () => {
  const mode = ref<ThemeMode>(
    (localStorage.getItem('lumigen_theme') as ThemeMode) || 'dark'
  )

  const isDark = ref<boolean>(true)

  function applyTheme() {
    let effectiveDark = true
    if (mode.value === 'system') {
      effectiveDark = window.matchMedia('(prefers-color-scheme: dark)').matches
    } else {
      effectiveDark = mode.value === 'dark'
    }

    isDark.value = effectiveDark
    const root = document.documentElement
    if (effectiveDark) {
      root.classList.add('dark')
      root.style.colorScheme = 'dark'
    } else {
      root.classList.remove('dark')
      root.style.colorScheme = 'light'
    }
  }

  function setMode(newMode: ThemeMode) {
    mode.value = newMode
    localStorage.setItem('lumigen_theme', newMode)
    applyTheme()
  }

  function toggle() {
    if (isDark.value) {
      setMode('light')
    } else {
      setMode('dark')
    }
  }

  // Initial apply
  applyTheme()

  // Listen to system changes
  if (typeof window !== 'undefined') {
    window
      .matchMedia('(prefers-color-scheme: dark)')
      .addEventListener('change', () => {
        if (mode.value === 'system') {
          applyTheme()
        }
      })
  }

  watch(mode, () => {
    applyTheme()
  })

  return {
    mode,
    isDark,
    setMode,
    toggle,
    applyTheme,
  }
})
