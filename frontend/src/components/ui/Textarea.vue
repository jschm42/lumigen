<script setup lang="ts">
import { computed, onMounted, ref, useAttrs, watch } from 'vue'
import FormField from './FormField.vue'
import { controlBaseClasses, controlSizeClasses, controlStateClasses, type ControlSize } from './controlStyles'

/**
 * Multi-line text control with optional auto-grow and character counter.
 * `class`/`style` apply to the wrapper; other attributes go to the <textarea>.
 */
defineOptions({ inheritAttrs: false })

interface Props {
  modelValue?: string
  placeholder?: string
  label?: string
  hint?: string
  error?: string
  rows?: number
  disabled?: boolean
  readonly?: boolean
  autoGrow?: boolean
  id?: string
  name?: string
  maxLength?: number
  size?: ControlSize
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: '',
  rows: 3,
  size: 'md',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
}>()

const attrs = useAttrs()
const rootAttrs = computed(() => ({ class: attrs.class, style: attrs.style }))
const controlAttrs = computed(() => {
  const { class: _class, style: _style, ...rest } = attrs
  return rest
})

const textareaRef = ref<HTMLTextAreaElement | null>(null)

function adjustHeight() {
  if (!props.autoGrow || !textareaRef.value) return
  textareaRef.value.style.height = 'auto'
  textareaRef.value.style.height = `${Math.min(textareaRef.value.scrollHeight, 280)}px`
}

function handleInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLTextAreaElement).value)
  adjustHeight()
}

onMounted(adjustHeight)
watch(() => props.modelValue, adjustHeight)
</script>

<template>
  <FormField v-bind="rootAttrs" :id="id" :label="label" :hint="hint" :error="error">
    <template v-if="maxLength" #aside>
      <span class="text-2xs text-slate-400">{{ modelValue?.length || 0 }} / {{ maxLength }}</span>
    </template>
    <template #default="{ id: fieldId, describedBy, invalid }">
      <textarea
        v-bind="controlAttrs"
        :id="fieldId"
        ref="textareaRef"
        :name="name"
        :value="modelValue"
        :placeholder="placeholder"
        :rows="rows"
        :disabled="disabled"
        :readonly="readonly"
        :maxlength="maxLength"
        :aria-invalid="invalid || undefined"
        :aria-describedby="describedBy"
        :class="[controlBaseClasses, controlSizeClasses[props.size], controlStateClasses(invalid), 'resize-none']"
        @input="handleInput"
      ></textarea>
    </template>
  </FormField>
</template>
