<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import ToastContainer from '@/components/ui/ToastContainer.vue'

const route = useRoute()

const isAuthPage = computed(() => {
  return route.path === '/login' || route.path === '/onboarding'
})
</script>

<template>
  <div v-if="isAuthPage" class="min-h-screen bg-slate-950 text-slate-100 font-sans antialiased">
    <router-view />
    <ToastContainer />
  </div>

  <AppLayout v-else>
    <router-view />
  </AppLayout>
</template>
