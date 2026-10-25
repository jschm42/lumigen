export interface User {
  id: number
  username: string
  role: 'admin' | 'user'
  email?: string | null
  display_name?: string | null
  is_active?: boolean
  created_at?: string | null
  last_login_at?: string | null
}

export interface UiSettings {
  show_token_usage: boolean
  /** ISO 4217 currency for configured model prices, e.g. "USD" or "EUR". */
  cost_currency: string
}

export interface TokenUsage {
  input_tokens: number | null
  output_tokens: number | null
  total_tokens: number | null
  /** Only set when prices are configured for the model. */
  cost: number | null
  /** ISO 4217 code, or "mixed" for totals across different currencies. */
  currency: string | null
}

export interface ModelConfig {
  id: number
  name: string
  provider: 'openai' | 'fal' | 'bfl' | 'openrouter' | 'google' | string
  model_identifier: string
  /** Media kind produced by the model; "video" models render MP4 clips. */
  media_type?: 'image' | 'video'
  is_active: boolean
  is_default: boolean
  supported_aspect_ratios: string[]
  supported_resolutions: string[]
  generic_params?: Record<string, any>
  fal_params?: Record<string, any>
  capabilities?: string[]
  /** Optional price per one million input tokens (studio currency). */
  price_input_per_mtok?: number | null
  /** Optional price per one million output tokens (studio currency). */
  price_output_per_mtok?: number | null
  /** Optional price per generated image (studio currency). */
  price_per_image?: number | null
}

export interface Profile {
  id: number
  name: string
  description?: string
  system_prompt?: string
  negative_prompt?: string
  width?: number | null
  height?: number | null
  aspect_ratio?: string | null
  default_aspect_ratio?: string
  resolution?: string
  default_resolution?: string
  default_model_config_id?: number | null
  n_images?: number | null
  seed?: number | null
  upscale_provider?: string | null
  upscale_model?: string | null
  upscale_topaz_model_id?: number | null
  upscale_factor?: number | null
  fal_aspect_ratio?: string
  fal_resolution?: string
  openrouter_aspect_ratio?: string
  openrouter_image_size?: string
  google_aspect_ratio?: string
  google_resolution?: string
  params_json?: Record<string, any>
  generic_params?: Record<string, any>
  category_ids?: number[]
  categories?: { id: number; name: string }[]
  created_at?: string
}


export interface Category {
  id: number
  name: string
  color?: string
  asset_count?: number
  profile_count?: number
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
  width?: number
  height?: number
  mime?: string
  metadata?: AssetMetadata
  categories?: Category[]
  category_ids?: number[]
  stack_id?: string | null
  stack_order?: number
  stack_count?: number
  stack_items?: Asset[]
}

export interface Generation {
  id: number
  status: 'queued' | 'running' | 'pending' | 'processing' | 'succeeded' | 'failed' | 'cancelled'
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
  n_images?: number | null
  profile_name?: string | null
  duration_seconds?: number | null
  usage?: TokenUsage | null
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
  homepage_url?: string
  has_key: boolean
  /** Media kinds the provider can produce, e.g. ["image", "video"]. */
  media_types?: string[]
  supports_video?: boolean
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
  model?: string
  thumb_size: 'sm' | 'md' | 'lg'
  thumb_fit?: 'cover' | 'contain'
  group_by_date?: boolean
  artbook_token?: string
  collapse_stacks?: boolean
}

export type GalleryPresetFilters = Partial<
  Pick<
    GalleryFilterState,
    | 'q'
    | 'min_rating'
    | 'unrated'
    | 'time_preset'
    | 'date_from'
    | 'date_to'
    | 'category_ids'
    | 'profile_name'
    | 'provider'
    | 'model'
    | 'collapse_stacks'
  >
>

export interface GalleryPreset {
  id: string
  name: string
  filters: GalleryPresetFilters
}

export interface UpscaleModel {
  id?: number
  name: string
  model_identifier: string
  params_json?: Record<string, any>
  is_enabled: boolean
  is_default: boolean
  created_at?: string
  updated_at?: string
}

export interface DiscoveredUpscaleModel {
  endpoint_id: string
  name: string
  description?: string
  category?: string
}
