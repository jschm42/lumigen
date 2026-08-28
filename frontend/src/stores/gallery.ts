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

  function toggleSelectAsset(id: number) {
    if (selectedAssetIds.value.includes(id)) {
      selectedAssetIds.value = selectedAssetIds.value.filter((item) => item !== id)
    } else {
      selectedAssetIds.value.push(id)
    }
  }

  function selectAll() {
    selectedAssetIds.value = assets.value.map((a) => a.id)
  }

  function clearSelection() {
    selectedAssetIds.value = []
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
      toastStore.error('Bewertung konnte nicht gespeichert werden.')
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
      toastStore.error('Favorit konnte nicht aktualisiert werden.')
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
      toastStore.success('Bild gelöscht.')
    } catch (_error) {
      toastStore.error('Bild konnte nicht gelöscht werden.')
    }
  }

  async function bulkDelete() {
    if (selectedAssetIds.value.length === 0) return
    try {
      const res = await galleryApi.bulkDelete(selectedAssetIds.value)
      assets.value = assets.value.filter((a) => !selectedAssetIds.value.includes(a.id))
      toastStore.success(`${res.deleted_count} Bilder gelöscht.`)
      clearSelection()
    } catch (_error) {
      toastStore.error('Fehler beim Löschen der Bilder.')
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
    resetFilters,
  }
})
