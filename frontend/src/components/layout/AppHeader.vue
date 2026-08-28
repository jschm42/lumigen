<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import ThemeToggle from './ThemeToggle.vue'

const route = useRoute()
const authStore = useAuthStore()

const isUserMenuOpen = ref(false)

const navLinks = computed(() => {
  const links = [
    { name: 'Generate', path: '/', exact: true },
    { name: 'Profiles', path: '/profiles' },
    { name: 'Gallery', path: '/gallery' },
  ]
  if (authStore.isAdmin) {
    links.push({ name: 'Admin', path: '/admin' })
  }
  return links
})

function isActive(path: string, exact = false) {
  if (exact) return route.path === path
  return route.path.startsWith(path)
}

function handleLogout() {
  authStore.logout()
}

function handleClickOutside(e: MouseEvent) {
  const target = e.target as HTMLElement
  if (!target.closest('[data-user-menu]')) {
    isUserMenuOpen.value = false
  }
}

onMounted(() => {
  window.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <header class="sticky top-0 z-40 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/80">
    <div class="mx-auto flex w-full max-w-7xl items-center justify-between px-4 py-3 sm:px-6 lg:px-8">
      <!-- Logo & Title -->
      <div class="flex items-center gap-6">
        <router-link
          to="/"
          class="inline-flex items-center gap-3 rounded-2xl border border-slate-300/60 bg-white/70 px-3 py-2 transition hover:border-sky-400/60 hover:bg-white dark:border-white/10 dark:bg-white/5 dark:hover:border-sky-300/50 dark:hover:bg-white/10"
        >
          <span class="inline-flex h-9 w-9 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-sky-400/40 bg-slate-200/80 dark:border-sky-300/30 dark:bg-slate-900/70">
            <img src="/static/app-logo.svg" alt="Lumigen" class="h-8 w-8 rounded-lg invert dark:invert-0" />
          </span>
          <span class="grid min-w-0 gap-0.5 text-left">
            <strong class="text-sm font-bold tracking-tight text-slate-900 dark:text-white">Lumigen</strong>
            <small class="truncate text-[11px] font-medium text-slate-500 dark:text-slate-400">AI Image Studio</small>
          </span>
        </router-link>

        <!-- Main Navigation -->
        <nav aria-label="Hauptnavigation" class="hidden md:flex items-center gap-1">
          <router-link
            v-for="link in navLinks"
            :key="link.path"
            :to="link.path"
            :class="[
              'inline-flex items-center rounded-full px-4 py-1.5 text-xs font-semibold transition-all duration-150',
              isActive(link.path, link.exact)
                ? 'bg-sky-500 text-white shadow-md shadow-sky-500/25'
                : 'text-slate-600 hover:bg-slate-200/60 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white',
            ]"
          >
            {{ link.name }}
          </router-link>
        </nav>
      </div>

      <!-- Right Controls: Theme Toggle & User Menu -->
      <div class="flex items-center gap-3">
        <ThemeToggle />

        <!-- User Dropdown Menu -->
        <div v-if="authStore.user" class="relative" data-user-menu>
          <button
            type="button"
            @click="isUserMenuOpen = !isUserMenuOpen"
            class="flex items-center gap-2.5 rounded-xl border border-slate-300/60 bg-white/70 px-3 py-1.5 text-xs font-semibold text-slate-800 transition hover:bg-slate-100 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-200 dark:hover:bg-white/10 cursor-pointer"
          >
            <span class="w-6 h-6 rounded-full bg-gradient-to-tr from-sky-400 to-indigo-500 flex items-center justify-center text-white font-bold text-[10px]">
              {{ authStore.user.username.charAt(0).toUpperCase() }}
            </span>
            <span class="max-w-[100px] truncate">{{ authStore.user.username }}</span>
            <span v-if="authStore.isAdmin" class="px-1.5 py-0.2 rounded text-[9px] font-bold bg-sky-500/20 text-sky-500 dark:bg-sky-400/20 dark:text-sky-300">ADMIN</span>
          </button>

          <!-- Dropdown popup -->
          <div
            v-if="isUserMenuOpen"
            class="absolute right-0 mt-2 w-48 rounded-2xl border border-slate-200 bg-white/95 p-1.5 text-xs shadow-xl backdrop-blur-md dark:border-white/10 dark:bg-slate-900/95 z-50 animate-in fade-in slide-in-from-top-2 duration-150"
          >
            <div class="px-3 py-2 border-b border-slate-200 dark:border-white/10 text-slate-500 dark:text-slate-400">
              Angemeldet als <strong class="text-slate-800 dark:text-slate-200">{{ authStore.user.username }}</strong>
            </div>

            <router-link
              v-if="authStore.isAdmin"
              to="/admin"
              @click="isUserMenuOpen = false"
              class="flex items-center gap-2 px-3 py-2 rounded-xl text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-white/10 transition-colors"
            >
              ⚙️ Studio Einstellungen
            </router-link>

            <button
              type="button"
              @click="handleLogout"
              class="w-full text-left flex items-center gap-2 px-3 py-2 rounded-xl text-rose-600 hover:bg-rose-50 dark:text-rose-400 dark:hover:bg-rose-950/40 transition-colors cursor-pointer"
            >
              🚪 Abmelden
            </button>
          </div>
        </div>

        <router-link
          v-else-if="!authStore.isLoading"
          to="/login"
          class="inline-flex items-center rounded-xl bg-sky-500 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-sky-600 shadow-sm transition-all"
        >
          Anmelden
        </router-link>
      </div>
    </div>
  </header>
</template>
