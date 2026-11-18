<script setup lang="ts">
import { computed, useAttrs } from 'vue'
import { ChevronDown } from 'lucide-vue-next'
import FormField from './FormField.vue'
import { controlBaseClasses, controlSizeClasses, controlStateClasses, type ControlSize } from './controlStyles'

/**
 * Native select with the shared control styling.
 * With `options`, the emitted value keeps the option's original type (number stays number);
 * with slotted <option> elements the raw string value is emitted.
 */
defineOptions({ inheritAttrs: false })

export interface SelectOption {
  value: string | number
  label: string
  disabled?: boolean
}

interface Props {
  modelValue?: string | number | null
  options?: SelectOption[]
  placeholder?: string
  label?: string
  hint?: string
  error?: string
  disabled?: boolean
  id?: string
  name?: string
  size?: ControlSize
}

const props = withDefaults(defineProps<Props>(), {
  size: 'md',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | number): void
}>()

const attrs = useAttrs()
const rootAttrs = computed(() => ({ class: attrs.class, style: attrs.style }))
const controlAttrs = computed(() => {
  const { class: _class, style: _style, ...rest } = attrs
  return rest
})

function handleChange(event: Event) {
  const raw = (event.target as HTMLSelectElement).value
  const match = props.options?.find((option) => String(option.value) === raw)
  emit('update:modelValue', match ? match.value : raw)
}
</script>

<template>
  <FormField v-bind="rootAttrs" :id="id" :label="label" :hint="hint" :error="error">
    <template #default="{ id: fieldId, describedBy, invalid }">
      <div class="relative">
        <select
          v-bind="controlAttrs"
          :id="fieldId"
          :name="name"
          :value="modelValue ?? ''"
          :disabled="disabled"
          :aria-invalid="invalid || undefined"
          :aria-describedby="describedBy"
          :class="[
            controlBaseClasses,
            controlSizeClasses[props.size],
            controlStateClasses(invalid),
            'cursor-pointer appearance-none pr-8',
          ]"
          @change="handleChange"
        >
          <option v-if="placeholder" value="" disabled>{{ placeholder }}</option>
          <slot>
            <option v-for="opt in options" :key="opt.value" :value="opt.value" :disabled="opt.disabled">
              {{ opt.label }}
            </option>
          </slot>
        </select>
        <ChevronDown
          class="pointer-events-none absolute right-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400"
          aria-hidden="true"
        />
      </div>
    </template>
  </FormField>
</template>
