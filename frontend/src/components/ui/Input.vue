<script setup lang="ts">
interface Props {
  modelValue?: string | number
  type?: string
  placeholder?: string
  label?: string
  error?: string
  disabled?: boolean
  readonly?: boolean
  id?: string
  name?: string
  autofocus?: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'blur', event: FocusEvent): void
  (e: 'focus', event: FocusEvent): void
}>()

function handleInput(event: Event) {
  const target = event.target as HTMLInputElement
  emit('update:modelValue', target.value)
}
</script>

<template>
  <div class="w-full space-y-1.5">
    <label v-if="label" :for="id" class="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400">
      {{ label }}
    </label>
    <div class="relative flex items-center">
      <div v-if="$slots.prefix" class="absolute left-3 text-slate-400 pointer-events-none">
        <slot name="prefix" />
      </div>
      <input
        :id="id"
        :name="name"
        :type="type || 'text'"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :readonly="readonly"
        :autofocus="autofocus"
        @input="handleInput"
        @blur="$emit('blur', $event)"
        @focus="$emit('focus', $event)"
        :class="[
          'w-full rounded-xl border bg-white/70 px-3.5 py-2 text-sm text-slate-900 placeholder-slate-400 transition-all duration-150',
          'focus:outline-none focus:ring-2 focus:ring-sky-500/40 focus:border-sky-500',
          'dark:bg-slate-900/70 dark:text-slate-100 dark:placeholder-slate-500',
          $slots.prefix ? 'pl-9' : '',
          $slots.suffix ? 'pr-9' : '',
          error
            ? 'border-rose-500 focus:ring-rose-500/40 focus:border-rose-500'
            : 'border-slate-300/80 hover:border-slate-400 dark:border-white/10 dark:hover:border-white/20',
          disabled ? 'opacity-50 cursor-not-allowed bg-slate-100 dark:bg-slate-800' : '',
        ]"
      />
      <div v-if="$slots.suffix" class="absolute right-3 text-slate-400">
        <slot name="suffix" />
      </div>
    </div>
    <p v-if="error" class="text-xs text-rose-500 font-medium">{{ error }}</p>
  </div>
</template>
