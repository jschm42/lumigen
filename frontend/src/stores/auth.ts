import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi, type LoginPayload } from '@/api/auth'
import type { UiSettings, User } from '@/types'

declare const __APP_VERSION__: string | undefined

const DEFAULT_UI_SETTINGS: UiSettings = {
  show_token_usage: false,
}

export const useAuthStore = defineStore('auth', () => {
  const defaultVersion = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '0.4.0-beta'
  const user = ref<User | null>(null)
  const isAuthenticated = ref<boolean>(false)
  const needsOnboarding = ref<boolean>(false)
  const isLoading = ref<boolean>(true)
  const appVersion = ref<string>(defaultVersion)
  const uiSettings = ref<UiSettings>({ ...DEFAULT_UI_SETTINGS })
  const passwordMinLength = ref<number>(8)

  const isAdmin = computed(() => user.value?.role === 'admin')
  const displayName = computed(() => user.value?.display_name || user.value?.username || '')
  const initials = computed(() => {
    const source = displayName.value.trim()
    if (!source) return '?'
    const parts = source.split(/\s+/).filter(Boolean)
    const letters = parts.length > 1 ? parts[0][0] + parts[parts.length - 1][0] : source.slice(0, 1)
    return letters.toUpperCase()
  })

  async function checkAuth() {
    isLoading.value = true
    try {
      const status = await authApi.getStatus()
      isAuthenticated.value = status.authenticated
      user.value = status.user
      needsOnboarding.value = status.needs_onboarding
      appVersion.value = status.app_version || defaultVersion
      uiSettings.value = { ...DEFAULT_UI_SETTINGS, ...(status.ui_settings || {}) }
      passwordMinLength.value = status.password_min_length || 8
    } catch (_error) {
      isAuthenticated.value = false
      user.value = null
    } finally {
      isLoading.value = false
    }
  }

  async function login(formData: FormData | LoginPayload | Record<string, any>) {
    const res = await authApi.login(formData)
    if (res.success && res.user) {
      user.value = res.user
      isAuthenticated.value = true
      needsOnboarding.value = false
      // Refresh studio-wide UI settings, which are only exposed to signed-in users.
      checkAuth()
    }
    return res
  }

  async function logout() {
    try {
      await authApi.logout()
    } finally {
      user.value = null
      isAuthenticated.value = false
      window.location.href = '/login'
    }
  }

  async function setupAdmin(data: Record<string, string>) {
    const res = await authApi.setupAdmin(data)
    if (res.success && res.user) {
      user.value = res.user
      isAuthenticated.value = true
      needsOnboarding.value = false
    }
    return res
  }

  function setUser(updated: User) {
    user.value = updated
  }

  function setUiSettings(settings: Partial<UiSettings>) {
    uiSettings.value = { ...uiSettings.value, ...settings }
  }

  return {
    user,
    isAuthenticated,
    needsOnboarding,
    isLoading,
    appVersion,
    uiSettings,
    passwordMinLength,
    isAdmin,
    displayName,
    initials,
    checkAuth,
    login,
    logout,
    setupAdmin,
    setUser,
    setUiSettings,
  }
})
