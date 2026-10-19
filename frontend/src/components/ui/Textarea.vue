<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'

interface Props {
  modelValue?: string
  placeholder?: string
  label?: string
  error?: string
  rows?: number
  disabled?: boolean
  autoGrow?: boolean
  id?: string
  name?: string
  maxLength?: number
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  rows: 3,
  disabled: false,
  autoGrow: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'keydown', event: KeyboardEvent): void
}>()

const textareaRef = ref<HTMLTextAreaElement | null>(null)

function adjustHeight() {
  if (!props.autoGrow || !textareaRef.value) return
  textareaRef.value.style.height = 'auto'
  textareaRef.value.style.height = `${Math.min(textareaRef.value.scrollHeight, 280)}px`
}

function handleInput(event: Event) {
  const target = event.target as HTMLTextAreaElement
  emit('update:modelValue', target.value)
  adjustHeight()
}

onMounted(() => {
  adjustHeight()
})

watch(() => props.modelValue, () => {
  adjustHeight()
})
</script>

<template>
  <div class="w-full space-y-1.5">
    <div v-if="label || maxLength" class="flex items-center justify-between">
      <label v-if="label" :for="id" class="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400">
        {{ label }}
      </label>
      <span v-if="maxLength" class="text-[11px] text-slate-400">
        {{ modelValue?.length || 0 }} / {{ maxLength }}
      </span>
    </div>
    <textarea
      ref="textareaRef"
      :id="id"
      :name="name"
      :value="modelValue"
      :placeholder="placeholder"
      :rows="rows"
      :disabled="disabled"
      :maxlength="maxLength"
      @input="handleInput"
      @keydown="$emit('keydown', $event)"
      :class="[
        'w-full rounded-xl border bg-white/70 px-3.5 py-2.5 text-sm text-slate-900 placeholder-slate-400 transition-all duration-150',
        'focus:outline-none focus:ring-2 focus:ring-sky-500/40 focus:border-sky-500 resize-none',
        'dark:bg-slate-900/70 dark:text-slate-100 dark:placeholder-slate-500',
        error
          ? 'border-rose-500 focus:ring-rose-500/40 focus:border-rose-500'
          : 'border-slate-300/80 hover:border-slate-400 dark:border-white/10 dark:hover:border-white/20',
        disabled ? 'opacity-50 cursor-not-allowed bg-slate-100 dark:bg-slate-800' : '',
      ]"
    ></textarea>
    <p v-if="error" class="text-xs text-rose-500 font-medium">{{ error }}</p>
  </div>
</template>
