import apiClient from './client'
import type { DiscoveredUpscaleModel, ModelConfig, ProviderApiKeyStatus, StylePreset, UpscaleModel, User } from '@/types'

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

  async generateStylePreview(
    styleId: string | number,
    prompt?: string,
    modelConfigId?: number,
  ): Promise<{ job_id: number; model_name?: string }> {
    const res = await apiClient.post(`/api/admin/styles/${styleId}/generate-preview`, {
      prompt,
      model_config_id: modelConfigId,
    })
    return res.data
  },

  async generateMissingStylePreviews(
    modelConfigId?: number,
  ): Promise<{ success: boolean; count: number; job_ids: number[]; model_name?: string; message?: string }> {
    const res = await apiClient.post('/api/admin/styles/generate-missing-previews', {
      model_config_id: modelConfigId,
    })
    return res.data
  },

  async getStylePreviewSettings(): Promise<{
    model_config_id: number | null
    models: { id: number; name: string; provider: string; model: string }[]
  }> {
    const res = await apiClient.get('/api/admin/styles/preview-settings')
    return res.data
  },

  async updateStylePreviewSettings(
    modelConfigId: number,
  ): Promise<{ success: boolean; model_config_id: number; name: string }> {
    const res = await apiClient.post('/api/admin/styles/preview-settings', {
      model_config_id: modelConfigId,
    })
    return res.data
  },

  async restoreDefaultStyles(): Promise<{
    success: boolean
    message: string
    created: number
    updated: number
    total: number
  }> {
    const res = await apiClient.post('/api/admin/styles/restore-defaults')
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

  async listUpscaleModels(): Promise<UpscaleModel[]> {
    const res = await apiClient.get<UpscaleModel[]>('/api/admin/upscale-models')
    return res.data
  },

  async saveUpscaleModel(data: Partial<UpscaleModel>): Promise<UpscaleModel> {
    if (data.id) {
      const res = await apiClient.put<UpscaleModel>(`/api/admin/upscale-models/${data.id}`, data)
      return res.data
    }
    const res = await apiClient.post<UpscaleModel>('/api/admin/upscale-models', data)
    return res.data
  },

  async deleteUpscaleModel(id: number): Promise<{ success: boolean }> {
    const res = await apiClient.delete(`/api/admin/upscale-models/${id}`)
    return res.data
  },

  async toggleUpscaleModel(id: number): Promise<{ id: number; is_enabled: boolean }> {
    const res = await apiClient.post(`/api/admin/upscale-models/${id}/toggle`)
    return res.data
  },

  async setDefaultUpscaleModel(id: number): Promise<{ id: number; is_default: boolean }> {
    const res = await apiClient.post(`/api/admin/upscale-models/${id}/set-default`)
    return res.data
  },

  async discoverUpscaleModels(): Promise<{ models: DiscoveredUpscaleModel[]; count: number }> {
    const res = await apiClient.get('/api/admin/upscale/discover-models')
    return res.data
  },
}
