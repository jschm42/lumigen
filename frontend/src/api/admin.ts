import apiClient from './client'
import type { ModelConfig, ProviderApiKeyStatus, StylePreset, User } from '@/types'

export interface SystemInfo {
  app_version: string
  app_name: string
  storage_dir: string
  storage_used_bytes: number
  storage_free_bytes: number
  total_assets: number
  total_generations: number
  python_version: string
}

export const adminApi = {
  async getProviderKeys(): Promise<ProviderApiKeyStatus[]> {
    const res = await apiClient.get<ProviderApiKeyStatus[]>('/api/admin/providers')
    return res.data
  },

  async updateProviderKey(provider: string, apiKey: string): Promise<{ success: boolean; message?: string }> {
    const res = await apiClient.post(`/api/admin/providers/${provider}`, { api_key: apiKey })
    return res.data
  },

  async deleteProviderKey(provider: string): Promise<{ success: boolean }> {
    const res = await apiClient.delete(`/api/admin/providers/${provider}`)
    return res.data
  },

  async testProvider(provider: string): Promise<{ success: boolean; message: string }> {
    const res = await apiClient.post(`/api/admin/providers/${provider}/test`)
    return res.data
  },

  async discoverModels(provider: string): Promise<{ models: string[]; count: number }> {
    const res = await apiClient.get(`/api/admin/providers/${provider}/discover-models`)
    return res.data
  },

  async listModelConfigs(): Promise<ModelConfig[]> {
    const res = await apiClient.get<ModelConfig[]>('/api/admin/models')
    return res.data
  },

  async saveModelConfig(data: Partial<ModelConfig>): Promise<ModelConfig> {
    if (data.id) {
      const res = await apiClient.put<ModelConfig>(`/api/admin/models/${data.id}`, data)
      return res.data
    }
    const res = await apiClient.post<ModelConfig>('/api/admin/models', data)
    return res.data
  },

  async deleteModelConfig(id: number): Promise<{ success: boolean }> {
    const res = await apiClient.delete(`/api/admin/models/${id}`)
    return res.data
  },

  async listStyles(): Promise<StylePreset[]> {
    const res = await apiClient.get<StylePreset[]>('/api/admin/styles')
    return res.data
  },

  async saveStyle(formData: FormData): Promise<StylePreset> {
    const res = await apiClient.post<StylePreset>('/api/admin/styles', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  async deleteStyle(styleId: string | number): Promise<{ success: boolean }> {
    const res = await apiClient.delete(`/api/admin/styles/${styleId}`)
    return res.data
  },

  async generateStylePreview(styleId: string | number, prompt?: string): Promise<{ job_id: number }> {
    const res = await apiClient.post(`/api/admin/styles/${styleId}/generate-preview`, { prompt })
    return res.data
  },

  async listUsers(): Promise<User[]> {
    const res = await apiClient.get<User[]>('/api/admin/users')
    return res.data
  },

  async createUser(data: { username: string; password: string; role: string }): Promise<User> {
    const res = await apiClient.post<User>('/api/admin/users', data)
    return res.data
  },

  async updateUserRole(userId: number, role: string): Promise<User> {
    const res = await apiClient.patch<User>(`/api/admin/users/${userId}/role`, { role })
    return res.data
  },

  async resetUserPassword(userId: number, password: string): Promise<{ success: boolean }> {
    const res = await apiClient.post(`/api/admin/users/${userId}/reset-password`, { password })
    return res.data
  },

  async deleteUser(userId: number): Promise<{ success: boolean }> {
    const res = await apiClient.delete(`/api/admin/users/${userId}`)
    return res.data
  },

  async getSystemInfo(): Promise<SystemInfo> {
    const res = await apiClient.get<SystemInfo>('/api/admin/system')
    return res.data
  },

  async importData(formData: FormData): Promise<{ success: boolean; imported: Record<string, number> }> {
    const res = await apiClient.post('/api/admin/import', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },
}
