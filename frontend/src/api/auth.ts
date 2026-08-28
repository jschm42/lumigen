import apiClient from './client'
import type { User } from '@/types'

export interface AuthStatusResponse {
  authenticated: boolean
  user: User | null
  needs_onboarding: boolean
  app_version: string
}

export const authApi = {
  async getStatus(): Promise<AuthStatusResponse> {
    const res = await apiClient.get<AuthStatusResponse>('/api/auth/status')
    return res.data
  },

  async login(formData: FormData | Record<string, string>): Promise<{ success: boolean; user?: User; message?: string }> {
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
}
