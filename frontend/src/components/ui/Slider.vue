<script setup lang="ts">
interface Props {
  modelValue: number
  min?: number
  max?: number
  step?: number
  label?: string
  unit?: string
  disabled?: boolean
}

withDefaults(defineProps<Props>(), {
  min: 0,
  max: 100,
  step: 1,
  unit: '',
  disabled: false,
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: number): void
}>()

function handleInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:modelValue', parseFloat(target.value))
}
</script>

<template>
  <div class="w-full space-y-1.5">
    <div v-if="label" class="flex items-center justify-between text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400">
      <span>{{ label }}</span>
      <span class="font-mono font-normal text-slate-800 dark:text-slate-200">{{ modelValue }}{{ unit }}</span>
    </div>
    <input
      type="range"
      :min="min"
      :max="max"
      :step="step"
      :value="modelValue"
      :disabled="disabled"
      @input="handleInput"
      class="w-full h-2 bg-slate-200 rounded-lg appearance-none cursor-pointer dark:bg-slate-800 accent-sky-500 disabled:opacity-50 disabled:cursor-not-allowed"
    />
  </div>
</template>
