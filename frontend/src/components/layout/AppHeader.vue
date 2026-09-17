<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useQueueStore } from '@/stores/queue'
import { useCreditsStore } from '@/stores/credits'
import ThemeToggle from './ThemeToggle.vue'

const route = useRoute()
const authStore = useAuthStore()
const queueStore = useQueueStore()
const creditsStore = useCreditsStore()

const isUserMenuOpen = ref(false)

const versionDisplay = computed(() => {
  const ver = authStore.appVersion
  if (!ver) return ''
  return ver.startsWith('v') ? ver : `v${ver}`
})

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
  <header class="sticky top-0 z-40 shrink-0 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/80">
    <div class="flex w-full items-center justify-between px-3 sm:px-6 py-2 sm:py-2.5">
      <!-- Logo & Title -->
      <div class="flex items-center gap-6">
        <router-link
          to="/"
          class="group inline-flex items-center gap-3 transition-opacity hover:opacity-85"
        >
          <img
            src="/app-logo.svg"
            alt="Lumigen"
            class="h-10 w-10 sm:h-11 sm:w-11 shrink-0 invert dark:invert-0 transition-transform duration-200 group-hover:scale-105"
          />
          <span class="grid min-w-0 gap-0.5 text-left">
            <span class="flex items-center gap-2">
              <strong class="text-sm sm:text-base font-bold tracking-tight text-slate-900 dark:text-white">Lumigen</strong>
              <button
                v-if="versionDisplay"
                type="button"
                @click.prevent.stop="creditsStore.open"
                title="View credits, licenses & version details"
                class="rounded-md bg-slate-200/70 px-1.5 py-0.5 text-[10px] font-semibold tracking-wide text-slate-600 dark:bg-white/10 dark:text-slate-300 hover:bg-sky-100 hover:text-sky-600 dark:hover:bg-sky-950/60 dark:hover:text-sky-300 transition-colors cursor-pointer"
              >
                {{ versionDisplay }}
              </button>
            </span>
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

          <!-- Queue Trigger Button -->
          <button
            type="button"
            @click="queueStore.toggleQueue"
            :class="[
              'ml-1 inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-all duration-150 cursor-pointer',
              queueStore.isOpen
                ? 'bg-sky-100 text-sky-700 dark:bg-sky-950 dark:text-sky-300 ring-1 ring-sky-500/30'
                : 'text-slate-600 hover:bg-slate-200/60 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white',
            ]"
            title="Warteschlange öffnen (Fortschritt & Steuerung)"
          >
            <span class="text-xs">⏳</span>
            <span>Queue</span>
            <span
              v-if="queueStore.totalActive > 0"
              class="inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[10px] font-bold text-white shadow-sm"
            >
              {{ queueStore.totalActive }}
            </span>
          </button>
        </nav>
      </div>

      <!-- Right Controls: Theme Toggle & User Menu -->
      <div class="flex items-center gap-3">
        <!-- Mobile Queue Button -->
        <button
          type="button"
          @click="queueStore.toggleQueue"
          class="md:hidden relative inline-flex items-center justify-center p-2 rounded-xl border border-slate-300/60 bg-white/70 text-slate-800 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-200"
          title="Warteschlange"
        >
          <span class="text-sm leading-none">⏳</span>
          <span
            v-if="queueStore.totalActive > 0"
            class="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[9px] font-bold text-white shadow-sm"
          >
            {{ queueStore.totalActive }}
          </span>
        </button>

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
              @click="isUserMenuOpen = false; creditsStore.open()"
              class="w-full text-left flex items-center gap-2 px-3 py-2 rounded-xl text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-white/10 transition-colors cursor-pointer"
            >
              📜 Credits & Licenses
            </button>

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
