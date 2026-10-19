<script setup lang="ts">
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import AppLayout from '@/components/layout/AppLayout.vue'
import ToastContainer from '@/components/ui/ToastContainer.vue'

const route = useRoute()

const AUTH_PAGES = new Set(['/login', '/onboarding', '/forgot-password', '/reset-password'])

const isAuthPage = computed(() => AUTH_PAGES.has(route.path))
// Until the initial navigation resolves, route.path is "/"; rendering the app layout in
// that moment would start authenticated polling on the login page.
const isRouteResolved = computed(() => route.matched.length > 0)
</script>

<template>
  <template v-if="!isRouteResolved" />

  <div v-else-if="isAuthPage" class="min-h-screen bg-slate-950 text-slate-100 font-sans antialiased">
    <router-view />
    <ToastContainer />
  </div>

  <AppLayout v-else>
    <router-view />
  </AppLayout>
</template>
