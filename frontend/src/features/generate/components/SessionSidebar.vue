<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import { useGenerateStore } from '@/stores/generate'
import { useQueueStore } from '@/stores/queue'
import Button from '@/components/ui/Button.vue'
import Modal from '@/components/ui/Modal.vue'
import Input from '@/components/ui/Input.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import UserNavFooter from '@/components/layout/UserNavFooter.vue'
import type { ChatSession } from '@/types'

interface Props {
  collapsed?: boolean
}

defineProps<Props>()
const emit = defineEmits<{
  (e: 'toggle'): void
}>()

const sessionsStore = useSessionsStore()
const generateStore = useGenerateStore()
const queueStore = useQueueStore()

const isRenameOpen = ref(false)
const renameToken = ref('')
const renameTitle = ref('')

const isDeleteOpen = ref(false)
const deleteToken = ref('')

const isDeleteAllOpen = ref(false)
const isDeletingAll = ref(false)

onMounted(() => {
  sessionsStore.fetchSessions()
})

function formatRelative(value?: string) {
  if (!value) return ''
  const diffSeconds = Math.max(0, (Date.now() - new Date(value).getTime()) / 1000)
  if (diffSeconds < 60) return 'just now'
  if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`
  if (diffSeconds < 86400) return `${Math.floor(diffSeconds / 3600)}h ago`
  if (diffSeconds < 86400 * 7) return `${Math.floor(diffSeconds / 86400)}d ago`
  return new Date(value).toLocaleDateString()
}

function imageCountLabel(session: ChatSession) {
  const count = session.generation_count || 0
  return `${count} ${count === 1 ? 'image' : 'images'}`
}

function selectSession(session: ChatSession) {
  sessionsStore.setActiveSessionToken(session.session_token)
  generateStore.loadSessionHistory(session.session_token)
}

function handleNewSession() {
  sessionsStore.createNewSession()
  generateStore.loadSessionHistory('')
}

function openRename(session: ChatSession) {
  renameToken.value = session.session_token
  renameTitle.value = session.title
  isRenameOpen.value = true
}

async function handleRename() {
  if (!renameTitle.value.trim()) return
  await sessionsStore.renameSession(renameToken.value, renameTitle.value.trim())
  isRenameOpen.value = false
}

function openDelete(session: ChatSession) {
  deleteToken.value = session.session_token
  isDeleteOpen.value = true
}

async function handleDelete() {
  await sessionsStore.deleteSession(deleteToken.value)
  if (sessionsStore.activeSessionToken === deleteToken.value) {
    generateStore.loadSessionHistory('')
  }
  isDeleteOpen.value = false
}

async function handleDeleteAll() {
  isDeletingAll.value = true
  try {
    await sessionsStore.deleteAllSessions()
    generateStore.loadSessionHistory('')
  } finally {
    isDeletingAll.value = false
    isDeleteAllOpen.value = false
  }
}
</script>

<template>
  <!-- Collapsed rail: keeps primary actions and account access reachable -->
  <aside
    v-if="collapsed"
    class="flex h-full w-14 shrink-0 flex-col items-center gap-2 rounded-2xl border border-slate-200/80 bg-white/75 p-2 shadow-sm backdrop-blur-xl select-none dark:border-white/10 dark:bg-slate-900/75"
    data-testid="session-sidebar-collapsed"
  >
    <button
      type="button"
      @click="emit('toggle')"
      class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-xl text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-white"
      title="Expand sidebar"
      aria-label="Expand sidebar"
      data-testid="sidebar-expand"
    >
      <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 5l7 7-7 7M5 5l7 7-7 7" />
      </svg>
    </button>
    <button
      type="button"
      @click="handleNewSession"
      class="flex h-9 w-9 cursor-pointer items-center justify-center rounded-xl border border-dashed border-sky-400/50 text-lg font-bold text-sky-500 transition-colors hover:border-sky-400 hover:bg-sky-500/10"
      title="New session"
      aria-label="New session"
    >
      +
    </button>
    <button
      type="button"
      @click="queueStore.openQueue"
      class="relative flex h-9 w-9 cursor-pointer items-center justify-center rounded-xl text-sky-600 transition-colors hover:bg-sky-500/10 dark:text-sky-300"
      title="Open queue"
      aria-label="Open queue"
    >
      <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7" />
      </svg>
      <span
        v-if="queueStore.totalActive > 0"
        class="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-sky-500 px-1 text-[9px] font-bold text-white"
      >
        {{ queueStore.totalActive }}
      </span>
    </button>
    <div class="flex-1" />
    <UserNavFooter collapsed />
  </aside>

  <aside
    v-else
    class="flex flex-col w-72 xl:w-80 shrink-0 rounded-2xl border border-slate-200/80 bg-white/75 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/75 p-3 h-full min-h-0 select-none shadow-sm"
    data-testid="session-sidebar"
  >
    <!-- Top Action: New Session + collapse -->
    <div class="mb-3 flex items-center gap-2">
      <Button
        variant="surface"
        size="sm"
        fullWidth
        @click="handleNewSession"
        class="border-dashed border-sky-400/40 hover:border-sky-400"
      >
        <template #icon>
          <span class="text-base leading-none text-sky-500 font-bold">+</span>
        </template>
        New Session
      </Button>
      <button
        type="button"
        @click="emit('toggle')"
        class="flex h-8 w-8 shrink-0 cursor-pointer items-center justify-center rounded-xl text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-white/10 dark:hover:text-white"
        title="Collapse sidebar"
        aria-label="Collapse sidebar"
        data-testid="sidebar-collapse"
      >
        <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
        </svg>
      </button>
    </div>

    <!-- Queue Status Card -->
    <div class="mb-3">
      <button
        type="button"
        @click="queueStore.openQueue"
        class="w-full flex items-center justify-between p-2.5 rounded-xl border border-slate-200/80 bg-slate-50/80 hover:bg-sky-50/60 hover:border-sky-400/50 dark:border-white/10 dark:bg-slate-950/50 dark:hover:bg-sky-950/30 dark:hover:border-sky-500/40 transition-all text-left group cursor-pointer"
        title="Open Queue"
      >
        <div class="flex items-center gap-2 min-w-0">
          <span
            :class="[
              'flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sky-500/10 text-sky-600 dark:bg-sky-400/20 dark:text-sky-300 text-xs',
              queueStore.totalActive > 0 ? 'animate-pulse' : '',
            ]"
          >
            <svg class="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h7" />
            </svg>
          </span>
          <div class="min-w-0">
            <div class="text-xs font-semibold text-slate-800 dark:text-slate-200 group-hover:text-sky-600 dark:group-hover:text-sky-400">
              Queue
            </div>
            <p class="text-[10px] text-slate-500 dark:text-slate-400 truncate">
              {{ queueStore.totalActive > 0 ? (queueStore.totalActive === 1 ? '1 job in progress' : `${queueStore.totalActive} jobs in progress`) : 'All jobs completed' }}
            </p>
          </div>
        </div>

        <svg class="w-4 h-4 text-slate-400 group-hover:text-sky-500 transition-transform group-hover:translate-x-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>

    <!-- Search Input -->
    <div class="relative mb-2">
      <svg class="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-slate-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-4.35-4.35M17 11A6 6 0 115 11a6 6 0 0112 0z" />
      </svg>
      <input
        type="search"
        v-model="sessionsStore.searchQuery"
        @input="sessionsStore.fetchSessions"
        placeholder="Search sessions..."
        class="w-full rounded-xl border border-slate-200 bg-white/60 py-1.5 pl-8 pr-3 text-xs text-slate-800 placeholder-slate-400 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-200 dark:placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
      />
    </div>

    <!-- List header -->
    <div class="mb-1 flex items-center justify-between px-1">
      <span class="text-[10px] font-semibold uppercase tracking-wider text-slate-400">
        Sessions<span v-if="sessionsStore.sessions.length"> ({{ sessionsStore.sessions.length }})</span>
      </span>
      <button
        v-if="sessionsStore.sessions.length > 0"
        type="button"
        @click="isDeleteAllOpen = true"
        class="cursor-pointer rounded px-1 text-[10px] font-medium text-slate-400 transition-colors hover:text-rose-500"
        title="Delete all sessions"
      >
        Clear all
      </button>
    </div>

    <!-- Sessions List -->
    <div class="flex-1 min-h-0 overflow-y-auto space-y-0.5 pr-1">
      <div v-if="sessionsStore.sessions.length === 0" class="py-8 text-center text-xs text-slate-400">
        {{ sessionsStore.searchQuery ? 'No matching sessions' : 'No sessions yet. Start with a prompt.' }}
      </div>

      <div
        v-for="session in sessionsStore.sessions"
        :key="session.id"
        role="button"
        tabindex="0"
        @click="selectSession(session)"
        @keydown.enter="selectSession(session)"
        :class="[
          'group relative flex items-center justify-between gap-2 px-2 py-1.5 rounded-xl text-xs font-medium transition-all duration-150 cursor-pointer focus:outline-none focus-visible:ring-1 focus-visible:ring-sky-500',
          sessionsStore.activeSessionToken === session.session_token
            ? 'bg-sky-500/10 text-sky-700 dark:bg-sky-500/20 dark:text-sky-200 font-semibold ring-1 ring-sky-400/30'
            : 'text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-white/5',
        ]"
      >
        <div class="flex items-center gap-2.5 min-w-0 flex-1">
          <div class="w-9 h-9 rounded-lg bg-slate-200 dark:bg-slate-800 shrink-0 overflow-hidden flex items-center justify-center border border-slate-300/40 dark:border-white/10">
            <img
              v-if="session.cover_asset_url"
              :src="session.cover_asset_url"
              alt=""
              loading="lazy"
              class="w-full h-full object-cover"
            />
            <span v-else class="text-[11px] text-slate-400">📁</span>
          </div>

          <div class="min-w-0 flex-1 text-left">
            <div class="truncate">{{ session.title }}</div>
            <div class="flex items-center gap-1 text-[10px] font-normal text-slate-400">
              <span>{{ imageCountLabel(session) }}</span>
              <span v-if="session.updated_at || session.created_at">· {{ formatRelative(session.updated_at || session.created_at) }}</span>
            </div>
          </div>
        </div>

        <div class="flex items-center gap-0.5 opacity-0 transition-opacity group-hover:opacity-100 group-focus-within:opacity-100">
          <button
            type="button"
            @click.stop="openRename(session)"
            class="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded cursor-pointer"
            title="Rename"
          >
            ✏️
          </button>
          <button
            type="button"
            @click.stop="openDelete(session)"
            class="p-1 text-slate-400 hover:text-rose-500 rounded cursor-pointer"
            title="Delete"
          >
            🗑️
          </button>
        </div>
      </div>
    </div>

    <!-- Account: profile, credits, logout -->
    <div class="mt-2">
      <UserNavFooter />
    </div>

    <!-- Rename Modal -->
    <Modal :open="isRenameOpen" title="Rename Session" size="sm" @update:open="isRenameOpen = $event">
      <div class="space-y-4">
        <Input
          label="Title"
          v-model="renameTitle"
          autofocus
          @keydown.enter="handleRename"
        />
      </div>
      <template #footer>
        <Button variant="secondary" size="sm" @click="isRenameOpen = false">Cancel</Button>
        <Button variant="primary" size="sm" @click="handleRename">Save</Button>
      </template>
    </Modal>

    <!-- Delete Confirm Dialog -->
    <ConfirmDialog
      :open="isDeleteOpen"
      message="Do you really want to delete this session and its history?"
      @update:open="isDeleteOpen = $event"
      @confirm="handleDelete"
    />

    <!-- Delete All Confirm Dialog -->
    <ConfirmDialog
      :open="isDeleteAllOpen"
      title="Delete all sessions"
      message="Do you really want to permanently delete all sessions and their history? Generated images in the gallery will be preserved."
      confirmText="Delete all"
      variant="danger"
      :loading="isDeletingAll"
      @update:open="isDeleteAllOpen = $event"
      @confirm="handleDeleteAll"
    />
  </aside>
</template>
