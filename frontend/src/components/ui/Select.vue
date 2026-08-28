<script setup lang="ts">
interface Option {
  value: string | number
  label: string
  disabled?: boolean
}

interface Props {
  modelValue?: string | number | null
  options?: Option[]
  placeholder?: string
  label?: string
  error?: string
  disabled?: boolean
  id?: string
  name?: string
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:modelValue', value: any): void
}>()

function handleChange(event: Event) {
  const target = event.target as HTMLSelectElement
  emit('update:modelValue', target.value)
}
</script>

<template>
  <div class="w-full space-y-1.5">
    <label v-if="label" :for="id" class="block text-xs font-semibold uppercase tracking-wider text-slate-600 dark:text-slate-400">
      {{ label }}
    </label>
    <div class="relative">
      <select
        :id="id"
        :name="name"
        :value="modelValue ?? ''"
        :disabled="disabled"
        @change="handleChange"
        :class="[
          'w-full appearance-none rounded-xl border bg-white/70 px-3.5 py-2 pr-10 text-sm text-slate-900 transition-all duration-150',
          'focus:outline-none focus:ring-2 focus:ring-sky-500/40 focus:border-sky-500 cursor-pointer',
          'dark:bg-slate-900/70 dark:text-slate-100',
          error
            ? 'border-rose-500 focus:ring-rose-500/40 focus:border-rose-500'
            : 'border-slate-300/80 hover:border-slate-400 dark:border-white/10 dark:hover:border-white/20',
          disabled ? 'opacity-50 cursor-not-allowed bg-slate-100 dark:bg-slate-800' : '',
        ]"
      >
        <option v-if="placeholder" value="" disabled selected>{{ placeholder }}</option>
        <slot>
          <option
            v-for="opt in options"
            :key="opt.value"
            :value="opt.value"
            :disabled="opt.disabled"
          >
            {{ opt.label }}
          </option>
        </slot>
      </select>
      <div class="pointer-events-none absolute inset-y-0 right-0 flex items-center px-3 text-slate-400">
        <svg class="h-4 w-4 fill-current" viewBox="0 0 20 20">
          <path d="M5.293 7.293a1 1 0 011.414 0L10 10.586l3.293-3.293a1 1 0 111.414 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 010-1.414z" />
        </svg>
      </div>
    </div>
    <p v-if="error" class="text-xs text-rose-500 font-medium">{{ error }}</p>
  </div>
</template>
