import { defineStore } from 'pinia'
import { ref } from 'vue'
import { adminApi, type SystemInfo } from '@/api/admin'
import { useToastStore } from './toast'
import type { ModelConfig, ProviderApiKeyStatus, StylePreset, UpscaleModel, User } from '@/types'

export const useAdminStore = defineStore('admin', () => {
  const toastStore = useToastStore()

  const providerStatuses = ref<ProviderApiKeyStatus[]>([])
  const modelConfigs = ref<ModelConfig[]>([])
  const styles = ref<StylePreset[]>([])
  const users = ref<User[]>([])
  const systemInfo = ref<SystemInfo | null>(null)
  const isLoading = ref<boolean>(false)

  async function fetchProviderKeys() {
    try {
      providerStatuses.value = await adminApi.getProviderKeys()
    } catch (_error) {
      providerStatuses.value = []
    }
  }

  async function updateProviderKey(provider: string, apiKey: string) {
    try {
      const res = await adminApi.updateProviderKey(provider, apiKey)
      toastStore.success(`API key for ${provider.toUpperCase()} saved.`)
      fetchProviderKeys()
      return res
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to save API key.')
      throw error
    }
  }

  async function testProvider(provider: string) {
    try {
      const res = await adminApi.testProvider(provider)
      toastStore.success(res.message || 'Connection successful!')
      return res
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Connection test failed.')
      throw error
    }
  }

  async function fetchModelConfigs() {
    try {
      modelConfigs.value = await adminApi.listModelConfigs()
    } catch (_error) {
      modelConfigs.value = []
    }
  }

  async function saveModelConfig(config: Partial<ModelConfig>) {
    try {
      const saved = await adminApi.saveModelConfig(config)
      const index = modelConfigs.value.findIndex((m) => m.id === saved.id)
      if (index !== -1) {
        modelConfigs.value[index] = saved
      } else {
        modelConfigs.value.push(saved)
      }
      toastStore.success('Model configuration saved.')
      return saved
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to save model configuration.')
      throw error
    }
  }

  async function deleteModelConfig(id: number) {
    try {
      await adminApi.deleteModelConfig(id)
      modelConfigs.value = modelConfigs.value.filter((m) => m.id !== id)
      toastStore.success('Model configuration deleted.')
    } catch (_error) {
      toastStore.error('Failed to delete.')
    }
  }

  async function fetchStyles() {
    try {
      styles.value = await adminApi.listStyles()
    } catch (_error) {
      styles.value = []
    }
  }

  async function deleteStyle(styleId: string | number) {
    try {
      await adminApi.deleteStyle(styleId)
      styles.value = styles.value.filter((s) => s.id !== styleId)
      toastStore.success('Style deleted.')
    } catch (_error) {
      toastStore.error('Failed to delete style.')
    }
  }

  async function restoreDefaultStyles() {
    try {
      const res = await adminApi.restoreDefaultStyles()
      toastStore.success(res.message || 'Default styles restored.')
      await fetchStyles()
      return res
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to restore default styles.')
      throw error
    }
  }

  async function fetchUsers() {
    try {
      users.value = await adminApi.listUsers()
    } catch (_error) {
      users.value = []
    }
  }

  async function fetchSystemInfo() {
    try {
      systemInfo.value = await adminApi.getSystemInfo()
    } catch (_error) {
      systemInfo.value = null
    }
  }

  const upscaleModels = ref<UpscaleModel[]>([])

  async function fetchUpscaleModels() {
    try {
      upscaleModels.value = await adminApi.listUpscaleModels()
    } catch (_error) {
      upscaleModels.value = []
    }
  }

  async function saveUpscaleModel(config: Partial<UpscaleModel>) {
    try {
      const saved = await adminApi.saveUpscaleModel(config)
      const index = upscaleModels.value.findIndex((m) => m.id === saved.id)
      if (index !== -1) {
        upscaleModels.value[index] = saved
      } else {
        upscaleModels.value.push(saved)
      }
      if (saved.is_default) {
        upscaleModels.value.forEach((m) => {
          if (m.id !== saved.id) m.is_default = false
        })
      }
      toastStore.success(`Upscale model "${saved.name}" saved.`)
      return saved
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to save upscale model.')
      throw error
    }
  }

  async function deleteUpscaleModel(id: number) {
    try {
      await adminApi.deleteUpscaleModel(id)
      upscaleModels.value = upscaleModels.value.filter((m) => m.id !== id)
      toastStore.success('Upscale model deleted.')
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to delete upscale model.')
      throw error
    }
  }

  async function toggleUpscaleModel(id: number) {
    try {
      const res = await adminApi.toggleUpscaleModel(id)
      const model = upscaleModels.value.find((m) => m.id === id)
      if (model) model.is_enabled = res.is_enabled
      toastStore.success(`Model ${res.is_enabled ? 'enabled' : 'disabled'}.`)
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to toggle model.')
    }
  }

  async function setDefaultUpscaleModel(id: number) {
    try {
      await adminApi.setDefaultUpscaleModel(id)
      upscaleModels.value.forEach((m) => {
        m.is_default = m.id === id
      })
      toastStore.success('Default upscale model updated.')
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to set default model.')
    }
  }

  return {
    providerStatuses,
    modelConfigs,
    upscaleModels,
    styles,
    users,
    systemInfo,
    isLoading,
    fetchProviderKeys,
    updateProviderKey,
    testProvider,
    fetchModelConfigs,
    saveModelConfig,
    deleteModelConfig,
    fetchUpscaleModels,
    saveUpscaleModel,
    deleteUpscaleModel,
    toggleUpscaleModel,
    setDefaultUpscaleModel,
    fetchStyles,
    deleteStyle,
    restoreDefaultStyles,
    fetchUsers,
    fetchSystemInfo,
  }
})
