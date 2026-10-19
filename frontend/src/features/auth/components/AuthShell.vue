<script setup lang="ts">
import Card from '@/components/ui/Card.vue'

interface Props {
  title: string
  subtitle?: string
}

defineProps<Props>()
</script>

<template>
  <div class="relative min-h-screen flex items-center justify-center p-4">
    <div class="pointer-events-none absolute inset-0 -z-10 flex items-center justify-center overflow-hidden">
      <div class="h-[440px] w-[440px] rounded-full bg-sky-500/10 blur-[100px]" />
      <div class="h-[340px] w-[340px] -translate-x-20 translate-y-16 rounded-full bg-indigo-500/10 blur-[90px]" />
    </div>

    <div class="w-full max-w-md space-y-6">
      <div class="text-center space-y-3">
        <router-link to="/login" class="inline-flex justify-center">
          <img
            src="/app-logo.svg"
            alt="Lumigen Logo"
            class="h-16 w-16 select-none invert dark:invert-0 drop-shadow-xl"
          />
        </router-link>
        <div class="space-y-1">
          <h1 class="text-2xl font-extrabold tracking-tight text-slate-900 dark:text-white">{{ title }}</h1>
          <p v-if="subtitle" class="text-sm text-slate-500 dark:text-slate-400">{{ subtitle }}</p>
        </div>
      </div>

      <Card padding="lg" class="shadow-2xl border border-slate-200/80 dark:border-white/10 dark:bg-slate-900/80 backdrop-blur-xl">
        <slot />
      </Card>

      <div class="text-center text-xs text-slate-400 dark:text-slate-500">
        <slot name="footer" />
      </div>
    </div>
  </div>
</template>
