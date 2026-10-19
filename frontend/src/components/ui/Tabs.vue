<script setup lang="ts">
export interface TabItem {
  id: string
  label: string
  icon?: any
  badge?: string | number
}

interface Props {
  tabs: TabItem[]
  modelValue: string
  variant?: 'pills' | 'underline'
}

withDefaults(defineProps<Props>(), {
  variant: 'pills',
})

const emit = defineEmits<{
  (e: 'update:modelValue', id: string): void
}>()
</script>

<template>
  <div
    v-if="variant === 'pills'"
    class="inline-flex p-1 rounded-xl bg-slate-200/60 dark:bg-slate-900/60 border border-slate-300/40 dark:border-white/10 gap-1"
  >
    <button
      v-for="tab in tabs"
      :key="tab.id"
      type="button"
      @click="emit('update:modelValue', tab.id)"
      :class="[
        'inline-flex items-center gap-2 px-3.5 py-1.5 rounded-lg text-xs font-semibold transition-all duration-150 cursor-pointer',
        modelValue === tab.id
          ? 'bg-white text-slate-900 shadow-sm dark:bg-slate-800 dark:text-white'
          : 'text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-white',
      ]"
    >
      <span>{{ tab.label }}</span>
      <span
        v-if="tab.badge !== undefined"
        class="px-1.5 py-0.2 rounded-full text-[10px] bg-slate-200 dark:bg-slate-700 text-slate-700 dark:text-slate-300"
      >
        {{ tab.badge }}
      </span>
    </button>
  </div>

  <div
    v-else
    class="flex border-b border-slate-200 dark:border-white/10 gap-6"
  >
    <button
      v-for="tab in tabs"
      :key="tab.id"
      type="button"
      @click="emit('update:modelValue', tab.id)"
      :class="[
        'pb-3 text-sm font-semibold border-b-2 transition-all duration-150 flex items-center gap-2 cursor-pointer',
        modelValue === tab.id
          ? 'border-sky-500 text-sky-600 dark:text-sky-400'
          : 'border-transparent text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-200',
      ]"
    >
      <span>{{ tab.label }}</span>
      <span
        v-if="tab.badge !== undefined"
        class="px-1.5 py-0.5 rounded-full text-[10px] bg-slate-200 dark:bg-slate-800 text-slate-700 dark:text-slate-300"
      >
        {{ tab.badge }}
      </span>
    </button>
  </div>
</template>
