<script setup lang="ts">
import { onMounted, ref, computed } from 'vue'
import { useProfilesStore } from '@/stores/profiles'
import ProfileCard from './components/ProfileCard.vue'
import ProfileEditorModal from './components/ProfileEditorModal.vue'
import Button from '@/components/ui/Button.vue'
import Spinner from '@/components/ui/Spinner.vue'

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
  <div class="space-y-6 pb-20">
    <!-- Top Action Bar -->
    <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 p-4 rounded-2xl border border-slate-200/80 bg-white/70 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/70 shadow-sm">
      <div class="space-y-0.5">
        <h2 class="text-base font-bold text-slate-900 dark:text-white">Profile</h2>
        <p class="text-xs text-slate-500">
          Definiere Voreinstellungen, System-Prompts und Modelle für verschiedene Bildstile.
        </p>
      </div>

      <div class="flex items-center gap-3 w-full sm:w-auto">
        <input
          type="text"
          v-model="searchQuery"
          placeholder="Profile filtern..."
          class="w-full sm:w-48 rounded-xl border border-slate-300/80 bg-white/80 px-3 py-1.5 text-xs text-slate-900 placeholder-slate-400 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100 focus:outline-none focus:ring-1 focus:ring-sky-500"
        />

        <Button variant="primary" size="sm" @click="profilesStore.openCreateModal" class="shrink-0">
          <template #icon>+</template>
          Neues Profil
        </Button>
      </div>
    </div>

    <!-- Loading -->
    <div v-if="profilesStore.isLoading" class="py-20 flex justify-center">
      <Spinner size="lg" class="text-sky-500" />
    </div>

    <!-- Empty State -->
    <div
      v-else-if="filteredProfiles.length === 0"
      class="py-20 text-center space-y-3"
    >
      <div class="text-4xl">🎭</div>
      <h3 class="text-base font-bold text-slate-800 dark:text-white">Keine Profile gefunden</h3>
      <p class="text-xs text-slate-500 max-w-sm mx-auto">
        Erstelle dein erstes Profil, um Workflows und Standardparameter zu speichern.
      </p>
      <Button variant="primary" size="sm" @click="profilesStore.openCreateModal">
        Profil anlegen
      </Button>
    </div>

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
