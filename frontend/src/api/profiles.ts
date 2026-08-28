import apiClient from './client'
import type { Profile } from '@/types'

export const profilesApi = {
  async listProfiles(): Promise<Profile[]> {
    const res = await apiClient.get<Profile[]>('/api/profiles')
    return res.data
  },

  async getProfile(id: number): Promise<Profile> {
    const res = await apiClient.get<Profile>(`/api/profiles/${id}`)
    return res.data
  },

  async createProfile(data: Partial<Profile>): Promise<Profile> {
    const res = await apiClient.post<Profile>('/api/profiles', data)
    return res.data
  },

  async updateProfile(id: number, data: Partial<Profile>): Promise<Profile> {
    const res = await apiClient.put<Profile>(`/api/profiles/${id}`, data)
    return res.data
  },

  async deleteProfile(id: number): Promise<{ success: boolean }> {
    const res = await apiClient.delete(`/api/profiles/${id}`)
    return res.data
  },
}
