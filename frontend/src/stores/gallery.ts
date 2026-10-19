import { defineStore } from 'pinia'
import { ref } from 'vue'
import { galleryApi, type GalleryFilterParams } from '@/api/gallery'
import { useToastStore } from './toast'
import type { Asset, Category, GalleryFilterState } from '@/types'

export const useGalleryStore = defineStore('gallery', () => {
  const toastStore = useToastStore()

  const assets = ref<Asset[]>([])
  const categories = ref<Category[]>([])
  const total = ref<number>(0)
  const page = ref<number>(1)
  const totalPages = ref<number>(1)
  const isLoading = ref<boolean>(false)

  // Selection state
  const selectedAssetIds = ref<number[]>([])

  // Modal / Detail state
  const activeAsset = ref<Asset | null>(null)
  const isDetailModalOpen = ref<boolean>(false)

  // Filters
  const filters = ref<GalleryFilterState>({
    q: '',
    profile_name: '',
    provider: '',
    min_rating: null,
    unrated: false,
    time_preset: '',
    date_from: '',
    date_to: '',
    category_ids: [],
    thumb_size: 'md',
    collapse_stacks: true,
  })

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

  async function fetchAssets(resetPage = false) {
    if (resetPage) {
      page.value = 1
    }
    isLoading.value = true
    try {
      const params: GalleryFilterParams = {
        q: filters.value.q || undefined,
        profile_name: filters.value.profile_name || undefined,
        provider: filters.value.provider || undefined,
        min_rating: filters.value.min_rating || undefined,
        unrated: filters.value.unrated || undefined,
        time_preset: filters.value.time_preset || undefined,
        date_from: filters.value.date_from || undefined,
        date_to: filters.value.date_to || undefined,
        category_ids: filters.value.category_ids.length > 0 ? filters.value.category_ids : undefined,
        artbook_token: filters.value.artbook_token || undefined,
        collapse_stacks: filters.value.collapse_stacks,
        page: page.value,
        page_size: 40,
      }

      const res = await galleryApi.listAssets(params)
      assets.value = res.assets
      total.value = res.total
      totalPages.value = res.total_pages
    } catch (_error) {
      assets.value = []
    } finally {
      isLoading.value = false
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
    filters.value = {
      q: '',
      profile_name: '',
      provider: '',
      min_rating: null,
      unrated: false,
      time_preset: '',
      date_from: '',
      date_to: '',
      category_ids: [],
      thumb_size: 'md',
      collapse_stacks: true,
    }
    fetchAssets(true)
  }

  return {
    assets,
    categories,
    total,
    page,
    totalPages,
    isLoading,
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

