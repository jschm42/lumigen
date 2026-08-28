import { defineStore } from 'pinia'
import { ref } from 'vue'
import { sessionsApi } from '@/api/sessions'
import type { ChatSession } from '@/types'

export const useSessionsStore = defineStore('sessions', () => {
  const sessions = ref<ChatSession[]>([])
  const activeSessionToken = ref<string>('')
  const activeSession = ref<ChatSession | null>(null)
  const searchQuery = ref<string>('')
  const isLoading = ref<boolean>(false)

  async function fetchSessions() {
    isLoading.value = true
    try {
      const res = await sessionsApi.listSessions({ q: searchQuery.value })
      sessions.value = res.sessions
      if (activeSessionToken.value) {
        activeSession.value = sessions.value.find((s) => s.session_token === activeSessionToken.value) || null
      }
    } catch (_error) {
      // ignore
    } finally {
      isLoading.value = false
    }
  }

  function setActiveSessionToken(token: string) {
    activeSessionToken.value = token
    activeSession.value = sessions.value.find((s) => s.session_token === token) || null
  }

  function createNewSession() {
    activeSessionToken.value = ''
    activeSession.value = null
  }

  async function renameSession(token: string, newTitle: string) {
    const res = await sessionsApi.renameSession(token, newTitle)
    if (res.success) {
      const session = sessions.value.find((s) => s.session_token === token)
      if (session) session.title = newTitle
      if (activeSession.value && activeSession.value.session_token === token) {
        activeSession.value.title = newTitle
      }
    }
    return res
  }

  async function deleteSession(token: string) {
    const res = await sessionsApi.deleteSession(token)
    if (res.success) {
      sessions.value = sessions.value.filter((s) => s.session_token !== token)
      if (activeSessionToken.value === token) {
        createNewSession()
      }
    }
    return res
  }

  async function togglePin(token: string) {
    const res = await sessionsApi.togglePin(token)
    if (res.success) {
      const session = sessions.value.find((s) => s.session_token === token)
      if (session) session.is_pinned = res.is_pinned
    }
    return res
  }

  return {
    sessions,
    activeSessionToken,
    activeSession,
    searchQuery,
    isLoading,
    fetchSessions,
    setActiveSessionToken,
    createNewSession,
    renameSession,
    deleteSession,
    togglePin,
  }
})
