<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useProfilesStore } from '@/stores/profiles'
import ProfileCard from './components/ProfileCard.vue'
import ProfileEditorModal from './components/ProfileEditorModal.vue'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import LoadingState from '@/components/ui/LoadingState.vue'
import { Plus, Search, SlidersHorizontal } from 'lucide-vue-next'

const profilesStore = useProfilesStore()
const searchQuery = ref('')

onMounted(() => {
  profilesStore.fetchProfiles()
})

const filteredProfiles = computed(() => {
  if (!searchQuery.value.trim()) return profilesStore.profiles
  const q = searchQuery.value.toLowerCase()
  return profilesStore.profiles.filter(
    (p) => p.name.toLowerCase().includes(q) || p.description?.toLowerCase().includes(q)
  )
})
</script>

<template>
  <div class="h-full overflow-y-auto space-y-6 pb-20 pr-1">
    <!-- Top Action Bar -->
    <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-2xl border border-slate-200/80 bg-white/70 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/70 shadow-sm">
      <div class="space-y-0.5">
        <h2 class="text-base font-bold text-slate-900 dark:text-white">Profiles</h2>
        <p class="text-xs text-slate-500">
          Define presets, system prompts, and default parameters for different creative workflows.
        </p>
      </div>

      <div class="flex items-center gap-3 w-full sm:w-auto">
        <Input
          v-model="searchQuery"
          type="search"
          size="sm"
          class="w-full sm:w-48"
          placeholder="Filter profiles..."
          aria-label="Filter profiles"
        >
          <template #prefix><Search class="size-3.5" aria-hidden="true" /></template>
        </Input>

        <Button variant="primary" size="sm" @click="profilesStore.openCreateModal" class="shrink-0">
          <template #icon><Plus class="size-4" aria-hidden="true" /></template>
          New Profile
        </Button>
      </div>
    </div>

    <!-- Loading -->
    <LoadingState v-if="profilesStore.isLoading" label="Loading profiles…" />

    <!-- Empty State -->
    <EmptyState
      v-else-if="filteredProfiles.length === 0"
      :icon="SlidersHorizontal"
      :title="searchQuery ? 'No profiles match your filter' : 'No profiles yet'"
      :description="searchQuery ? 'Try a different name.' : 'Create your first profile to save workflows and default parameters.'"
    >
      <template #actions>
        <Button v-if="searchQuery" variant="secondary" size="sm" @click="searchQuery = ''">Clear filter</Button>
        <Button v-else variant="primary" size="sm" @click="profilesStore.openCreateModal">Create Profile</Button>
      </template>
    </EmptyState>

    <!-- Profiles Grid -->
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
      <ProfileCard
        v-for="profile in filteredProfiles"
        :key="profile.id"
        :profile="profile"
      />
    </div>

    <!-- Profile Editor Modal -->
    <ProfileEditorModal />
  </div>
</template>
