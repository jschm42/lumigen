import apiClient from './client'
import type { ChatSession, Generation } from '@/types'

export interface SessionListResponse {
  sessions: ChatSession[]
  total: number
}

export const sessionsApi = {
  async listSessions(params?: { q?: string; page?: number; page_size?: number }): Promise<SessionListResponse> {
    const res = await apiClient.get<SessionListResponse>('/api/sessions', { params })
    return res.data
  },

  async getSessionHistory(sessionToken: string): Promise<{ session: ChatSession; generations: Generation[] }> {
    const res = await apiClient.get(`/api/sessions/${sessionToken}`)
    return res.data
  },

  async renameSession(sessionToken: string, title: string): Promise<{ success: boolean; session: ChatSession }> {
    const res = await apiClient.patch(`/api/sessions/${sessionToken}/rename`, { title })
    return res.data
  },

  async deleteSession(sessionToken: string): Promise<{ success: boolean }> {
    const res = await apiClient.delete(`/api/sessions/${sessionToken}`)
    return res.data
  },

  async togglePin(sessionToken: string): Promise<{ success: boolean; is_pinned: boolean }> {
    const res = await apiClient.post(`/api/sessions/${sessionToken}/pin`)
    return res.data
  },
}
