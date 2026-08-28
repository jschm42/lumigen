export interface User {
  id: number
  username: string
  role: 'admin' | 'user'
  created_at?: string
}

export interface ModelConfig {
  id: number
  name: string
  provider: 'openai' | 'fal' | 'bfl' | 'openrouter' | 'google' | string
  model_identifier: string
  is_active: boolean
  is_default: boolean
  supported_aspect_ratios: string[]
  supported_resolutions: string[]
  generic_params?: Record<string, any>
  fal_params?: Record<string, any>
  capabilities?: string[]
}

export interface Profile {
  id: number
  name: string
  description?: string
  system_prompt?: string
  negative_prompt?: string
  default_aspect_ratio?: string
  default_resolution?: string
  default_model_config_id?: number | null
  upscale_provider?: string | null
  upscale_model?: string | null
  upscale_factor?: number | null
  generic_params?: Record<string, any>
  category_ids?: number[]
  created_at?: string
}

export interface Category {
  id: number
  name: string
  color?: string
}

export interface AssetMetadata {
  prompt?: string
  negative_prompt?: string
  seed?: number | string
  width?: number
  height?: number
  aspect_ratio?: string
  resolution?: string
  provider?: string
  model?: string
  steps?: number
  cfg_scale?: number
  sampler?: string
  generation_time_ms?: number
  created_at?: string
  [key: string]: any
}

export interface Asset {
  id: number
  slug: string
  prompt: string
  negative_prompt?: string
  seed?: number | string
  aspect_ratio: string
  resolution?: string
  provider: string
  model: string
  generation_id?: number
  created_at: string
  is_favorite: boolean
  rating: number
  thumbnail_url: string
  image_url: string
  download_url: string
  metadata?: AssetMetadata
  categories?: Category[]
  category_ids?: number[]
}

export interface Generation {
  id: number
  status: 'pending' | 'processing' | 'succeeded' | 'failed' | 'cancelled'
  progress?: number
  error_message?: string | null
  prompt: string
  negative_prompt?: string
  session_token?: string
  created_at: string
  completed_at?: string | null
  model_name?: string
  provider?: string
  aspect_ratio?: string
  resolution?: string
  seed?: number | string
  assets: Asset[]
}

export interface ChatSession {
  id: number
  session_token: string
  title: string
  created_at: string
  updated_at?: string
  cover_asset_id?: number | null
  cover_asset_url?: string | null
  generation_count?: number
  asset_count?: number
  last_llm_model?: string | null
  last_model_config_id?: number | null
  is_pinned?: boolean
}

export interface StylePreset {
  id: string | number
  name: string
  description?: string
  prompt_template: string
  negative_prompt?: string
  image_url?: string
  is_custom?: boolean
  category?: string
}

export interface ProviderApiKeyStatus {
  provider: string
  display_name: string
  has_key: boolean
  is_encrypted?: boolean
  status?: 'ok' | 'error' | 'unconfigured'
  message?: string
}

export interface Toast {
  id: string
  type: 'success' | 'error' | 'info' | 'warning'
  title?: string
  message: string
  duration?: number
}

export interface GalleryFilterState {
  q: string
  profile_name: string
  provider: string
  min_rating: number | null
  unrated: boolean
  time_preset: string
  date_from: string
  date_to: string
  category_ids: number[]
  thumb_size: 'sm' | 'md' | 'lg'
  artbook_token?: string
}
