<script setup lang="ts">
import { computed, useAttrs } from 'vue'

/**
 * On/off toggle. `class`/`style` apply to the wrapper; other attributes
 * (aria-label, data-testid) go to the switch button itself.
 */
defineOptions({ inheritAttrs: false })

interface Props {
  modelValue?: boolean
  label?: string
  description?: string
  disabled?: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
}>()

const attrs = useAttrs()
const rootAttrs = computed(() => ({ class: attrs.class, style: attrs.style }))
const controlAttrs = computed(() => {
  const { class: _class, style: _style, ...rest } = attrs
  return rest
})
</script>

<template>
  <label v-bind="rootAttrs" :class="['flex items-center gap-3 cursor-pointer select-none', disabled ? 'opacity-50 cursor-not-allowed' : '']">
    <button
      v-bind="controlAttrs"
      type="button"
      role="switch"
      :aria-checked="modelValue"
      :disabled="disabled"
      @click="!disabled && emit('update:modelValue', !modelValue)"
      :class="[
        'relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors duration-200 ease-in-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40',
        modelValue ? 'bg-sky-500' : 'bg-slate-300 dark:bg-slate-700',
      ]"
    >
      <span
        :class="[
          'pointer-events-none inline-block h-5 w-5 transform rounded-full bg-white shadow ring-0 transition duration-200 ease-in-out',
          modelValue ? 'translate-x-5' : 'translate-x-0',
        ]"
      />
    </button>
    <div v-if="label || description" class="text-left">
      <div v-if="label" class="text-sm font-medium text-slate-800 dark:text-slate-200">{{ label }}</div>
      <div v-if="description" class="text-xs text-slate-500 dark:text-slate-400">{{ description }}</div>
    </div>
  </label>
</template>
