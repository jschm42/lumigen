import apiClient from './client'
import type { Generation, ModelConfig, StylePreset } from '@/types'

export interface SubmitGenerationPayload {
  prompt: string
  negative_prompt?: string
  profile_id?: number | null
  model_config_id?: number | null
  aspect_ratio?: string
  resolution?: string
  seed?: number | string | null
  session_token?: string
  input_images?: File[]
  style_id?: string | number | null
  fal_params?: Record<string, any>
  generic_params?: Record<string, any>
}

export interface EnhancePromptPayload {
  prompt: string
  llm_model?: string
  profile_id?: number | null
  image?: File
}

export interface ExpandPayload {
  asset_id: number
  prompt: string
  aspect_ratio: string
  expand_left?: number
  expand_right?: number
  expand_top?: number
  expand_bottom?: number
}

export const generationApi = {
  async submitGeneration(payload: SubmitGenerationPayload): Promise<{ job_id: number; status: string }> {
    const formData = new FormData()
    formData.append('prompt', payload.prompt)
    if (payload.negative_prompt) formData.append('negative_prompt', payload.negative_prompt)
    if (payload.profile_id != null) formData.append('profile_id', String(payload.profile_id))
    if (payload.model_config_id != null) formData.append('model_config_id', String(payload.model_config_id))
    if (payload.aspect_ratio) formData.append('aspect_ratio', payload.aspect_ratio)
    if (payload.resolution) formData.append('resolution', payload.resolution)
    if (payload.seed !== undefined && payload.seed !== null && payload.seed !== '') {
      formData.append('seed', String(payload.seed))
    }
    if (payload.session_token) formData.append('conversation', payload.session_token)
    if (payload.style_id) formData.append('style_id', String(payload.style_id))
    if (payload.fal_params) formData.append('fal_params_json', JSON.stringify(payload.fal_params))
    if (payload.generic_params) formData.append('generic_params_json', JSON.stringify(payload.generic_params))

    if (payload.input_images && payload.input_images.length > 0) {
      payload.input_images.forEach((file) => {
        formData.append('images', file)
      })
    }

    const res = await apiClient.post('/api/generate', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  async getJobStatus(jobId: number): Promise<Generation> {
    const res = await apiClient.get<Generation>(`/api/jobs/${jobId}/status`)
    return res.data
  },

  async cancelJob(jobId: number): Promise<{ success: boolean }> {
    const res = await apiClient.post(`/api/jobs/${jobId}/cancel`)
    return res.data
  },

  async upscale(assetId: number, options?: { provider?: string; model?: string; factor?: number }): Promise<{ job_id: number; status: string }> {
    const res = await apiClient.post(`/api/assets/${assetId}/upscale`, options || {})
    return res.data
  },

  async enhancePrompt(payload: EnhancePromptPayload): Promise<{ enhanced_prompt: string; diff?: string }> {
    const formData = new FormData()
    formData.append('prompt', payload.prompt)
    if (payload.llm_model) formData.append('llm_model', payload.llm_model)
    if (payload.profile_id != null) formData.append('profile_id', String(payload.profile_id))
    if (payload.image) formData.append('image', payload.image)

    const res = await apiClient.post('/api/enhance-prompt', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })
    return res.data
  },

  async expandImage(payload: ExpandPayload): Promise<{ job_id: number; status: string }> {
    const res = await apiClient.post(`/api/assets/${payload.asset_id}/expand`, payload)
    return res.data
  },

  async getActiveModelConfigs(): Promise<ModelConfig[]> {
    const res = await apiClient.get<ModelConfig[]>('/api/models/active')
    return res.data
  },

  async getStyles(): Promise<StylePreset[]> {
    const res = await apiClient.get<StylePreset[]>('/api/styles')
    return res.data
  },
}
