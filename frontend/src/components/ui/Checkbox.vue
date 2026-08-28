<script setup lang="ts">
interface Props {
  modelValue?: boolean
  label?: string
  value?: string | number
  disabled?: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

function handleChange(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:modelValue', target.checked)
}
</script>

<template>
  <label :class="['inline-flex items-center gap-2.5 cursor-pointer select-none', disabled ? 'opacity-50 cursor-not-allowed' : '']">
    <input
      type="checkbox"
      :checked="modelValue"
      :disabled="disabled"
      @change="handleChange"
      class="h-4 w-4 rounded border-slate-300 text-sky-500 focus:ring-sky-400 dark:border-white/20 dark:bg-slate-900/80 cursor-pointer"
    />
    <span v-if="label" class="text-sm font-medium text-slate-700 dark:text-slate-300">{{ label }}</span>
    <slot />
  </label>
</template>
