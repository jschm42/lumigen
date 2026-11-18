<script setup lang="ts">
import { computed, ref, watch, onMounted, onUnmounted } from 'vue'
import { FileText, LogOut, Menu, Settings, User, X } from 'lucide-vue-next'
import Avatar from '@/components/ui/Avatar.vue'
import Badge from '@/components/ui/Badge.vue'
import DropdownMenu from '@/components/ui/DropdownMenu.vue'
import DropdownMenuItem from '@/components/ui/DropdownMenuItem.vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useQueueStore } from '@/stores/queue'
import { useCreditsStore } from '@/stores/credits'
import ThemeToggle from './ThemeToggle.vue'
import { COPYRIGHT_NOTICE } from '@/constants/app'

const route = useRoute()
const authStore = useAuthStore()
const queueStore = useQueueStore()
const creditsStore = useCreditsStore()

const isMobileNavOpen = ref(false)

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

function closeMenus() {
  isMobileNavOpen.value = false
}

// composedPath() is captured at dispatch time, so it still works when the click
// re-rendered the target (e.g. the Menu/X icon swap) before this listener runs.
function isInside(e: MouseEvent, selector: string) {
  return e.composedPath().some((node) => node instanceof Element && node.matches(selector))
}

function handleClickOutside(e: MouseEvent) {
  if (!isInside(e, '[data-mobile-nav]')) {
    isMobileNavOpen.value = false
  }
}

// Close open menus after navigating (mobile nav links, user menu links).
watch(() => route.path, closeMenus)

onMounted(() => {
  window.addEventListener('click', handleClickOutside)
})

onUnmounted(() => {
  window.removeEventListener('click', handleClickOutside)
})
</script>

<template>
  <header
    class="sticky top-0 z-40 shrink-0 border-b border-slate-200/80 bg-white/80 backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/80"
    @keydown.esc="closeMenus"
  >
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
                class="hidden sm:inline-block whitespace-nowrap rounded-md bg-slate-200/70 px-1.5 py-0.5 text-2xs font-semibold tracking-wide text-slate-600 dark:bg-white/10 dark:text-slate-300 hover:bg-sky-100 hover:text-sky-600 dark:hover:bg-sky-950/60 dark:hover:text-sky-300 transition-colors cursor-pointer"
              >
                {{ versionDisplay }}
              </button>
            </span>
            <small class="truncate text-2xs font-medium text-slate-500 dark:text-slate-400">AI Image Studio</small>
          </span>
        </router-link>

        <!-- Main Navigation -->
        <nav aria-label="Main navigation" class="hidden md:flex items-center gap-1">
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
            title="Open queue (Progress & controls)"
          >
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
      <div class="flex items-center gap-2 sm:gap-3">
        <!-- Mobile Navigation Toggle -->
        <button
          type="button"
          data-mobile-nav
          data-testid="mobile-nav-toggle"
          class="md:hidden inline-flex items-center justify-center p-2 rounded-xl border border-slate-300/60 bg-white/70 text-slate-800 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-200 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40"
          :aria-expanded="isMobileNavOpen"
          aria-controls="mobile-nav"
          :aria-label="isMobileNavOpen ? 'Close navigation' : 'Open navigation'"
          @click="isMobileNavOpen = !isMobileNavOpen"
        >
          <X v-if="isMobileNavOpen" class="size-4" aria-hidden="true" />
          <Menu v-else class="size-4" aria-hidden="true" />
        </button>

        <!-- Mobile Queue Button -->
        <button
          type="button"
          @click="queueStore.toggleQueue"
          class="md:hidden relative inline-flex items-center justify-center p-2 rounded-xl border border-slate-300/60 bg-white/70 text-slate-800 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-200 cursor-pointer"
          title="Queue"
          aria-label="Open queue"
        >
          <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7" />
          </svg>
          <span
            v-if="queueStore.totalActive > 0"
            class="absolute -top-1 -right-1 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[9px] font-bold text-white shadow-sm"
          >
            {{ queueStore.totalActive }}
          </span>
        </button>

        <ThemeToggle />

        <!-- User Dropdown Menu -->
        <DropdownMenu v-if="authStore.user" data-user-menu>
          <template #trigger="{ toggle, triggerAttrs }">
            <button
              type="button"
              v-bind="triggerAttrs"
              :aria-label="`Account menu for ${authStore.displayName}`"
              class="flex cursor-pointer items-center gap-2.5 rounded-xl border border-slate-300/60 bg-white/70 px-2 py-1.5 text-xs font-semibold text-slate-800 transition hover:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-500/40 sm:px-3 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-200 dark:hover:bg-white/10"
              @click="toggle"
            >
              <Avatar :initials="authStore.initials" size="xs" />
              <span class="hidden max-w-[120px] truncate sm:inline">{{ authStore.displayName }}</span>
              <Badge v-if="authStore.isAdmin" variant="sky" size="xs" class="hidden uppercase sm:inline-flex">Admin</Badge>
            </button>
          </template>

          <div class="border-b border-slate-200 px-3 py-2 text-slate-500 dark:border-white/10 dark:text-slate-400">
            Signed in as <strong class="text-slate-800 dark:text-slate-200">{{ authStore.user.username }}</strong>
          </div>
          <DropdownMenuItem to="/account" :icon="User">My Profile</DropdownMenuItem>
          <DropdownMenuItem v-if="authStore.isAdmin" to="/admin" :icon="Settings">Studio Settings</DropdownMenuItem>
          <DropdownMenuItem :icon="FileText" @select="creditsStore.open()">Credits &amp; Licenses</DropdownMenuItem>
          <DropdownMenuItem :icon="LogOut" variant="danger" @select="handleLogout">Sign out</DropdownMenuItem>
          <div class="mt-1 border-t border-slate-200 px-3 pb-1 pt-2 text-2xs text-slate-400 dark:border-white/10 dark:text-slate-500">
            {{ COPYRIGHT_NOTICE }}
          </div>
        </DropdownMenu>

        <router-link
          v-else-if="!authStore.isLoading"
          to="/login"
          class="inline-flex items-center rounded-xl bg-sky-500 px-3.5 py-1.5 text-xs font-semibold text-white hover:bg-sky-600 shadow-sm transition-all"
        >
          Sign in
        </router-link>
      </div>
    </div>

    <!-- Mobile Navigation Panel (below md the inline nav is hidden) -->
    <nav
      v-if="isMobileNavOpen"
      id="mobile-nav"
      data-mobile-nav
      aria-label="Main navigation"
      class="md:hidden absolute inset-x-0 top-full border-b border-slate-200/80 bg-white/95 px-3 py-2 shadow-lg backdrop-blur-xl dark:border-white/10 dark:bg-slate-950/95"
    >
      <router-link
        v-for="link in navLinks"
        :key="link.path"
        :to="link.path"
        :aria-current="isActive(link.path, link.exact) ? 'page' : undefined"
        :class="[
          'flex items-center rounded-xl px-3 py-2.5 text-sm font-semibold transition-colors',
          isActive(link.path, link.exact)
            ? 'bg-sky-500/10 text-sky-700 dark:bg-sky-500/20 dark:text-sky-300'
            : 'text-slate-700 hover:bg-slate-100 dark:text-slate-200 dark:hover:bg-white/10',
        ]"
      >
        {{ link.name }}
      </router-link>
    </nav>
  </header>
</template>
