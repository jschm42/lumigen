import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { generationApi, type SubmitGenerationPayload } from '@/api/generation'
import { sessionsApi } from '@/api/sessions'
import { useSessionsStore } from './sessions'
import { useToastStore } from './toast'
import { useQueueStore } from './queue'
import type { Asset, Generation, ModelConfig, StylePreset } from '@/types'

export interface AttachedImage {
  id: string
  file?: File
  assetId?: number
  previewUrl: string
  name?: string
}

export interface DimensionPresetOption {
  label: string
  value: string
  ratio?: string
}

export const DIMENSION_PRESETS: DimensionPresetOption[] = [
  { label: 'Custom', value: '' },
  { label: '512 × 512 (1:1)', value: '512x512', ratio: '1:1' },
  { label: '768 × 768 (1:1)', value: '768x768', ratio: '1:1' },
  { label: '1024 × 1024 (1:1)', value: '1024x1024', ratio: '1:1' },
  { label: '1152 × 896 (9:7)', value: '1152x896', ratio: '4:3' },
  { label: '896 × 1152 (7:9)', value: '896x1152', ratio: '3:4' },
  { label: '1216 × 832 (3:2)', value: '1216x832', ratio: '3:2' },
  { label: '832 × 1216 (2:3)', value: '832x1216', ratio: '2:3' },
  { label: '1344 × 768 (16:9)', value: '1344x768', ratio: '16:9' },
  { label: '768 × 1344 (9:16)', value: '768x1344', ratio: '9:16' },
  { label: '1536 × 640 (21:9)', value: '1536x640', ratio: '21:9' },
  { label: '640 × 1536 (9:21)', value: '640x1536', ratio: '9:16' },
]

