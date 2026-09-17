import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'
import type { User } from '@/types'

declare const __APP_VERSION__: string | undefined

export const useAuthStore = defineStore('auth', () => {
  const defaultVersion = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : '0.4.0-beta'
  const user = ref<User | null>(null)
  const isAuthenticated = ref<boolean>(false)
  const needsOnboarding = ref<boolean>(false)
  const isLoading = ref<boolean>(true)
  const appVersion = ref<string>(defaultVersion)

  const isAdmin = computed(() => user.value?.role === 'admin')

  async function checkAuth() {
    isLoading.value = true
    try {
      const status = await authApi.getStatus()
      isAuthenticated.value = status.authenticated
      user.value = status.user
      needsOnboarding.value = status.needs_onboarding
      appVersion.value = status.app_version || defaultVersion
    } catch (_error) {
      isAuthenticated.value = false
      user.value = null
    } finally {
      isLoading.value = false
    }
  }

  async function login(formData: FormData | Record<string, string>) {
    const res = await authApi.login(formData)
    if (res.success && res.user) {
      user.value = res.user
      isAuthenticated.value = true
      needsOnboarding.value = false
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

  return {
    user,
    isAuthenticated,
    needsOnboarding,
    isLoading,
    appVersion,
    isAdmin,
    checkAuth,
    login,
    logout,
    setupAdmin,
  }
})
