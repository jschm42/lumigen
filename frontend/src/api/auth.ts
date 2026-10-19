import apiClient from './client'
import type { UiSettings, User } from '@/types'

export interface AuthStatusResponse {
  authenticated: boolean
  user: User | null
  needs_onboarding: boolean
  app_version: string
  ui_settings?: Partial<UiSettings>
  password_min_length?: number
}

export interface LoginPayload {
  username: string
  password: string
  remember_me?: boolean
}

export const authApi = {
  async getStatus(): Promise<AuthStatusResponse> {
    const res = await apiClient.get<AuthStatusResponse>('/api/auth/status')
    return res.data
  },

  async login(formData: FormData | LoginPayload | Record<string, any>): Promise<{ success: boolean; user?: User; message?: string }> {
    const res = await apiClient.post('/api/auth/login', formData)
    return res.data
  },

  async logout(): Promise<{ success: boolean }> {
    const res = await apiClient.post('/api/auth/logout')
    return res.data
  },

  async setupAdmin(data: Record<string, string>): Promise<{ success: boolean; user?: User; message?: string }> {
    const res = await apiClient.post('/api/auth/setup', data)
    return res.data
  },

  async forgotPassword(identifier: string): Promise<{ success: boolean; message: string }> {
    const res = await apiClient.post('/api/auth/password/forgot', { identifier })
    return res.data
  },

  async validateResetToken(token: string): Promise<{ valid: boolean }> {
    const res = await apiClient.post('/api/auth/password/validate-token', { token })
    return res.data
  },

  async resetPassword(token: string, newPassword: string): Promise<{ success: boolean }> {
    const res = await apiClient.post('/api/auth/password/reset', { token, new_password: newPassword })
    return res.data
  },
}
