import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { galleryApi, type GalleryFacets, type GalleryFilterParams } from '@/api/gallery'
import { accountApi } from '@/api/account'
import { useToastStore } from './toast'
import type { Asset, Category, GalleryFilterState, GalleryPreset, GalleryPresetFilters } from '@/types'

/** Filter keys that are shared via URL and stored in presets (view preferences excluded). */
const FILTER_KEYS = [
  'q',
  'min_rating',
  'unrated',
  'time_preset',
  'date_from',
  'date_to',
  'category_ids',
  'profile_name',
  'provider',
  'model',
  'collapse_stacks',
] as const

type FilterKey = (typeof FILTER_KEYS)[number]

export const useGalleryStore = defineStore('gallery', () => {
  const toastStore = useToastStore()

  const assets = ref<Asset[]>([])
  const categories = ref<Category[]>([])
  const total = ref<number>(0)
  const page = ref<number>(1)
  const totalPages = ref<number>(1)
  const isLoading = ref<boolean>(false)
  const isLoadingMore = ref<boolean>(false)
  const hasLoadedOnce = ref<boolean>(false)

  // Selection state
  const selectedAssetIds = ref<number[]>([])

  // Modal / Detail state
  const activeAsset = ref<Asset | null>(null)
  const isDetailModalOpen = ref<boolean>(false)

  // View preferences (thumbnail size / crop) persist per browser.
  const VIEW_PREFS_KEY = 'lumigen_gallery_view'
  const PAGE_SIZE = 40

  type ViewPrefs = Pick<GalleryFilterState, 'thumb_size' | 'thumb_fit' | 'group_by_date'>

  function readViewPrefs(): ViewPrefs {
    try {
      const raw = JSON.parse(localStorage.getItem(VIEW_PREFS_KEY) || '{}')
      return {
        thumb_size: ['sm', 'md', 'lg'].includes(raw.thumb_size) ? raw.thumb_size : 'md',
        thumb_fit: raw.thumb_fit === 'contain' ? 'contain' : 'cover',
        group_by_date: raw.group_by_date !== false,
      }
    } catch (_e) {
      return { thumb_size: 'md', thumb_fit: 'cover', group_by_date: true }
    }
  }

  function defaultFilters(): GalleryFilterState {
    return {
      q: '',
      profile_name: '',
      provider: '',
      model: '',
      min_rating: null,
      unrated: false,
      time_preset: '',
      date_from: '',
      date_to: '',
      category_ids: [],
      collapse_stacks: true,
      ...readViewPrefs(),
    }
  }

  // Filters
  const filters = ref<GalleryFilterState>(defaultFilters())

  watch(
    () => [filters.value.thumb_size, filters.value.thumb_fit, filters.value.group_by_date],
    ([thumbSize, thumbFit, groupByDate]) => {
      try {
        localStorage.setItem(
          VIEW_PREFS_KEY,
          JSON.stringify({ thumb_size: thumbSize, thumb_fit: thumbFit, group_by_date: groupByDate })
        )
      } catch (_e) {
        // Storage unavailable: preferences simply do not persist.
      }
    }
  )

  const activeFilterCount = computed(() => {
    const f = filters.value
    let count = 0
    if (f.q.trim()) count++
    if (f.min_rating) count++
    if (f.unrated) count++
    if (f.time_preset) count++
    if (f.category_ids.length) count++
    if (f.profile_name) count++
    if (f.provider) count++
    if (f.model) count++
    return count
  })

  // --- Facets (provider / model / profile options) ---------------------------
  const facets = ref<GalleryFacets>({ providers: [], models: [], profiles: [] })

  async function loadFacets() {
    try {
      facets.value = await galleryApi.getFacets()
    } catch (_e) {
      // Filters simply show no extra options.
    }
  }

  // --- URL sync ---------------------------------------------------------------
  /** Serialize the active filters into URL query parameters (defaults are omitted). */
  function filtersToQuery(): Record<string, string> {
    const f = filters.value
    const query: Record<string, string> = {}
    if (f.q.trim()) query.q = f.q.trim()
    if (f.unrated) query.rating = 'unrated'
    else if (f.min_rating) query.rating = String(f.min_rating)
    if (f.time_preset) query.time = f.time_preset
    if (f.date_from) query.from = f.date_from
    if (f.date_to) query.to = f.date_to
    if (f.category_ids.length) query.cats = f.category_ids.join(',')
    if (f.profile_name) query.profile = f.profile_name
    if (f.provider) query.provider = f.provider
    if (f.model) query.model = f.model
    if (!f.collapse_stacks) query.stacks = 'expanded'
    return query
  }

  /** Apply filters from URL query parameters; unknown or missing keys fall back to defaults. */
  function applyQuery(query: Record<string, unknown>) {
    const read = (key: string) => (typeof query[key] === 'string' ? (query[key] as string) : '')
    const rating = read('rating')
    const cats = read('cats')
      .split(',')
      .map((v) => Number(v))
      .filter((v) => Number.isInteger(v) && v > 0)
    filters.value = {
      ...filters.value,
      q: read('q'),
      unrated: rating === 'unrated',
      min_rating: rating && rating !== 'unrated' ? Number(rating) || null : null,
      time_preset: read('time'),
      date_from: read('from'),
      date_to: read('to'),
      category_ids: cats,
      profile_name: read('profile'),
      provider: read('provider'),
      model: read('model'),
      collapse_stacks: read('stacks') !== 'expanded',
    }
  }

  // --- Presets ----------------------------------------------------------------
  const presets = ref<GalleryPreset[]>([])

  function currentPresetFilters(): GalleryPresetFilters {
    const result: Record<string, unknown> = {}
    FILTER_KEYS.forEach((key: FilterKey) => {
      result[key] = filters.value[key]
    })
    return result as GalleryPresetFilters
  }

  async function loadPresets() {
    try {
      presets.value = await accountApi.getGalleryPresets()
    } catch (_e) {
      presets.value = []
    }
  }

  async function persistPresets(next: GalleryPreset[]) {
    try {
      presets.value = await accountApi.saveGalleryPresets(next)
      return true
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Presets could not be saved.')
      return false
    }
  }

  async function savePreset(name: string) {
    const trimmed = name.trim().slice(0, 40)
    if (!trimmed) return
    const existing = presets.value.find((p) => p.name.toLowerCase() === trimmed.toLowerCase())
    const preset: GalleryPreset = {
      id: existing?.id || `${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`,
      name: trimmed,
      filters: currentPresetFilters(),
    }
    const next = existing
      ? presets.value.map((p) => (p.id === existing.id ? preset : p))
      : [...presets.value, preset]
    if (await persistPresets(next)) {
      toastStore.success(existing ? `Preset "${trimmed}" updated.` : `Preset "${trimmed}" saved.`)
    }
  }

  async function deletePreset(id: string) {
    await persistPresets(presets.value.filter((p) => p.id !== id))
  }

  function applyPreset(preset: GalleryPreset) {
    const { thumb_size, thumb_fit, group_by_date } = filters.value
    filters.value = {
      ...defaultFilters(),
      ...preset.filters,
      category_ids: [...(preset.filters.category_ids || [])],
      thumb_size,
      thumb_fit,
      group_by_date,
    }
    fetchAssets(true)
  }

  // Stack expansion state
  const expandedStackIds = ref<Set<string>>(new Set())

  function isStackExpanded(stackId?: string | null): boolean {
    if (!stackId) return false
    return expandedStackIds.value.has(stackId)
  }

  function toggleStackExpanded(stackId: string) {
    const next = new Set(expandedStackIds.value)
    if (next.has(stackId)) {
      next.delete(stackId)
    } else {
      next.add(stackId)
    }
    expandedStackIds.value = next
  }

  function expandAllStacks() {
    const next = new Set<string>()
    assets.value.forEach((a) => {
      if (a.stack_id) next.add(a.stack_id)
    })
    expandedStackIds.value = next
  }

  function collapseAllStacks() {
    expandedStackIds.value = new Set()
  }

  async function loadCategories() {
    try {
      categories.value = await galleryApi.listCategories()
    } catch (_error) {
      // fallback
    }
  }

  // Each fetch gets a sequence number; responses from superseded requests are dropped,
  // so fast typing in the search box can never show results of an older query.
  let requestSeq = 0
  let searchTimer: ReturnType<typeof setTimeout> | null = null

  function buildParams(pageNo: number): GalleryFilterParams {
    return {
      q: filters.value.q || undefined,
      profile_name: filters.value.profile_name || undefined,
      provider: filters.value.provider || undefined,
      model: filters.value.model || undefined,
      min_rating: filters.value.min_rating || undefined,
      unrated: filters.value.unrated || undefined,
      time_preset: filters.value.time_preset || undefined,
      date_from: filters.value.date_from || undefined,
      date_to: filters.value.date_to || undefined,
      category_ids: filters.value.category_ids.length > 0 ? filters.value.category_ids : undefined,
      artbook_token: filters.value.artbook_token || undefined,
      collapse_stacks: filters.value.collapse_stacks,
      page: pageNo,
      page_size: PAGE_SIZE,
    }
  }

  /**
   * Load assets. With ``resetPage`` the list restarts at page 1 (filter change);
   * otherwise every page loaded so far is refreshed (e.g. after stacking or deleting).
   */
  async function fetchAssets(resetPage = false) {
    if (searchTimer) {
      clearTimeout(searchTimer)
      searchTimer = null
    }
    const seq = ++requestSeq
    const pagesToLoad = resetPage ? 1 : Math.max(1, page.value)
    isLoading.value = true
    try {
      const collected: Asset[] = []
      const seen = new Set<number>()
      let lastTotal = 0
      let lastTotalPages = 1
      let loadedPages = 0
      for (let pageNo = 1; pageNo <= pagesToLoad; pageNo++) {
        const res = await galleryApi.listAssets(buildParams(pageNo))
        if (seq !== requestSeq) return
        res.assets.forEach((asset) => {
          if (!seen.has(asset.id)) {
            seen.add(asset.id)
            collected.push(asset)
          }
        })
        lastTotal = res.total
        lastTotalPages = res.total_pages || 1
        loadedPages = pageNo
        if (pageNo >= lastTotalPages) break
      }
      assets.value = collected
      total.value = lastTotal
      totalPages.value = lastTotalPages
      page.value = Math.max(1, loadedPages)
      hasLoadedOnce.value = true
    } catch (_error) {
      if (seq === requestSeq && resetPage) {
        assets.value = []
        total.value = 0
      }
    } finally {
      if (seq === requestSeq) {
        isLoading.value = false
      }
    }
  }

  const hasMore = computed(() => page.value < totalPages.value)

  /** Append the next page (infinite scroll). */
  async function loadMore() {
    if (isLoading.value || isLoadingMore.value || !hasMore.value) return
    const seq = requestSeq
    isLoadingMore.value = true
    try {
      const res = await galleryApi.listAssets(buildParams(page.value + 1))
      if (seq !== requestSeq) return
      const known = new Set(assets.value.map((a) => a.id))
      assets.value = [...assets.value, ...res.assets.filter((a) => !known.has(a.id))]
      page.value += 1
      total.value = res.total
      totalPages.value = res.total_pages || page.value
    } catch (_error) {
      toastStore.error('Could not load more images.')
    } finally {
      isLoadingMore.value = false
    }
  }

  /** Debounced reload for free-text search input. */
  function searchDebounced(delayMs = 300) {
    if (searchTimer) clearTimeout(searchTimer)
    searchTimer = setTimeout(() => {
      searchTimer = null
      fetchAssets(true)
    }, delayMs)
  }

  /** Assets in display order, with expanded stacks flattened into their items. */
  const displayedAssets = computed<Asset[]>(() => {
    if (!filters.value.collapse_stacks) {
      return assets.value
    }
    const result: Asset[] = []
    for (const asset of assets.value) {
      if (asset.stack_id && isStackExpanded(asset.stack_id) && asset.stack_items && asset.stack_items.length > 0) {
        result.push(...asset.stack_items)
      } else {
        result.push(asset)
      }
    }
    return result
  })

  /** Move the detail modal to the previous/next asset; loads more pages at the end. */
  async function openAdjacentAsset(delta: number) {
    if (!activeAsset.value) return
    const list = displayedAssets.value
    const index = list.findIndex((a) => a.id === activeAsset.value?.id)
    if (index === -1) return
    if (index + delta >= list.length && hasMore.value) {
      await loadMore()
    }
    const updated = displayedAssets.value
    const target = Math.max(0, Math.min(updated.length - 1, index + delta))
    if (updated[target] && updated[target].id !== activeAsset.value?.id) {
      activeAsset.value = updated[target]
    }
  }

  const lastSelectedAssetId = ref<number | null>(null)

  function toggleSelectAsset(id: number, isRange = false) {
    if (isRange && lastSelectedAssetId.value !== null && lastSelectedAssetId.value !== id) {
      const idx1 = assets.value.findIndex((a) => a.id === lastSelectedAssetId.value)
      const idx2 = assets.value.findIndex((a) => a.id === id)
      if (idx1 !== -1 && idx2 !== -1) {
        const start = Math.min(idx1, idx2)
        const end = Math.max(idx1, idx2)
        const rangeIds = assets.value.slice(start, end + 1).map((a) => a.id)
        const newSet = new Set([...selectedAssetIds.value, ...rangeIds])
        selectedAssetIds.value = Array.from(newSet)
        lastSelectedAssetId.value = id
        return
      }
    }

    if (selectedAssetIds.value.includes(id)) {
      selectedAssetIds.value = selectedAssetIds.value.filter((item) => item !== id)
    } else {
      selectedAssetIds.value.push(id)
    }
    lastSelectedAssetId.value = id
  }

  /** Replace (or extend, when ``additive``) the selection, e.g. after a rubber-band drag. */
  function setSelection(ids: number[], additive = false) {
    const next = additive ? new Set([...selectedAssetIds.value, ...ids]) : new Set(ids)
    selectedAssetIds.value = Array.from(next)
    lastSelectedAssetId.value = ids.length ? ids[ids.length - 1] : lastSelectedAssetId.value
  }

  function findLoadedAsset(id: number): Asset | undefined {
    for (const asset of assets.value) {
      if (asset.id === id) return asset
      const nested = asset.stack_items?.find((item) => item.id === id)
      if (nested) return nested
    }
    return undefined
  }

  /** Selected assets in selection order (also resolves items inside expanded stacks). */
  const selectedAssets = computed<Asset[]>(() =>
    selectedAssetIds.value.map(findLoadedAsset).filter((a): a is Asset => !!a)
  )

  /** Rate several assets at once (keyboard rating of a selection). */
  async function rateAssets(ids: number[], rating: number) {
    const targets = ids.map(findLoadedAsset).filter((a): a is Asset => !!a)
    if (targets.length === 0) return
    const results = await Promise.allSettled(targets.map((a) => galleryApi.rateAsset(a.id, rating)))
    let ok = 0
    results.forEach((result, index) => {
      if (result.status === 'fulfilled') {
        targets[index].rating = result.value.rating
        if (activeAsset.value?.id === targets[index].id) activeAsset.value.rating = result.value.rating
        ok++
      }
    })
    if (ok < targets.length) toastStore.error(`${targets.length - ok} ratings could not be saved.`)
    else if (targets.length > 1) toastStore.success(`${ok} images rated ${rating} ★.`)
  }

  const isZipDownloading = ref(false)

  async function downloadSelectedZip() {
    if (selectedAssetIds.value.length === 0 || isZipDownloading.value) return
    isZipDownloading.value = true
    try {
      const { blob, filename } = await galleryApi.downloadZip(selectedAssetIds.value)
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      setTimeout(() => URL.revokeObjectURL(url), 1000)
    } catch (_error) {
      toastStore.error('ZIP download failed.')
    } finally {
      isZipDownloading.value = false
    }
  }

  function selectAll() {
    selectedAssetIds.value = assets.value.map((a) => a.id)
  }

  function clearSelection() {
    selectedAssetIds.value = []
    lastSelectedAssetId.value = null
  }

  function openDetailModal(asset: Asset) {
    activeAsset.value = asset
    isDetailModalOpen.value = true
  }

  function closeDetailModal() {
    activeAsset.value = null
    isDetailModalOpen.value = false
  }

  async function rateAsset(asset: Asset, rating: number) {
    try {
      const res = await galleryApi.rateAsset(asset.id, rating)
      asset.rating = res.rating
      if (activeAsset.value && activeAsset.value.id === asset.id) {
        activeAsset.value.rating = res.rating
      }
    } catch (_error) {
      toastStore.error('Failed to save rating.')
    }
  }

  async function toggleFavorite(asset: Asset) {
    try {
      const res = await galleryApi.toggleFavorite(asset.id)
      asset.is_favorite = res.is_favorite
      if (activeAsset.value && activeAsset.value.id === asset.id) {
        activeAsset.value.is_favorite = res.is_favorite
      }
    } catch (_error) {
      toastStore.error('Failed to update favorite.')
    }
  }

  async function deleteAsset(id: number) {
    try {
      await galleryApi.deleteAsset(id)
      assets.value = assets.value.filter((a) => a.id !== id)
      selectedAssetIds.value = selectedAssetIds.value.filter((item) => item !== id)
      if (activeAsset.value?.id === id) {
        closeDetailModal()
      }
      toastStore.success('Image deleted.')
    } catch (_error) {
      toastStore.error('Could not delete image.')
    }
  }

  async function bulkDelete() {
    if (selectedAssetIds.value.length === 0) return
    try {
      const res = await galleryApi.bulkDelete(selectedAssetIds.value)
      assets.value = assets.value.filter((a) => !selectedAssetIds.value.includes(a.id))
      toastStore.success(`${res.deleted_count} images deleted.`)
      clearSelection()
    } catch (_error) {
      toastStore.error('Failed to delete images.')
    }
  }

  async function createCategory(name: string, color?: string) {
    try {
      const newCat = await galleryApi.createCategory(name, color)
      categories.value.push(newCat)
      categories.value.sort((a, b) => a.name.localeCompare(b.name))
      toastStore.success(`Category "${newCat.name}" created.`)
      return newCat
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to create category.')
      throw error
    }
  }

  async function updateCategory(id: number, name: string, color?: string) {
    try {
      const updated = await galleryApi.updateCategory(id, name, color)
      const index = categories.value.findIndex((c) => c.id === id)
      if (index !== -1) {
        categories.value[index] = { ...categories.value[index], ...updated }
      }
      toastStore.success('Category updated.')
      return updated
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to update category.')
      throw error
    }
  }

  async function deleteCategory(id: number) {
    try {
      await galleryApi.deleteCategory(id)
      categories.value = categories.value.filter((c) => c.id !== id)
      assets.value.forEach((a) => {
        if (a.category_ids) {
          a.category_ids = a.category_ids.filter((cid) => cid !== id)
        }
      })
      if (activeAsset.value?.category_ids) {
        activeAsset.value.category_ids = activeAsset.value.category_ids.filter((cid) => cid !== id)
      }
      toastStore.success('Category deleted.')
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to delete category.')
      throw error
    }
  }

  async function updateAssetCategories(assetId: number, categoryIds: number[]) {
    try {
      const res = await galleryApi.updateCategories(assetId, categoryIds)
      const asset = assets.value.find((a) => a.id === assetId)
      if (asset) {
        asset.category_ids = categoryIds
      }
      if (activeAsset.value && activeAsset.value.id === assetId) {
        activeAsset.value.category_ids = categoryIds
      }
      toastStore.success('Categories updated.')
      return res
    } catch (_error) {
      toastStore.error('Failed to update categories.')
    }
  }

  async function bulkCategorize(categoryIds: number[], mode: 'replace' | 'append' = 'replace') {
    if (selectedAssetIds.value.length === 0) return
    try {
      await galleryApi.bulkCategorize(selectedAssetIds.value, categoryIds, mode)
      assets.value.forEach((a) => {
        if (selectedAssetIds.value.includes(a.id)) {
          if (mode === 'append') {
            const set = new Set([...(a.category_ids || []), ...categoryIds])
            a.category_ids = Array.from(set)
          } else {
            a.category_ids = [...categoryIds]
          }
        }
      })
      toastStore.success(`${selectedAssetIds.value.length} images updated.`)
      loadCategories()
    } catch (_error) {
      toastStore.error('Failed to batch categorize.')
    }
  }

  async function stackSelected() {
    if (selectedAssetIds.value.length < 2) return
    try {
      const res = await galleryApi.stackAssets(selectedAssetIds.value)
      toastStore.success(`Created stack with ${res.count} images.`)
      clearSelection()
      await fetchAssets()
    } catch (_error) {
      toastStore.error('Failed to create stack.')
    }
  }

  async function unstackSelected() {
    if (selectedAssetIds.value.length === 0) return
    try {
      await galleryApi.unstackAssets({ assetIds: selectedAssetIds.value })
      toastStore.success('Unstacked selected images.')
      clearSelection()
      await fetchAssets()
    } catch (_error) {
      toastStore.error('Failed to unstack images.')
    }
  }

  async function unstackById(stackId: string) {
    try {
      await galleryApi.unstackAssets({ stackId })
      expandedStackIds.value.delete(stackId)
      toastStore.success('Stack dissolved.')
      if (activeAsset.value?.stack_id === stackId) {
        activeAsset.value.stack_id = null
        activeAsset.value.stack_count = 1
        activeAsset.value.stack_items = []
      }
      await fetchAssets()
    } catch (_error) {
      toastStore.error('Failed to dissolve stack.')
    }
  }

  async function removeAssetFromStack(assetId: number) {
    try {
      await galleryApi.unstackAssets({ assetIds: [assetId] })
      toastStore.success('Removed from stack.')
      if (activeAsset.value?.id === assetId) {
        activeAsset.value.stack_id = null
        activeAsset.value.stack_count = 1
        activeAsset.value.stack_items = []
      } else if (activeAsset.value?.stack_items) {
        activeAsset.value.stack_items = activeAsset.value.stack_items.filter((item) => item.id !== assetId)
        activeAsset.value.stack_count = activeAsset.value.stack_items.length
      }
      await fetchAssets()
    } catch (_error) {
      toastStore.error('Failed to remove from stack.')
    }
  }

  async function setStackCover(assetId: number) {
    try {
      await galleryApi.setStackCover(assetId)
      toastStore.success('Set as stack cover.')
      if (activeAsset.value) {
        const fresh = await galleryApi.getAsset(assetId)
        activeAsset.value = fresh
      }
      await fetchAssets()
    } catch (_error) {
      toastStore.error('Failed to set stack cover.')
    }
  }

  function resetFilters() {
    // View preferences (size / crop / grouping) are not filters and survive a reset.
    const { thumb_size, thumb_fit, group_by_date } = filters.value
    filters.value = { ...defaultFilters(), thumb_size, thumb_fit, group_by_date }
    fetchAssets(true)
  }

  return {
    assets,
    categories,
    total,
    page,
    totalPages,
    isLoading,
    isLoadingMore,
    hasLoadedOnce,
    hasMore,
    activeFilterCount,
    displayedAssets,
    facets,
    loadFacets,
    filtersToQuery,
    applyQuery,
    presets,
    loadPresets,
    savePreset,
    deletePreset,
    applyPreset,
    setSelection,
    selectedAssets,
    rateAssets,
    isZipDownloading,
    downloadSelectedZip,
    loadMore,
    searchDebounced,
    openAdjacentAsset,
    selectedAssetIds,
    activeAsset,
    isDetailModalOpen,
    filters,
    expandedStackIds,
    isStackExpanded,
    toggleStackExpanded,
    expandAllStacks,
    collapseAllStacks,
    stackSelected,
    unstackSelected,
    unstackById,
    removeAssetFromStack,
    setStackCover,
    loadCategories,
    fetchAssets,
    toggleSelectAsset,
    selectAll,
    clearSelection,
    openDetailModal,
    closeDetailModal,
    rateAsset,
    toggleFavorite,
    deleteAsset,
    bulkDelete,
    createCategory,
    updateCategory,
    deleteCategory,
    updateAssetCategories,
    bulkCategorize,
    resetFilters,
  }
})

