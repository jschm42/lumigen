<script setup lang="ts">
import { useProfilesStore } from '@/stores/profiles'
import type { Profile } from '@/types'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'

interface Props {
  profile: Profile
}

const props = defineProps<Props>()

const profilesStore = useProfilesStore()

function handleEdit() {
  profilesStore.openEditModal(props.profile)
}

function handleDelete() {
  if (confirm(`Möchtest du das Profil "${props.profile.name}" wirklich löschen?`)) {
    profilesStore.deleteProfile(props.profile.id)
  }
}
</script>

<template>
  <div class="rounded-2xl border border-slate-200/80 bg-white/70 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/70 p-5 shadow-sm hover:border-sky-400/50 dark:hover:border-sky-400/40 transition-all flex flex-col justify-between text-xs space-y-4">
    <!-- Header -->
    <div class="space-y-2">
      <div class="flex items-start justify-between gap-2">
        <h3 class="font-bold text-sm text-slate-900 dark:text-white truncate">
          {{ profile.name }}
        </h3>
        <Badge v-if="profile.default_aspect_ratio" variant="sky" size="xs">
          {{ profile.default_aspect_ratio }}
        </Badge>
      </div>

      <p v-if="profile.description" class="text-slate-500 dark:text-slate-400 line-clamp-2">
        {{ profile.description }}
      </p>
    </div>

    <!-- Prompts preview -->
    <div class="space-y-2 py-2 border-y border-slate-200/60 dark:border-white/10 flex-1">
      <div v-if="profile.system_prompt" class="space-y-0.5">
        <span class="text-[10px] font-semibold uppercase text-slate-400">System Prompt</span>
        <p class="text-[11px] text-slate-700 dark:text-slate-300 line-clamp-2 bg-slate-100 dark:bg-slate-800/60 p-2 rounded-lg font-mono">
          {{ profile.system_prompt }}
        </p>
      </div>

      <div v-if="profile.negative_prompt" class="space-y-0.5">
        <span class="text-[10px] font-semibold uppercase text-rose-400">Negativ Prompt</span>
        <p class="text-[11px] text-slate-700 dark:text-slate-300 line-clamp-1 bg-rose-50/50 dark:bg-rose-950/20 p-2 rounded-lg font-mono">
          {{ profile.negative_prompt }}
        </p>
      </div>
    </div>

    <!-- Footer Actions -->
    <div class="flex items-center justify-end gap-2 pt-1">
      <Button variant="secondary" size="xs" @click="handleEdit">
        ✏️ Bearbeiten
      </Button>
      <Button variant="danger" size="xs" @click="handleDelete">
        🗑️
      </Button>
    </div>
  </div>
</template>
