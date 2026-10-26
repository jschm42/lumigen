import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { generationApi, type SubmitGenerationPayload } from '@/api/generation'
import { sessionsApi } from '@/api/sessions'
import { useSessionsStore } from './sessions'
import { useToastStore } from './toast'
import { useQueueStore } from './queue'
import type { Asset, Generation, ModelConfig, StylePreset, TokenUsage } from '@/types'

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
  const selectedCategoryIds = ref<number[]>([])
  const profileLockedCategoryIds = ref<number[]>([])

  // Agentic Mode
  const isAgenticMode = ref<boolean>(false)
  const agenticMinImages = ref<number | null>(null)
  const agenticMaxImages = ref<number | null>(null)
  const agenticLlmModel = ref<string>('')
  const availableLlmModels = ref<{ id: string; name: string; provider: string; is_default?: boolean }[]>([])

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
  // Bumped on every submit so the feed can scroll the new job into view.
  const lastSubmittedAt = ref<number>(0)

  const isGenerating = computed(() => {
    return isSubmitting.value || activeJobIds.value.length > 0
  })

  const selectedModel = computed(() => {
    return activeModels.value.find((m) => m.id === selectedModelConfigId.value) || null
  })

  // Media kind of the selected model; drives the video-specific controls.
  const selectedMediaType = computed<'image' | 'video'>(() =>
    selectedModel.value?.media_type === 'video' ? 'video' : 'image'
  )
  const isVideoModel = computed(() => selectedMediaType.value === 'video')

  // Video-only generation options (provider payload: media_type/duration/generate_audio).
  const videoDuration = ref<number>(5)
  const videoGenerateAudio = ref<boolean>(false)

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

    // Categories: Lock profile categories and merge with custom selected categories
    const oldLocked = profileLockedCategoryIds.value
    const profileCatIds: number[] = Array.isArray(profile.categories)
      ? profile.categories.map((c: any) => c.id)
      : Array.isArray(profile.category_ids)
        ? profile.category_ids
        : []
    profileLockedCategoryIds.value = profileCatIds
    const userCategories = selectedCategoryIds.value.filter((id) => !oldLocked.includes(id))
    selectedCategoryIds.value = Array.from(new Set([...userCategories, ...profileCatIds]))
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

    // Remove previously locked profile categories, preserve user-selected ones
    selectedCategoryIds.value = selectedCategoryIds.value.filter(
      (id) => !profileLockedCategoryIds.value.includes(id)
    )
    profileLockedCategoryIds.value = []
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

    try {
      const llmData = await generationApi.getLlmModels()
      if (Array.isArray(llmData) && llmData.length > 0) {
        availableLlmModels.value = llmData
      }
    } catch (_error) {
      // fallback
    }
  }


  // --- Job polling -------------------------------------------------------
  // A single loop polls all tracked jobs with one batch request. The interval starts
  // fast and backs off for long-running jobs; transient network errors are retried
  // instead of silently abandoning the job (which left spinners hanging forever).
  const POLL_FAST_MS = 1500
  const POLL_SLOW_MS = 4000
  const POLL_FAST_WINDOW_MS = 30000
  const POLL_MAX_CONSECUTIVE_ERRORS = 8

  const sessionUsageTotal = ref<TokenUsage | null>(null)
  const jobStartedAt = new Map<number, number>()
  let pollTimer: ReturnType<typeof setTimeout> | null = null
  let pollInFlight = false
  let consecutivePollErrors = 0

  const isRunningStatus = (status: Generation['status']) =>
    status === 'queued' || status === 'running' || status === 'pending' || status === 'processing'

  function stopPolling(jobId: number) {
    jobStartedAt.delete(jobId)
    activeJobIds.value = activeJobIds.value.filter((id) => id !== jobId)
    if (activeJobIds.value.length === 0 && pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  function clearAllPolling() {
    if (pollTimer) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
    jobStartedAt.clear()
    activeJobIds.value = []
    consecutivePollErrors = 0
  }

  function nextPollDelay(): number {
    const now = Date.now()
    const hasFreshJob = Array.from(jobStartedAt.values()).some((start) => now - start < POLL_FAST_WINDOW_MS)
    const base = hasFreshJob ? POLL_FAST_MS : POLL_SLOW_MS
    const backoff = Math.min(consecutivePollErrors, 4) * 1000
    const hiddenPenalty = typeof document !== 'undefined' && document.hidden ? POLL_SLOW_MS : 0
    return base + backoff + hiddenPenalty
  }

  function schedulePoll(delay = nextPollDelay()) {
    if (pollTimer) clearTimeout(pollTimer)
    if (activeJobIds.value.length === 0) {
      pollTimer = null
      return
    }
    pollTimer = setTimeout(runPollCycle, delay)
  }

  function upsertGeneration(gen: Generation) {
    const index = generations.value.findIndex((g) => g.id === gen.id)
    if (index !== -1) {
      generations.value[index] = gen
    } else if (!sessionsStore.activeSessionToken || gen.session_token === sessionsStore.activeSessionToken) {
      generations.value.push(gen)
    }
  }

  function handleFinishedJob(gen: Generation) {
    stopPolling(gen.id)
    if (gen.status === 'succeeded') {
      const count = gen.assets?.length || 0
      toastStore.success(count > 1 ? `${count} images generated!` : 'Image successfully generated!')
      sessionsStore.fetchSessions()
      recalcUsageTotal()
    } else if (gen.status === 'failed') {
      toastStore.error(gen.error_message || 'Generation failed.')
    }
    queueStore.fetchQueue()
  }

  async function runPollCycle() {
    pollTimer = null
    if (pollInFlight || activeJobIds.value.length === 0) return
    pollInFlight = true
    const ids = [...activeJobIds.value]
    try {
      const res = await generationApi.getJobsStatus(ids)
      consecutivePollErrors = 0
      res.missing.forEach((id) => {
        stopPolling(id)
        generations.value = generations.value.filter((g) => g.id !== id)
      })
      res.jobs.forEach((gen) => {
        upsertGeneration(gen)
        if (gen.session_token && !sessionsStore.activeSessionToken) {
          sessionsStore.setActiveSessionToken(gen.session_token)
        }
        if (!isRunningStatus(gen.status)) {
          handleFinishedJob(gen)
        }
      })
    } catch (_error) {
      consecutivePollErrors += 1
      if (consecutivePollErrors >= POLL_MAX_CONSECUTIVE_ERRORS) {
        toastStore.warning('Lost connection while tracking generations. Reload the session to refresh.')
        clearAllPolling()
      }
    } finally {
      pollInFlight = false
      schedulePoll()
    }
  }

  function pollJob(jobId: number) {
    if (!activeJobIds.value.includes(jobId)) {
      activeJobIds.value.push(jobId)
    }
    if (!jobStartedAt.has(jobId)) {
      jobStartedAt.set(jobId, Date.now())
    }
    if (!pollTimer && !pollInFlight) {
      schedulePoll(POLL_FAST_MS)
    }
  }

  function recalcUsageTotal() {
    const items = generations.value.map((g) => g.usage).filter((u): u is TokenUsage => !!u)
    if (items.length === 0) {
      sessionUsageTotal.value = null
      return
    }
    // Costs only add up within one currency (same rule as the backend's sum_usage).
    const currencies = new Set(items.filter((u) => u.cost != null).map((u) => u.currency).filter(Boolean))
    const currency = currencies.size === 1 ? (Array.from(currencies)[0] as string) : currencies.size > 1 ? 'mixed' : null
    sessionUsageTotal.value = {
      input_tokens: items.reduce((sum, u) => sum + (u.input_tokens || 0), 0),
      output_tokens: items.reduce((sum, u) => sum + (u.output_tokens || 0), 0),
      total_tokens: items.reduce((sum, u) => sum + (u.total_tokens || 0), 0),
      cost: currency && currency !== 'mixed' ? items.reduce((sum, u) => sum + (u.cost || 0), 0) : null,
      currency,
    }
  }

  async function loadSessionHistory(sessionToken: string) {
    clearAllPolling()
    if (!sessionToken) {
      generations.value = []
      sessionUsageTotal.value = null
      return
    }
    isLoadingHistory.value = true
    try {
      const res = await sessionsApi.getSessionHistory(sessionToken)
      generations.value = Array.isArray(res?.generations) ? res.generations : []
      sessionUsageTotal.value = res?.usage_total || null
      generations.value.forEach((g) => {
        if (isRunningStatus(g.status) && (!g.assets || g.assets.length === 0)) {
          pollJob(g.id)
        }
      })
    } catch (_error) {
      generations.value = []
      sessionUsageTotal.value = null
    } finally {
      isLoadingHistory.value = false
    }
  }

  async function cancelGeneration(jobId: number) {
    try {
      const res = await generationApi.cancelJob(jobId)
      if (res.success) {
        const gen = generations.value.find((g) => g.id === jobId)
        if (gen) gen.status = 'cancelled'
        stopPolling(jobId)
        toastStore.info('Generation cancelled.')
      } else {
        toastStore.warning(res.message || 'Generation could not be cancelled.')
      }
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to cancel generation.')
    } finally {
      queueStore.fetchQueue()
    }
  }

  async function deleteGeneration(jobId: number) {
    stopPolling(jobId)
    generations.value = generations.value.filter((g) => g.id !== jobId)
    recalcUsageTotal()

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
        category_ids: selectedCategoryIds.value.length > 0 ? selectedCategoryIds.value : undefined,
        input_images: inputFiles.length > 0 ? inputFiles : undefined,
        asset_id: firstAsset ? firstAsset.assetId : undefined,
        // Video models need an explicit media type so the provider builds a clip payload.
        media_type: isVideoModel.value ? 'video' : undefined,
        duration: isVideoModel.value ? videoDuration.value : undefined,
        generate_audio: isVideoModel.value ? videoGenerateAudio.value : undefined,
        is_agentic: isAgenticMode.value ? true : undefined,
        min_images: isAgenticMode.value ? agenticMinImages.value : undefined,
        max_images: isAgenticMode.value ? agenticMaxImages.value : undefined,
        llm_model: isAgenticMode.value && agenticLlmModel.value ? agenticLlmModel.value : undefined,
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
        progress: 0,
        prompt: payload.prompt,
        negative_prompt: payload.negative_prompt,
        model_name: selectedModel.value?.name,
        provider: selectedModel.value?.provider,
        aspect_ratio: payload.aspect_ratio,
        resolution: payload.resolution,
        n_images: payload.n_images ?? null,
        created_at: new Date().toISOString(),
        session_token: res.session_token,
        assets: [],
        is_agentic: isAgenticMode.value,
        agentic_step: isAgenticMode.value ? 'planning' : undefined,
        total_planned: isAgenticMode.value ? (agenticMaxImages.value ?? undefined) : undefined,
      }
      generations.value.push(optimisticGen)
      lastSubmittedAt.value = Date.now()

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
        progress: 0,
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
      lastSubmittedAt.value = Date.now()
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
    lastSubmittedAt,
    sessionUsageTotal,
    selectedModel,
    selectedMediaType,
    isVideoModel,
    videoDuration,
    videoGenerateAudio,
    selectedCategoryIds,
    profileLockedCategoryIds,
    isAgenticMode,
    agenticMinImages,
    agenticMaxImages,
    agenticLlmModel,
    availableLlmModels,
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
    cancelGeneration,
    submit,
    retryGeneration,
    remixGeneration,
  }
})

