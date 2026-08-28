<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useProfilesStore } from '@/stores/profiles'
import { useGenerateStore } from '@/stores/generate'
import Modal from '@/components/ui/Modal.vue'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import Textarea from '@/components/ui/Textarea.vue'

const profilesStore = useProfilesStore()
const generateStore = useGenerateStore()

const formData = ref({
  id: 0,
  name: '',
  description: '',
  system_prompt: '',
  negative_prompt: '',
  default_aspect_ratio: '1:1',
  default_resolution: '1K',
  default_model_config_id: null as number | null,
  upscale_provider: null as string | null,
  upscale_model: null as string | null,
  upscale_factor: null as number | null,
})

const aspectRatios = ['1:1', '16:9', '9:16', '4:3', '3:4', '21:9']
const isSubmitting = ref(false)

onMounted(() => {
  generateStore.loadModelsAndStyles()
})

watch(
  () => profilesStore.activeProfile,
  (profile) => {
    if (profile) {
      formData.value = {
        id: profile.id || 0,
        name: profile.name || '',
        description: profile.description || '',
        system_prompt: profile.system_prompt || '',
        negative_prompt: profile.negative_prompt || '',
        default_aspect_ratio: profile.default_aspect_ratio || '1:1',
        default_resolution: profile.default_resolution || '1K',
        default_model_config_id: profile.default_model_config_id || null,
        upscale_provider: profile.upscale_provider || null,
        upscale_model: profile.upscale_model || null,
        upscale_factor: profile.upscale_factor || null,
      }
    }
  },
  { immediate: true }
)

async function handleSubmit() {
  if (!formData.value.name.trim()) return
  isSubmitting.value = true
  try {
    await profilesStore.saveProfile(formData.value)
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <Modal
    :open="profilesStore.isEditorOpen"
    :title="profilesStore.isEditing ? 'Profil bearbeiten' : 'Neues Profil erstellen'"
    size="lg"
    @update:open="profilesStore.closeEditorModal"
  >
    <form @submit.prevent="handleSubmit" class="space-y-4 text-xs">
      <Input
        label="Profil Name"
        placeholder="z.B. Cinematic Portrait"
        v-model="formData.name"
        required
      />

      <Input
        label="Beschreibung"
        placeholder="Kurze Beschreibung des Profils..."
        v-model="formData.description"
      />

      <Textarea
        label="System Prompt / Basis-Stil"
        placeholder="Wird automatisch jedem Prompt vorangestellt..."
        v-model="formData.system_prompt"
        :rows="3"
      />

      <Textarea
        label="Standard Negativer Prompt"
        placeholder="Standardmäßig zu vermeidende Begriffe..."
        v-model="formData.negative_prompt"
        :rows="2"
      />

      <div>
        <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500 mb-1.5">
          Standard Format (Seitenverhältnis)
        </label>
        <select
          v-model="formData.default_aspect_ratio"
          class="w-full rounded-xl border border-slate-300/80 bg-white/80 px-3 py-2 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100"
        >
          <option v-for="ar in aspectRatios" :key="ar" :value="ar">{{ ar }}</option>
        </select>
      </div>
    </form>

    <template #footer>
      <Button variant="secondary" size="sm" @click="profilesStore.closeEditorModal">
        Abbrechen
      </Button>
      <Button
        variant="primary"
        size="sm"
        :loading="isSubmitting"
        @click="handleSubmit"
      >
        Speichern
      </Button>
    </template>
  </Modal>
</template>
