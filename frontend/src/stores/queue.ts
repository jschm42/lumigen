import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { generationApi } from '@/api/generation'
import { useToastStore } from './toast'
import type { Generation } from '@/types'

export const useQueueStore = defineStore('queue', () => {
  const toastStore = useToastStore()

  const activeJobs = ref<Generation[]>([])
  const recentJobs = ref<Generation[]>([])
  const totalActive = ref<number>(0)
  const isOpen = ref<boolean>(false)
  const isLoading = ref<boolean>(false)
  const actionLoading = ref<Record<number, boolean>>({})

  let pollTimeout: any = null

  async function fetchQueue() {
    try {
      const data = await generationApi.getQueue()
      activeJobs.value = data.active || []
      recentJobs.value = data.recent || []
      totalActive.value = data.total_active || 0
    } catch (_err) {
      // Silently catch background poll errors
    } finally {
      scheduleNextPoll()
    }
  }

  function scheduleNextPoll() {
    clearTimeout(pollTimeout)
    // Poll every 2.5 seconds if there are active jobs or the queue dialog is open; otherwise every 10 seconds
    const interval = totalActive.value > 0 || isOpen.value ? 2500 : 10000
    pollTimeout = setTimeout(() => {
      fetchQueue()
    }, interval)
  }

  function openQueue() {
    isOpen.value = true
    fetchQueue()
  }

  function closeQueue() {
    isOpen.value = false
  }

  function toggleQueue() {
    if (isOpen.value) {
      closeQueue()
    } else {
      openQueue()
    }
  }

  async function cancelJob(jobId: number) {
    actionLoading.value[jobId] = true
    try {
      const res = await generationApi.cancelJob(jobId)
      if (res.success) {
        toastStore.info('Generation was cancelled.')
        await fetchQueue()
      } else {
        toastStore.warning(res.message || 'Could not be cancelled.')
      }
    } catch (err: any) {
      toastStore.error(err?.response?.data?.detail || 'Failed to cancel generation.')
    } finally {
      actionLoading.value[jobId] = false
    }
  }

  async function retryJob(jobId: number) {
    actionLoading.value[jobId] = true
    try {
      const res = await generationApi.retryJob(jobId)
      toastStore.success(`Generation #${res.job_id} queued again.`)
      await fetchQueue()
    } catch (err: any) {
      toastStore.error(err?.response?.data?.detail || 'Failed to restart generation.')
    } finally {
      actionLoading.value[jobId] = false
    }
  }

  // If user opens the queue, trigger an immediate refresh
  watch(isOpen, (newVal) => {
    if (newVal) {
      fetchQueue()
    }
  })

  return {
    activeJobs,
    recentJobs,
    totalActive,
    isOpen,
    isLoading,
    actionLoading,
    fetchQueue,
    scheduleNextPoll,
    openQueue,
    closeQueue,
    toggleQueue,
    cancelJob,
    retryJob,
  }
})
