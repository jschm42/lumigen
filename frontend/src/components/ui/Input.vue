<script setup lang="ts">
import { computed, useAttrs } from 'vue'
import FormField from './FormField.vue'
import { controlBaseClasses, controlSizeClasses, controlStateClasses, type ControlSize } from './controlStyles'

/**
 * Text-like input with optional label, hint, error and prefix/suffix slots.
 * `class`/`style` apply to the wrapper; all other attributes (data-testid,
 * min/max/step, listeners, aria-*) are forwarded to the <input>.
 */
defineOptions({ inheritAttrs: false })

interface Props {
  modelValue?: string | number | null
  type?: string
  placeholder?: string
  label?: string
  hint?: string
  error?: string
  disabled?: boolean
  readonly?: boolean
  id?: string
  name?: string
  autofocus?: boolean
  size?: ControlSize
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
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

function handleInput(event: Event) {
  emit('update:modelValue', (event.target as HTMLInputElement).value)
}
</script>

<template>
  <FormField v-bind="rootAttrs" :id="id" :label="label" :hint="hint" :error="error">
    <template #default="{ id: fieldId, describedBy, invalid }">
      <div class="relative flex items-center">
        <div v-if="$slots.prefix" class="pointer-events-none absolute left-3 text-slate-400">
          <slot name="prefix" />
        </div>
        <input
          v-bind="controlAttrs"
          :id="fieldId"
          :name="name"
          :type="type"
          :value="modelValue ?? ''"
          :placeholder="placeholder"
          :disabled="disabled"
          :readonly="readonly"
          :autofocus="autofocus"
          :aria-invalid="invalid || undefined"
          :aria-describedby="describedBy"
          :class="[
            controlBaseClasses,
            controlSizeClasses[props.size],
            controlStateClasses(invalid),
            $slots.prefix ? 'pl-9' : '',
            $slots.suffix ? 'pr-9' : '',
          ]"
          @input="handleInput"
        />
        <div v-if="$slots.suffix" class="absolute right-3 text-slate-400">
          <slot name="suffix" />
        </div>
      </div>
    </template>
  </FormField>
</template>
