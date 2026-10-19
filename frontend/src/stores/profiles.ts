import { defineStore } from 'pinia'
import { ref } from 'vue'
import { profilesApi } from '@/api/profiles'
import { useToastStore } from './toast'
import type { Profile } from '@/types'

export const useProfilesStore = defineStore('profiles', () => {
  const toastStore = useToastStore()

  const profiles = ref<Profile[]>([])
  const activeProfile = ref<Profile | null>(null)
  const isEditing = ref<boolean>(false)
  const isEditorOpen = ref<boolean>(false)
  const isLoading = ref<boolean>(false)

  async function fetchProfiles() {
    isLoading.value = true
    try {
      profiles.value = await profilesApi.listProfiles()
    } catch (_error) {
      profiles.value = []
    } finally {
      isLoading.value = false
    }
  }

  function openCreateModal() {
    activeProfile.value = {
      id: 0,
      name: '',
      description: '',
      system_prompt: '',
      negative_prompt: '',
      default_aspect_ratio: '1:1',
      default_resolution: '1K',
      upscale_provider: null,
      upscale_model: null,
      upscale_factor: null,
      category_ids: [],
    }
    isEditing.value = false
    isEditorOpen.value = true
  }

  function openEditModal(profile: Profile) {
    activeProfile.value = { ...profile }
    isEditing.value = true
    isEditorOpen.value = true
  }

  function closeEditorModal() {
    activeProfile.value = null
    isEditorOpen.value = false
  }

  async function saveProfile(data: Partial<Profile>) {
    try {
      if (isEditing.value && data.id) {
        const updated = await profilesApi.updateProfile(data.id, data)
        const index = profiles.value.findIndex((p) => p.id === data.id)
        if (index !== -1) profiles.value[index] = updated
        toastStore.success('Profile updated.')
      } else {
        const created = await profilesApi.createProfile(data)
        profiles.value.push(created)
        toastStore.success('Profile created.')
      }
      closeEditorModal()
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Failed to save profile.')
    }
  }

  async function deleteProfile(id: number) {
    try {
      await profilesApi.deleteProfile(id)
      profiles.value = profiles.value.filter((p) => p.id !== id)
      toastStore.success('Profile deleted.')
    } catch (_error) {
      toastStore.error('Failed to delete profile.')
    }
  }

  return {
    profiles,
    activeProfile,
    isEditing,
    isEditorOpen,
    isLoading,
    fetchProfiles,
    openCreateModal,
    openEditModal,
    closeEditorModal,
    saveProfile,
    deleteProfile,
  }
})
