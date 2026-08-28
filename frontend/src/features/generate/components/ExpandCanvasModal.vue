<script setup lang="ts">
import { ref } from 'vue'
import { generationApi } from '@/api/generation'
import { useToastStore } from '@/stores/toast'
import Modal from '@/components/ui/Modal.vue'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import type { Asset } from '@/types'

interface Props {
  open: boolean
  asset: Asset | null
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'submitted', jobId: number): void
}>()

const toastStore = useToastStore()

const prompt = ref('')
const selectedAspectRatio = ref('16:9')
const isSubmitting = ref(false)

const aspectRatios = ['16:9', '9:16', '21:9', '4:3', '3:4', '1:1']

async function handleSubmit() {
  if (!props.asset) return

  isSubmitting.value = true
  try {
    const res = await generationApi.expandImage({
      asset_id: props.asset.id,
      prompt: prompt.value.trim() || props.asset.prompt,
      aspect_ratio: selectedAspectRatio.value,
    })

    toastStore.success('Outpainting gestartet!')
    emit('submitted', res.job_id)
    emit('update:open', false)
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Fehler beim Starten von Outpainting.')
  } finally {
    isSubmitting.value = false
  }
}
</script>

<template>
  <Modal :open="open" title="Bild erweitern / Outpainting" size="lg" @update:open="emit('update:open', $event)">
    <div v-if="asset" class="space-y-4 text-xs">
      <!-- Preview Image -->
      <div class="flex justify-center bg-slate-900/80 rounded-2xl p-4 border border-slate-200 dark:border-white/10">
        <img :src="asset.thumbnail_url || asset.image_url" alt="" class="max-h-56 rounded-xl object-contain shadow-lg" />
      </div>

      <!-- Target Aspect Ratio -->
      <div>
        <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500 mb-1.5">
          Ziel-Seitenverhältnis
        </label>
        <div class="flex flex-wrap gap-1.5">
          <button
            v-for="ar in aspectRatios"
            :key="ar"
            type="button"
            @click="selectedAspectRatio = ar"
            :class="[
              'px-3 py-1 rounded-lg font-semibold transition-all border',
              selectedAspectRatio === ar
                ? 'bg-sky-500 text-white border-sky-500 shadow-sm'
                : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:border-white/10',
            ]"
          >
            {{ ar }}
          </button>
        </div>
      </div>

      <!-- Expansion prompt -->
      <Input
        label="Prompt für die Erweiterung (Optional)"
        placeholder="Beschreibung für den hinzugefügten Bereich..."
        v-model="prompt"
      />
    </div>

    <template #footer>
      <Button variant="secondary" size="sm" @click="emit('update:open', false)">
        Abbrechen
      </Button>
      <Button
        variant="primary"
        size="sm"
        :loading="isSubmitting"
        @click="handleSubmit"
      >
        Erweitern
      </Button>
    </template>
  </Modal>
</template>