export const useGenerateStore = defineStore('generate', () => {
  const sessionsStore = useSessionsStore()
  const toastStore = useToastStore()
  const queueStore = useQueueStore()

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

  // Advanced Overrides (from old prompt panel)
  const isAdvancedOpen = ref<boolean>(false)
  const dimensionPreset = ref<string>('')
  const customWidth = ref<string>('')
  const customHeight = ref<string>('')
  const nImages = ref<number | null>(null)
  const openRouterAspectRatio = ref<string>('')
  const openRouterImageSize = ref<string>('')
  const falAspectRatio = ref<string>('')
  const falResolution = ref<string>('')
  const googleAspectRatio = ref<string>('')
  const googleResolution = ref<string>('')
  const upscaleModel = ref<string>('__profile__')
  const availableUpscaleModels = ref<{ value: string; label: string }[]>([
    { value: '__none__', label: 'No Upscaling' },
    { value: 'fal', label: 'FAL.ai Standard' },
    { value: 'local:RealESRGAN_x4plus', label: 'Real-ESRGAN x4plus (Local)' },
  ])

  // Available options
  const activeModels = ref<ModelConfig[]>([])
  const styles = ref<StylePreset[]>([])

  // History & active jobs
  const generations = ref<Generation[]>([])
  const activeJobIds = ref<number[]>([])
  const isSubmitting = ref<boolean>(false)
  const isLoadingHistory = ref<boolean>(false)

  const isGenerating = computed(() => {
    return isSubmitting.value || activeJobIds.value.length > 0
  })

  const selectedModel = computed(() => {
    return activeModels.value.find((m) => m.id === selectedModelConfigId.value) || null
  })

  function addAttachedImage(file: File) {
    if (attachedImages.value.length >= 5) {
      toastStore.warning('Maximum 5 reference images allowed.')
      return
    }
    const previewUrl = URL.createObjectURL(file)
    attachedImages.value.push({
      id: Math.random().toString(36).substring(2, 9),
      file,
      previewUrl,
      name: file.name,
    })
  }

  function attachAssetAsImage(asset: Asset) {
    if (attachedImages.value.length >= 5) {
      toastStore.warning('Maximum 5 reference images allowed.')
      return
    }
    const alreadyExists = attachedImages.value.some((img) => img.assetId === asset.id)
    if (alreadyExists) {
      toastStore.info('This image is already selected.')
      return
    }
    attachedImages.value.push({
      id: `asset-${asset.id}`,
      assetId: asset.id,
      previewUrl: asset.thumbnail_url || asset.image_url,
      name: `Asset #${asset.id}`,
    })
    toastStore.success(`Asset #${asset.id} added as input image!`)
  }

  function removeAttachedImage(id: string) {
    const item = attachedImages.value.find((img) => img.id === id)
    if (item) {
      if (item.previewUrl.startsWith('blob:')) {
        URL.revokeObjectURL(item.previewUrl)
      }
      attachedImages.value = attachedImages.value.filter((img) => img.id !== id)
    }
  }

  function clearAttachedImages() {
    attachedImages.value.forEach((img) => {
      if (img.previewUrl.startsWith('blob:')) {
        URL.revokeObjectURL(img.previewUrl)
      }
    })
    attachedImages.value = []
  }

  function onDimensionPresetChange(preset: string) {
    dimensionPreset.value = preset
    if (preset && preset.includes('x')) {
      const [w, h] = preset.split('x')
      customWidth.value = w
      customHeight.value = h
      const found = DIMENSION_PRESETS.find((p) => p.value === preset)
      if (found?.ratio) {
        aspectRatio.value = found.ratio
        falAspectRatio.value = found.ratio
        openRouterAspectRatio.value = found.ratio
        googleAspectRatio.value = found.ratio
      }
    }
  }

  function syncDimensionsToPreset() {
    if (customWidth.value && customHeight.value) {
      const dimKey = `${customWidth.value.trim()}x${customHeight.value.trim()}`
      const match = DIMENSION_PRESETS.find((p) => p.value === dimKey)
      dimensionPreset.value = match ? match.value : ''
    } else {
      dimensionPreset.value = ''
    }
  }

  function applyProfileDefaults(profile: any) {
    if (profile.aspect_ratio || profile.default_aspect_ratio) {
      aspectRatio.value = profile.aspect_ratio || profile.default_aspect_ratio || '1:1'
    }
    if (profile.resolution || profile.default_resolution) {
      resolution.value = profile.resolution || profile.default_resolution || '1K'
    }

    // Dimensions: width / height & Preset
    if (profile.width && profile.height) {
      customWidth.value = String(profile.width)
      customHeight.value = String(profile.height)
      const dimKey = `${profile.width}x${profile.height}`
      const match = DIMENSION_PRESETS.find((p) => p.value === dimKey)
      dimensionPreset.value = match ? match.value : ''
    } else {
      customWidth.value = ''
      customHeight.value = ''
      dimensionPreset.value = ''
    }

    // Provider specific overrides
    openRouterAspectRatio.value = profile.openrouter_aspect_ratio || ''
    openRouterImageSize.value = profile.openrouter_image_size || ''
    falAspectRatio.value = profile.fal_aspect_ratio || ''
    falResolution.value = profile.fal_resolution || ''
    googleAspectRatio.value = profile.google_aspect_ratio || ''
    googleResolution.value = profile.google_resolution || ''

    // nImages & seed
    nImages.value = profile.n_images ?? null
    seed.value = profile.seed != null ? String(profile.seed) : ''

    // Upscaling: Pre-fill matching profile config
    if (profile.upscale_provider === 'fal') {
      if (profile.upscale_topaz_model_id) {
        upscaleModel.value = `falm:${profile.upscale_topaz_model_id}`
      } else {
        upscaleModel.value = 'fal'
      }
    } else if (profile.upscale_provider === 'local' && profile.upscale_model) {
      upscaleModel.value = `local:${profile.upscale_model}`
    } else if (profile.upscale_model === '__none__' || (!profile.upscale_provider && !profile.upscale_model)) {
      upscaleModel.value = '__none__'
    } else if (profile.upscale_model) {
      upscaleModel.value = profile.upscale_model
    } else {
      upscaleModel.value = '__none__'
    }
  }

  function clearProfileDefaults() {
    dimensionPreset.value = ''
    customWidth.value = ''
    customHeight.value = ''
    openRouterAspectRatio.value = ''
    openRouterImageSize.value = ''
    falAspectRatio.value = ''
    falResolution.value = ''
    googleAspectRatio.value = ''
    googleResolution.value = ''
    nImages.value = null
    seed.value = ''
    upscaleModel.value = '__none__'
    aspectRatio.value = '1:1'
    resolution.value = '1K'
  }

  async function loadModelsAndStyles() {
    try {
      const modelsData = await generationApi.getActiveModelConfigs()
      activeModels.value = modelsData || []

      // Auto-select default model if none selected or current selection is invalid
      const currentSelectedExists = activeModels.value.some((m) => m.id === selectedModelConfigId.value)
      if (!currentSelectedExists && activeModels.value.length > 0) {
        const defaultModel = activeModels.value.find((m) => m.is_default) || activeModels.value[0]
        selectedModelConfigId.value = defaultModel.id
      }
    } catch (_error) {
      // fallback
    }

    try {
      const stylesData = await generationApi.getStyles()
      styles.value = stylesData || []
    } catch (_error) {
      // fallback
    }

    try {
      const upscaleData = await generationApi.getUpscaleModels()
      if (Array.isArray(upscaleData) && upscaleData.length > 0) {
        availableUpscaleModels.value = upscaleData
      }
    } catch (_error) {
      // fallback
    }
  }


  const pollingIntervals = new Map<number, ReturnType<typeof setInterval>>()

  function stopPolling(jobId: number) {
    const timer = pollingIntervals.get(jobId)
    if (timer) {
      clearInterval(timer)
      pollingIntervals.delete(jobId)
    }
    activeJobIds.value = activeJobIds.value.filter((id) => id !== jobId)
  }

  function clearAllPolling() {
    pollingIntervals.forEach((timer) => clearInterval(timer))
    pollingIntervals.clear()
    activeJobIds.value = []
  }

  async function loadSessionHistory(sessionToken: string) {
    clearAllPolling()
    if (!sessionToken) {
      generations.value = []
      return
    }
    isLoadingHistory.value = true
    try {
      const res = await sessionsApi.getSessionHistory(sessionToken)
      generations.value = Array.isArray(res?.generations) ? res.generations : []
      generations.value.forEach((g) => {
        const isStillRunning = (g.status === 'queued' || g.status === 'running' || g.status === 'pending' || g.status === 'processing') && (!g.assets || g.assets.length === 0)
        if (isStillRunning && !activeJobIds.value.includes(g.id)) {
          pollJob(g.id)
        }
      })
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

    if (pollingIntervals.has(jobId)) {
      clearInterval(pollingIntervals.get(jobId))
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

        if (gen.session_token && !sessionsStore.activeSessionToken) {
          sessionsStore.setActiveSessionToken(gen.session_token)
        }

        if (gen.status === 'succeeded') {
          stopPolling(jobId)
          toastStore.success('Image successfully generated!')
          sessionsStore.fetchSessions()
        } else if (gen.status === 'failed' || gen.status === 'cancelled') {
          stopPolling(jobId)
          toastStore.error(gen.error_message || 'Generation failed.')
        }
      } catch (_error) {
        stopPolling(jobId)
      }
    }, 2000)

    pollingIntervals.set(jobId, interval)
  }

  async function deleteGeneration(jobId: number) {
    stopPolling(jobId)
    generations.value = generations.value.filter((g) => g.id !== jobId)

    try {
      await generationApi.deleteGeneration(jobId)
      toastStore.success('Generation deleted.')
    } catch (_error) {
      toastStore.info('Generation removed from view.')
    } finally {
      sessionsStore.fetchSessions()
      queueStore.fetchQueue()
    }
  }

  async function submit() {
    if (!prompt.value.trim()) {
      toastStore.warning('Please enter a prompt.')
      return
    }

    isSubmitting.value = true
    try {
      const inputFiles = attachedImages.value
        .filter((img) => img.file)
        .map((img) => img.file as File)
      const firstAsset = attachedImages.value.find((img) => img.assetId)

      const payload: SubmitGenerationPayload = {
        prompt: prompt.value.trim(),
        negative_prompt: showNegativePrompt.value ? negativePrompt.value.trim() : undefined,
        profile_id: selectedProfileId.value,
        model_config_id: selectedModelConfigId.value,
        aspect_ratio: openRouterAspectRatio.value || aspectRatio.value,
        resolution: resolution.value,
        image_size: openRouterImageSize.value || undefined,
        fal_aspect_ratio: falAspectRatio.value || undefined,
        fal_resolution: falResolution.value || undefined,
        google_aspect_ratio: googleAspectRatio.value || undefined,
        google_resolution: googleResolution.value || undefined,
        width: customWidth.value ? Number(customWidth.value) : undefined,
        height: customHeight.value ? Number(customHeight.value) : undefined,
        n_images: nImages.value || undefined,
        seed: seed.value ? seed.value : null,
        upscale_model: upscaleModel.value !== '__profile__' ? upscaleModel.value : undefined,
        session_token: sessionsStore.activeSessionToken || undefined,
        style_id: selectedStyleId.value,
        input_images: inputFiles.length > 0 ? inputFiles : undefined,
        asset_id: firstAsset ? firstAsset.assetId : undefined,
      }

      const res = await generationApi.submitGeneration(payload)
      
      // If no session was active, immediately adopt the newly created session
      if (res.session_token && !sessionsStore.activeSessionToken) {
        sessionsStore.setActiveSessionToken(res.session_token)
        sessionsStore.fetchSessions()
      }

      // Temporary optimistic generation item
      const optimisticGen: Generation = {
        id: res.job_id,
        status: 'queued',
        progress: 10,
        prompt: prompt.value,
        negative_prompt: payload.negative_prompt,
        created_at: new Date().toISOString(),
        session_token: res.session_token,
        assets: [],
      }
      generations.value.push(optimisticGen)

      // Start polling
      pollJob(res.job_id)
      queueStore.fetchQueue()

      // Clear input images but keep prompt for quick iterations
      clearAttachedImages()
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to start generation.')
    } finally {
      isSubmitting.value = false
    }
  }

  async function retryGeneration(gen: Generation) {
    isSubmitting.value = true
    try {
      const res = await generationApi.retryJob(gen.id)
      const optimisticGen: Generation = {
        id: res.job_id,
        status: 'queued',
        progress: 10,
        prompt: gen.prompt,
        negative_prompt: gen.negative_prompt,
        model_name: gen.model_name,
        aspect_ratio: gen.aspect_ratio,
        resolution: gen.resolution,
        created_at: new Date().toISOString(),
        session_token: gen.session_token,
        assets: [],
      }
      generations.value.push(optimisticGen)
      pollJob(res.job_id)
      queueStore.fetchQueue()
      toastStore.info(`Generation #${res.job_id} queued again!`)
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to restart generation.')
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
    toastStore.info('Prompt & settings applied!')
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
    isAdvancedOpen,
    dimensionPreset,
    customWidth,
    customHeight,
    nImages,
    openRouterAspectRatio,
    openRouterImageSize,
    falAspectRatio,
    falResolution,
    googleAspectRatio,
    googleResolution,
    upscaleModel,
    availableUpscaleModels,
    activeModels,
    styles,
    generations,
    activeJobIds,
    isSubmitting,
    isGenerating,
    isLoadingHistory,
    selectedModel,
    addAttachedImage,
    attachAssetAsImage,
    removeAttachedImage,
    clearAttachedImages,
    onDimensionPresetChange,
    syncDimensionsToPreset,
    applyProfileDefaults,
    clearProfileDefaults,
    loadModelsAndStyles,
    loadSessionHistory,
    pollJob,
    stopPolling,
    clearAllPolling,
    deleteGeneration,
    submit,
    retryGeneration,
    remixGeneration,
  }
})

