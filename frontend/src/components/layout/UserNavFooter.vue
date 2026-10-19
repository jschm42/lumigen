<script setup lang="ts">
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useCreditsStore } from '@/stores/credits'

interface Props {
  collapsed?: boolean
}

defineProps<Props>()

const route = useRoute()
const authStore = useAuthStore()
const creditsStore = useCreditsStore()
</script>

<template>
  <div
    v-if="authStore.user"
    :class="[
      'shrink-0 border-t border-slate-200/80 pt-3 dark:border-white/10',
      collapsed ? 'flex flex-col items-center gap-1.5' : 'space-y-2',
    ]"
    data-testid="user-nav-footer"
  >
    <!-- Identity -->
    <router-link
      to="/account"
      :class="[
        'group flex items-center gap-2.5 rounded-xl transition-colors',
        collapsed ? 'p-1' : 'px-2 py-1.5',
        route.path === '/account'
          ? 'bg-sky-500/10 dark:bg-sky-500/20'
          : 'hover:bg-slate-100 dark:hover:bg-white/5',
      ]"
      :title="collapsed ? `${authStore.displayName} – My profile` : 'My profile'"
    >
      <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-tr from-sky-400 to-indigo-500 text-[11px] font-bold text-white shadow-sm">
        {{ authStore.initials }}
      </span>
      <span v-if="!collapsed" class="min-w-0 flex-1">
        <span class="block truncate text-xs font-semibold text-slate-800 group-hover:text-sky-600 dark:text-slate-100 dark:group-hover:text-sky-300">
          {{ authStore.displayName }}
        </span>
        <span class="block truncate text-[10px] text-slate-500 dark:text-slate-400">
          {{ authStore.isAdmin ? 'Administrator' : 'User' }}<template v-if="authStore.user.email"> · {{ authStore.user.email }}</template>
        </span>
      </span>
    </router-link>

    <!-- Actions -->
    <div :class="collapsed ? 'flex flex-col gap-1' : 'grid grid-cols-3 gap-1'">
      <router-link
        to="/account"
        class="inline-flex items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white"
        title="My profile"
        data-testid="nav-profile"
      >
        <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
        </svg>
        <span v-if="!collapsed">Profile</span>
      </router-link>
      <button
        type="button"
        @click="creditsStore.open()"
        class="inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] font-medium text-slate-600 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-slate-300 dark:hover:bg-white/10 dark:hover:text-white"
        title="Credits & licenses"
        data-testid="nav-credits"
      >
        <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
        </svg>
        <span v-if="!collapsed">Credits</span>
      </button>
      <button
        type="button"
        @click="authStore.logout()"
        class="inline-flex cursor-pointer items-center justify-center gap-1.5 rounded-lg px-2 py-1.5 text-[11px] font-medium text-rose-500 transition-colors hover:bg-rose-500/10 hover:text-rose-600 dark:text-rose-400 dark:hover:text-rose-300"
        title="Sign out"
        data-testid="nav-logout"
      >
        <svg class="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1" />
        </svg>
        <span v-if="!collapsed">Logout</span>
      </button>
    </div>
  </div>
</template>
