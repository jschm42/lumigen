import apiClient from './client'
import type { Asset, Category } from '@/types'

export interface AssetListResponse {
  assets: Asset[]
  total: number
  page: number
  total_pages: number
}

export interface GalleryFilterParams {
  q?: string
  profile_name?: string
  provider?: string
  min_rating?: number | null
  unrated?: boolean
  time_preset?: string
  date_from?: string
  date_to?: string
  category_ids?: number[]
  artbook_token?: string
  page?: number
  page_size?: number
}

export const galleryApi = {
  async listAssets(params: GalleryFilterParams): Promise<AssetListResponse> {
    const res = await apiClient.get<AssetListResponse>('/api/assets', {
      params: {
        ...params,
        category_ids: params.category_ids?.join(','),
      },
    })
    return res.data
  },

  async getAsset(id: number): Promise<Asset> {
    const res = await apiClient.get<Asset>(`/api/assets/${id}`)
    return res.data
  },

  async rateAsset(id: number, rating: number): Promise<{ success: boolean; rating: number }> {
    const res = await apiClient.post(`/api/assets/${id}/rate`, { rating })
    return res.data
  },

  async toggleFavorite(id: number): Promise<{ success: boolean; is_favorite: boolean }> {
    const res = await apiClient.post(`/api/assets/${id}/favorite`)
    return res.data
  },

  async updateCategories(id: number, categoryIds: number[]): Promise<{ success: boolean; categories: Category[] }> {
    const res = await apiClient.put(`/api/assets/${id}/categories`, { category_ids: categoryIds })
    return res.data
  },

  async deleteAsset(id: number): Promise<{ success: boolean }> {
    const res = await apiClient.delete(`/api/assets/${id}`)
    return res.data
  },

  async bulkDelete(assetIds: number[]): Promise<{ success: boolean; deleted_count: number }> {
    const res = await apiClient.post('/api/assets/bulk-delete', { asset_ids: assetIds })
    return res.data
  },

  async bulkCategorize(assetIds: number[], categoryIds: number[]): Promise<{ success: boolean }> {
    const res = await apiClient.post('/api/assets/bulk-categorize', {
      asset_ids: assetIds,
      category_ids: categoryIds,
    })
    return res.data
  },

  async listCategories(): Promise<Category[]> {
    const res = await apiClient.get<Category[]>('/api/categories')
    return res.data
  },

  async createCategory(name: string, color?: string): Promise<Category> {
    const res = await apiClient.post<Category>('/api/categories', { name, color })
    return res.data
  },
}
