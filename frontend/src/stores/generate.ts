import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { generationApi, type SubmitGenerationPayload } from '@/api/generation'
import { sessionsApi } from '@/api/sessions'
import { useSessionsStore } from './sessions'
import { useToastStore } from './toast'
import type { Generation, ModelConfig, StylePreset } from '@/types'

export interface AttachedImage {
  id: string
  file: File
  previewUrl: string
}

export const useGenerateStore = defineStore('generate', () => {
  const sessionsStore = useSessionsStore()
  const toastStore = useToastStore()

  // Input states
  const prompt = ref<string>('')
  const negativePrompt = ref<string>('')
  const showNegativePrompt = ref<boolean>(false)
  const selectedProfileId = ref<number | null>(null)
  const selectedModelConfigId = ref<number | null>(null)
  const aspectRatio = ref<string>('1:1')
  const resolution = ref<string>('1K')
  const seed = ref<string>('')
  const selectedStyleId = ref<string | number | null>(null)
  const attachedImages = ref<AttachedImage[]>([])

  // Available options
  const activeModels = ref<ModelConfig[]>([])
  const styles = ref<StylePreset[]>([])

  // History & active jobs
  const generations = ref<Generation[]>([])
  const activeJobIds = ref<number[]>([])
  const isSubmitting = ref<boolean>(false)
  const isLoadingHistory = ref<boolean>(false)

  const selectedModel = computed(() => {
    return activeModels.value.find((m) => m.id === selectedModelConfigId.value) || null
  })

  function addAttachedImage(file: File) {
    if (attachedImages.value.length >= 5) {
      toastStore.warning('Maximal 5 Referenzbilder erlaubt.')
      return
    }
    const previewUrl = URL.createObjectURL(file)
    attachedImages.value.push({
      id: Math.random().toString(36).substring(2, 9),
      file,
      previewUrl,
    })
  }

  function removeAttachedImage(id: string) {
    const item = attachedImages.value.find((img) => img.id === id)
    if (item) {
      URL.revokeObjectURL(item.previewUrl)
      attachedImages.value = attachedImages.value.filter((img) => img.id !== id)
    }
  }

  function clearAttachedImages() {
    attachedImages.value.forEach((img) => URL.revokeObjectURL(img.previewUrl))
    attachedImages.value = []
  }

  async function loadModelsAndStyles() {
    try {
      const [modelsData, stylesData] = await Promise.all([
        generationApi.getActiveModelConfigs(),
        generationApi.getStyles(),
      ])
      activeModels.value = modelsData
      styles.value = stylesData

      // Auto-select default model if none selected
      if (!selectedModelConfigId.value && activeModels.value.length > 0) {
        const defaultModel = activeModels.value.find((m) => m.is_default) || activeModels.value[0]
        selectedModelConfigId.value = defaultModel.id
      }
    } catch (_error) {
      // fallback
    }
  }

  async function loadSessionHistory(sessionToken: string) {
    if (!sessionToken) {
      generations.value = []
      return
    }
    isLoadingHistory.value = true
    try {
      const res = await sessionsApi.getSessionHistory(sessionToken)
      generations.value = res.generations
    } catch (_error) {
      generations.value = []
    } finally {
      isLoadingHistory.value = false
    }
  }

  async function pollJob(jobId: number) {
    if (!activeJobIds.value.includes(jobId)) {
      activeJobIds.value.push(jobId)
    }

    const interval = setInterval(async () => {
      try {
        const gen = await generationApi.getJobStatus(jobId)
        
        // Update in generations array
        const index = generations.value.findIndex((g) => g.id === jobId)
        if (index !== -1) {
          generations.value[index] = gen
        } else {
          generations.value.push(gen)
        }

        if (gen.status === 'succeeded') {
          clearInterval(interval)
          activeJobIds.value = activeJobIds.value.filter((id) => id !== jobId)
          toastStore.success('Bild erfolgreich generiert!')
          sessionsStore.fetchSessions()
        } else if (gen.status === 'failed' || gen.status === 'cancelled') {
          clearInterval(interval)
          activeJobIds.value = activeJobIds.value.filter((id) => id !== jobId)
          toastStore.error(gen.error_message || 'Generierung fehlgeschlagen.')
        }
      } catch (_error) {
        clearInterval(interval)
        activeJobIds.value = activeJobIds.value.filter((id) => id !== jobId)
      }
    }, 2000)
  }

  async function submit() {
    if (!prompt.value.trim()) {
      toastStore.warning('Bitte gib einen Prompt ein.')
      return
    }

    isSubmitting.value = true
    try {
      const payload: SubmitGenerationPayload = {
        prompt: prompt.value.trim(),
        negative_prompt: showNegativePrompt.value ? negativePrompt.value.trim() : undefined,
        profile_id: selectedProfileId.value,
        model_config_id: selectedModelConfigId.value,
        aspect_ratio: aspectRatio.value,
        resolution: resolution.value,
        seed: seed.value ? seed.value : null,
        session_token: sessionsStore.activeSessionToken || undefined,
        style_id: selectedStyleId.value,
        input_images: attachedImages.value.map((img) => img.file),
      }

      const res = await generationApi.submitGeneration(payload)
      
      // Temporary optimistic generation item
      const optimisticGen: Generation = {
        id: res.job_id,
        status: 'pending',
        progress: 10,
        prompt: prompt.value,
        negative_prompt: payload.negative_prompt,
        created_at: new Date().toISOString(),
        assets: [],
      }
      generations.value.push(optimisticGen)

      // Start polling
      pollJob(res.job_id)

      // Clear input images but keep prompt for quick iterations or clear if desired
      clearAttachedImages()
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Fehler beim Starten der Generierung.')
    } finally {
      isSubmitting.value = false
    }
  }

  function remixGeneration(gen: Generation) {
    prompt.value = gen.prompt
    if (gen.negative_prompt) {
      negativePrompt.value = gen.negative_prompt
      showNegativePrompt.value = true
    }
    if (gen.aspect_ratio) aspectRatio.value = gen.aspect_ratio
    if (gen.resolution) resolution.value = gen.resolution
    if (gen.seed !== undefined && gen.seed !== null) seed.value = String(gen.seed)
    toastStore.info('Prompt & Einstellungen übernommen!')
  }

  return {
    prompt,
    negativePrompt,
    showNegativePrompt,
    selectedProfileId,
    selectedModelConfigId,
    aspectRatio,
    resolution,
    seed,
    selectedStyleId,
    attachedImages,
    activeModels,
    styles,
    generations,
    activeJobIds,
    isSubmitting,
    isLoadingHistory,
    selectedModel,
    addAttachedImage,
    removeAttachedImage,
    clearAttachedImages,
    loadModelsAndStyles,
    loadSessionHistory,
    pollJob,
    submit,
    remixGeneration,
  }
})
