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
  })

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

