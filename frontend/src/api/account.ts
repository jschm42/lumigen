import apiClient from './client'
import type { User } from '@/types'

export interface AccountUpdatePayload {
  username?: string
  email?: string | null
  display_name?: string | null
}

export const accountApi = {
  async getAccount(): Promise<User> {
    const res = await apiClient.get<User>('/api/account')
    return res.data
  },

  async updateAccount(payload: AccountUpdatePayload): Promise<User> {
    const res = await apiClient.patch<User>('/api/account', payload)
    return res.data
  },

  async changePassword(currentPassword: string, newPassword: string): Promise<{ success: boolean }> {
    const res = await apiClient.post('/api/account/password', {
      current_password: currentPassword,
      new_password: newPassword,
    })
    return res.data
  },
}
