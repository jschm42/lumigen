<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useSessionsStore } from '@/stores/sessions'
import { useGenerateStore } from '@/stores/generate'
import { useQueueStore } from '@/stores/queue'
import Button from '@/components/ui/Button.vue'
import Modal from '@/components/ui/Modal.vue'
import Input from '@/components/ui/Input.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import type { ChatSession } from '@/types'

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
  <aside class="flex flex-col w-72 sm:w-80 shrink-0 rounded-2xl border border-slate-200/80 bg-white/75 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/75 p-3.5 h-full min-h-0 select-none shadow-sm">
    <!-- Top Action: New Artbook / Session -->
    <div class="mb-3">
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
        Neue Session / Artbook
      </Button>
    </div>

    <!-- Queue Status Card in Left Navigation Area -->
    <div class="mb-3">
      <button
        type="button"
        @click="queueStore.openQueue"
        class="w-full flex items-center justify-between p-2.5 rounded-xl border border-slate-200/80 bg-slate-50/80 hover:bg-sky-50/60 hover:border-sky-400/50 dark:border-white/10 dark:bg-slate-950/50 dark:hover:bg-sky-950/30 dark:hover:border-sky-500/40 transition-all text-left group cursor-pointer shadow-xs"
        title="Warteschlange öffnen"
      >
        <div class="flex items-center gap-2 min-w-0">
          <span class="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sky-500/10 text-sky-600 dark:bg-sky-400/20 dark:text-sky-300 text-xs">
            ⏳
          </span>
          <div class="min-w-0">
            <div class="text-xs font-semibold text-slate-800 dark:text-slate-200 group-hover:text-sky-600 dark:group-hover:text-sky-400 flex items-center gap-1.5">
              <span>Warteschlange</span>
              <span
                v-if="queueStore.totalActive > 0"
                class="px-1.5 py-0.2 rounded-full text-[10px] font-bold bg-sky-500 text-white"
              >
                {{ queueStore.totalActive }}
              </span>
            </div>
            <p class="text-[10px] text-slate-500 dark:text-slate-400 truncate">
              {{ queueStore.totalActive > 0 ? `${queueStore.totalActive} Auftrag in Arbeit` : 'Alle Aufträge fertig' }}
            </p>
          </div>
        </div>

        <svg class="w-4 h-4 text-slate-400 group-hover:text-sky-500 transition-transform group-hover:translate-x-0.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>

    <!-- Search Input -->
    <div class="relative mb-3">
      <input
        type="text"
        v-model="sessionsStore.searchQuery"
        @input="sessionsStore.fetchSessions"
        placeholder="Sessions durchsuchen..."
        class="w-full rounded-xl border border-slate-200 bg-white/60 px-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 dark:border-white/10 dark:bg-slate-950/60 dark:text-slate-200 dark:placeholder-slate-500 focus:outline-none focus:ring-1 focus:ring-sky-500"
      />
    </div>

    <!-- Sessions List -->
    <div class="flex-1 overflow-y-auto space-y-1 pr-1">
      <div v-if="sessionsStore.sessions.length === 0" class="py-8 text-center text-xs text-slate-400">
        Keine Sessions gefunden
      </div>

      <div
        v-for="session in sessionsStore.sessions"
        :key="session.id"
        @click="selectSession(session)"
        :class="[
          'group relative flex items-center justify-between gap-2 px-3 py-2 rounded-xl text-xs font-medium transition-all duration-150 cursor-pointer',
          sessionsStore.activeSessionToken === session.session_token
            ? 'bg-sky-500/10 text-sky-600 dark:bg-sky-500/20 dark:text-sky-300 font-semibold border border-sky-400/30'
            : 'text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-white/5 border border-transparent',
        ]"
      >
        <div class="flex items-center gap-2.5 min-w-0 flex-1">
          <!-- Session Cover Thumbnail or Fallback Icon -->
          <div class="w-7 h-7 rounded-lg bg-slate-200 dark:bg-slate-800 shrink-0 overflow-hidden flex items-center justify-center border border-slate-300/40 dark:border-white/10">
            <img
              v-if="session.cover_asset_url"
              :src="session.cover_asset_url"
              alt=""
              class="w-full h-full object-cover"
            />
            <span v-else class="text-[10px] text-slate-400">📁</span>
          </div>

          <div class="truncate text-left flex-1">
            <div class="truncate">{{ session.title }}</div>
            <div class="text-[10px] text-slate-400 font-normal">
              {{ session.generation_count || 0 }} Bilder
            </div>
          </div>
        </div>

        <!-- Quick actions hover menu -->
        <div class="opacity-0 group-hover:opacity-100 flex items-center gap-1 transition-opacity">
          <button
            type="button"
            @click.stop="openRename(session)"
            class="p-1 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 rounded"
            title="Umbenennen"
          >
            ✏️
          </button>
          <button
            type="button"
            @click.stop="openDelete(session)"
            class="p-1 text-slate-400 hover:text-rose-500 rounded"
            title="Löschen"
          >
            🗑️
          </button>
        </div>
      </div>
    </div>

    <!-- Bottom Action: Delete All Sessions -->
    <div v-if="sessionsStore.sessions.length > 0" class="pt-2.5 mt-2 border-t border-slate-200/80 dark:border-white/10 shrink-0">
      <Button
        variant="ghost"
        size="xs"
        fullWidth
        @click="isDeleteAllOpen = true"
        class="text-rose-500 hover:text-rose-600 hover:bg-rose-500/10 justify-center text-xs font-medium"
      >
        <template #icon>
          <span class="text-xs">🗑️</span>
        </template>
        Alle Sessions löschen
      </Button>
    </div>

    <!-- Rename Modal -->
    <Modal :open="isRenameOpen" title="Session umbenennen" size="sm" @update:open="isRenameOpen = $event">
      <div class="space-y-4">
        <Input
          label="Titel"
          v-model="renameTitle"
          autofocus
          @keydown.enter="handleRename"
        />
      </div>
      <template #footer>
        <Button variant="secondary" size="sm" @click="isRenameOpen = false">Abbrechen</Button>
        <Button variant="primary" size="sm" @click="handleRename">Speichern</Button>
      </template>
    </Modal>

    <!-- Delete Confirm Dialog -->
    <ConfirmDialog
      :open="isDeleteOpen"
      message="Möchtest du diese Session und ihren Verlauf wirklich löschen?"
      @update:open="isDeleteOpen = $event"
      @confirm="handleDelete"
    />

    <!-- Delete All Confirm Dialog -->
    <ConfirmDialog
      :open="isDeleteAllOpen"
      title="Alle Sessions löschen"
      message="Möchtest du wirklich alle Sessions und deren Verläufe unwiderruflich löschen? Die generierten Bilder in der Galerie bleiben erhalten."
      confirmText="Alle löschen"
      variant="danger"
      :loading="isDeletingAll"
      @update:open="isDeleteAllOpen = $event"
      @confirm="handleDeleteAll"
    />
  </aside>
</template>
