<script setup lang="ts">
import { computed, useId } from 'vue'
import { fieldLabelClasses } from './controlStyles'

/**
 * Label + hint + error wrapper around any form control.
 * The default slot receives `{ id, describedBy, invalid }` to bind onto the control.
 */
interface Props {
  label?: string
  hint?: string
  error?: string
  id?: string
  required?: boolean
}

const props = defineProps<Props>()

const generatedId = `field-${useId()}`
const fieldId = computed(() => props.id || generatedId)
const hintId = computed(() => `${fieldId.value}-hint`)
const errorId = computed(() => `${fieldId.value}-error`)
const describedBy = computed(() => {
  const ids = [props.hint ? hintId.value : '', props.error ? errorId.value : ''].filter(Boolean)
  return ids.length ? ids.join(' ') : undefined
})
</script>

<template>
  <div class="space-y-1">
    <div v-if="label || $slots.aside" class="flex items-center justify-between gap-2">
      <label v-if="label" :for="fieldId" :class="fieldLabelClasses">
        {{ label }}<span v-if="required" class="text-rose-500" aria-hidden="true"> *</span>
      </label>
      <slot name="aside" />
    </div>
    <slot :id="fieldId" :described-by="describedBy" :invalid="!!error" />
    <p v-if="hint && !error" :id="hintId" class="text-2xs text-slate-500 dark:text-slate-400">{{ hint }}</p>
    <p v-if="error" :id="errorId" role="alert" class="text-xs font-medium text-rose-500">{{ error }}</p>
  </div>
</template>
