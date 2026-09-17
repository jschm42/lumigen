<script setup lang="ts">
import { ref, watch, onMounted } from 'vue'
import { useProfilesStore } from '@/stores/profiles'
import { useGenerateStore } from '@/stores/generate'
import { galleryApi } from '@/api/gallery'
import type { Category } from '@/types'
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
  upscale_provider: null as string | null,
  upscale_model: null as string | null,
  upscale_factor: null as number | null,
  category_ids: [] as number[],
})

const aspectRatios = ['1:1', '16:9', '9:16', '4:3', '3:4', '21:9']
const availableCategories = ref<Category[]>([])
const isLoadingCategories = ref(false)
const newCategoryName = ref('')
const isCreatingCategory = ref(false)
const isSubmitting = ref(false)

async function loadCategories() {
  isLoadingCategories.value = true
  try {
    availableCategories.value = await galleryApi.listCategories()
  } catch (_e) {
    availableCategories.value = []
  } finally {
    isLoadingCategories.value = false
  }
}

onMounted(() => {
  generateStore.loadModelsAndStyles()
  loadCategories()
})

watch(
  () => profilesStore.activeProfile,
  (profile) => {
    if (profile) {
      let initialCatIds: number[] = []
      if (profile.category_ids && Array.isArray(profile.category_ids)) {
        initialCatIds = [...profile.category_ids]
      } else if (profile.categories && Array.isArray(profile.categories)) {
        initialCatIds = profile.categories.map((c: any) => c.id)
      }

      formData.value = {
        id: profile.id || 0,
        name: profile.name || '',
        description: profile.description || '',
        system_prompt: profile.system_prompt || '',
        negative_prompt: profile.negative_prompt || '',
        default_aspect_ratio: profile.default_aspect_ratio || '1:1',
        default_resolution: profile.default_resolution || '1K',
        upscale_provider: profile.upscale_provider || null,
        upscale_model: profile.upscale_model || null,
        upscale_factor: profile.upscale_factor || null,
        category_ids: initialCatIds,
      }
    }
  },
  { immediate: true }
)

function toggleCategory(catId: number) {
  if (formData.value.category_ids.includes(catId)) {
    formData.value.category_ids = formData.value.category_ids.filter((id) => id !== catId)
  } else {
    formData.value.category_ids.push(catId)
  }
}

async function handleQuickCreateCategory() {
  const name = newCategoryName.value.trim()
  if (!name) return
  isCreatingCategory.value = true
  try {
    const created = await galleryApi.createCategory(name)
    availableCategories.value.push(created)
    if (!formData.value.category_ids.includes(created.id)) {
      formData.value.category_ids.push(created.id)
    }
    newCategoryName.value = ''
  } catch (_e) {
    // ignore or let store handle
  } finally {
    isCreatingCategory.value = false
  }
}

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
    :title="profilesStore.isEditing ? 'Edit Profile' : 'Create New Profile'"
    size="lg"
    @update:open="profilesStore.closeEditorModal"
  >
    <form @submit.prevent="handleSubmit" class="space-y-4 text-xs">
      <Input
        label="Profile Name"
        placeholder="e.g. Cinematic Portrait"
        v-model="formData.name"
        required
      />

      <Input
        label="Description"
        placeholder="Short description of the profile..."
        v-model="formData.description"
      />

      <Textarea
        label="System Prompt / Base Style"
        placeholder="Automatically prepended to every prompt..."
        v-model="formData.system_prompt"
        :rows="3"
      />

      <Textarea
        label="Default Negative Prompt"
        placeholder="Default terms to avoid..."
        v-model="formData.negative_prompt"
        :rows="2"
      />

      <div>
        <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500 mb-1.5">
          Default Format (Aspect Ratio)
        </label>
        <select
          v-model="formData.default_aspect_ratio"
          class="w-full rounded-xl border border-slate-300/80 bg-white/80 px-3 py-2 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100"
        >
          <option v-for="ar in aspectRatios" :key="ar" :value="ar">{{ ar }}</option>
        </select>
      </div>

      <!-- Categories Section -->
      <div class="space-y-2 pt-2 border-t border-slate-200/80 dark:border-white/10">
        <div class="flex items-center justify-between">
          <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500">
            Categories
          </label>
          <span v-if="formData.category_ids.length > 0" class="text-[10px] font-medium text-sky-600 dark:text-sky-400">
            {{ formData.category_ids.length }} selected
          </span>
        </div>
        <p class="text-[11px] text-slate-500 dark:text-slate-400">
          Images generated with this profile will be automatically assigned to these categories.
        </p>

        <!-- Category Chips -->
        <div v-if="isLoadingCategories" class="py-2 text-slate-400">
          Loading categories...
        </div>
        <div v-else class="flex flex-wrap gap-2 max-h-40 overflow-y-auto py-1">
          <button
            v-for="cat in availableCategories"
            :key="cat.id"
            type="button"
            @click="toggleCategory(cat.id)"
            :class="[
              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-semibold transition-all cursor-pointer shadow-sm',
              formData.category_ids.includes(cat.id)
                ? 'bg-sky-500 border-sky-500 text-white shadow-sky-500/20'
                : 'bg-white border-slate-300/80 text-slate-700 hover:border-sky-400 dark:bg-slate-800 dark:border-white/10 dark:text-slate-200 dark:hover:border-white/30',
            ]"
          >
            <span>🏷️</span>
            <span>{{ cat.name }}</span>
            <span v-if="formData.category_ids.includes(cat.id)" class="text-[10px] font-bold">✓</span>
          </button>
          <div v-if="availableCategories.length === 0" class="text-slate-400 italic py-1">
            No categories available yet.
          </div>
        </div>

        <!-- Quick create category -->
        <div class="flex items-center gap-2 pt-1">
          <input
            v-model="newCategoryName"
            type="text"
            placeholder="Add new category..."
            class="flex-1 rounded-xl border border-slate-300/80 bg-white/80 px-3 py-1.5 text-xs text-slate-900 placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-sky-500 dark:border-white/10 dark:bg-slate-900/80 dark:text-slate-100"
            @keydown.enter.prevent="handleQuickCreateCategory"
          />
          <Button
            type="button"
            variant="secondary"
            size="xs"
            :loading="isCreatingCategory"
            :disabled="!newCategoryName.trim()"
            @click="handleQuickCreateCategory"
          >
            + Add
          </Button>
        </div>
      </div>
    </form>

    <template #footer>
      <Button variant="secondary" size="sm" @click="profilesStore.closeEditorModal">
        Cancel
      </Button>
      <Button
        variant="primary"
        size="sm"
        :loading="isSubmitting"
        @click="handleSubmit"
      >
        Save
      </Button>
    </template>
  </Modal>
</template>
