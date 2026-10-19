<script setup lang="ts">
import { ref } from 'vue'
import { generationApi } from '@/api/generation'
import { useGenerateStore } from '@/stores/generate'
import { useToastStore } from '@/stores/toast'
import Modal from '@/components/ui/Modal.vue'
import Button from '@/components/ui/Button.vue'
import Textarea from '@/components/ui/Textarea.vue'

interface Props {
  open: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

const generateStore = useGenerateStore()
const toastStore = useToastStore()

const isEnhancing = ref(false)
const enhancedPrompt = ref('')
const selectedLlm = ref('gemini-2.5-flash')

async function runEnhancement() {
  if (!generateStore.prompt.trim()) {
    toastStore.warning('Please enter an initial prompt first.')
    return
  }

  isEnhancing.value = true
  try {
    const res = await generationApi.enhancePrompt({
      prompt: generateStore.prompt,
      llm_model: selectedLlm.value,
      profile_id: generateStore.selectedProfileId,
    })
    enhancedPrompt.value = res.enhanced_prompt
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Failed to optimize prompt.')
  } finally {
    isEnhancing.value = false
  }
}

function applyEnhanced() {
  if (enhancedPrompt.value.trim()) {
    generateStore.prompt = enhancedPrompt.value.trim()
    toastStore.success('Optimized prompt applied!')
    emit('update:open', false)
  }
}
</script>

<template>
  <Modal :open="open" title="Magic Prompt Enhancement" size="lg" @update:open="emit('update:open', $event)">
    <div class="space-y-4 text-xs">
      <!-- LLM Model Selection -->
      <div class="flex items-center justify-between">
        <span class="text-slate-600 dark:text-slate-400 font-medium">AI model for prompt enhancement:</span>
        <select
          v-model="selectedLlm"
          class="rounded-xl border border-slate-300/80 bg-white px-3 py-1.5 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900 dark:text-slate-100"
        >
          <option value="gemini-2.5-flash">Google Gemini 2.5 Flash</option>
          <option value="openai/gpt-4o-mini">OpenAI GPT-4o Mini</option>
          <option value="anthropic/claude-3.5-haiku">Claude 3.5 Haiku</option>
        </select>
      </div>

      <!-- Original Prompt Preview -->
      <div class="space-y-1">
        <label class="font-semibold uppercase tracking-wider text-[11px] text-slate-500">
          Original Prompt
        </label>
        <div class="p-3 rounded-xl bg-slate-100 dark:bg-slate-800/80 text-slate-800 dark:text-slate-200">
          {{ generateStore.prompt || '(No prompt entered)' }}
        </div>
      </div>

      <!-- Action Button to start enhancement -->
      <div>
        <Button
          variant="primary"
          size="sm"
          :loading="isEnhancing"
          @click="runEnhancement"
        >
          ✨ Optimize prompt now
        </Button>
      </div>

      <!-- Enhanced Result Preview -->
      <div v-if="enhancedPrompt" class="space-y-2 pt-2 border-t border-slate-200 dark:border-white/10">
        <label class="font-semibold uppercase tracking-wider text-[11px] text-sky-500">
          Model suggestion
        </label>
        <Textarea
          v-model="enhancedPrompt"
          :rows="4"
          placeholder="Optimized prompt..."
        />
      </div>
    </div>

    <template #footer>
      <Button variant="secondary" size="sm" @click="emit('update:open', false)">
        Cancel
      </Button>
      <Button
        v-if="enhancedPrompt"
        variant="primary"
        size="sm"
        @click="applyEnhanced"
      >
        Apply prompt
      </Button>
    </template>
  </Modal>
</template>
