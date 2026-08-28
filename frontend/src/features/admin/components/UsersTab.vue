<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { adminApi } from '@/api/admin'
import { useToastStore } from '@/stores/toast'
import Button from '@/components/ui/Button.vue'
import Modal from '@/components/ui/Modal.vue'
import Input from '@/components/ui/Input.vue'

const adminStore = useAdminStore()
const toastStore = useToastStore()

const isCreateOpen = ref(false)
const newUsername = ref('')
const newPassword = ref('')
const newRole = ref('user')
const isSaving = ref(false)

onMounted(() => {
  adminStore.fetchUsers()
})

async function handleCreateUser() {
  if (!newUsername.value.trim() || !newPassword.value) return
  isSaving.value = true
  try {
    await adminApi.createUser({
      username: newUsername.value.trim(),
      password: newPassword.value,
      role: newRole.value,
    })
    toastStore.success('Benutzer erfolgreich angelegt!')
    adminStore.fetchUsers()
    isCreateOpen.value = false
    newUsername.value = ''
    newPassword.value = ''
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Fehler beim Erstellen des Benutzers.')
  } finally {
    isSaving.value = false
  }
}

async function handleDeleteUser(userId: number, username: string) {
  if (confirm(`Möchtest du den Benutzer "${username}" wirklich löschen?`)) {
    try {
      await adminApi.deleteUser(userId)
      toastStore.success('Benutzer gelöscht.')
      adminStore.fetchUsers()
    } catch (error: any) {
      toastStore.error(error?.response?.data?.detail || 'Löschen fehlgeschlagen.')
    }
  }
}
</script>

<template>
  <div class="space-y-6 text-xs">
    <div class="flex items-center justify-between">
      <div class="space-y-0.5">
        <h3 class="text-sm font-bold text-slate-900 dark:text-white">Benutzerverwaltung</h3>
        <p class="text-slate-500">Verwalte Konten und Zugriffsrollen für dein Studio.</p>
      </div>

      <Button variant="primary" size="sm" @click="isCreateOpen = true">
        <template #icon>+</template>
        Benutzer anlegen
      </Button>
    </div>

    <!-- Users Table -->
    <div class="rounded-2xl border border-slate-200/80 bg-white/70 backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/70 overflow-hidden shadow-sm">
      <table class="w-full text-left border-collapse">
        <thead>
          <tr class="border-b border-slate-200 dark:border-white/10 text-slate-500 text-[11px] font-semibold uppercase tracking-wider bg-slate-50/50 dark:bg-slate-950/40">
            <th class="p-3.5">ID</th>
            <th class="p-3.5">Benutzername</th>
            <th class="p-3.5">Rolle</th>
            <th class="p-3.5 text-right">Aktionen</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-200/60 dark:divide-white/10">
          <tr
            v-for="u in adminStore.users"
            :key="u.id"
            class="hover:bg-slate-50/50 dark:hover:bg-white/5 transition-colors"
          >
            <td class="p-3.5 font-mono text-slate-400">#{{ u.id }}</td>
            <td class="p-3.5 font-bold text-slate-900 dark:text-white">{{ u.username }}</td>
            <td class="p-3.5">
              <span
                :class="[
                  'px-2 py-0.5 rounded-full text-[10px] font-bold uppercase',
                  u.role === 'admin'
                    ? 'bg-sky-100 text-sky-800 dark:bg-sky-950/60 dark:text-sky-300'
                    : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
                ]"
              >
                {{ u.role }}
              </span>
            </td>
            <td class="p-3.5 text-right">
              <button
                type="button"
                @click="handleDeleteUser(u.id, u.username)"
                class="text-rose-500 hover:text-rose-400 font-semibold"
              >
                Löschen
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create User Modal -->
    <Modal
      :open="isCreateOpen"
      title="Neuen Benutzer anlegen"
      size="sm"
      @update:open="isCreateOpen = $event"
    >
      <form @submit.prevent="handleCreateUser" class="space-y-4">
        <Input
          label="Benutzername"
          v-model="newUsername"
          required
        />
        <Input
          label="Passwort"
          type="password"
          v-model="newPassword"
          required
        />
        <div>
          <label class="block font-semibold uppercase tracking-wider text-[11px] text-slate-500 mb-1.5">
            Rolle
          </label>
          <select
            v-model="newRole"
            class="w-full rounded-xl border border-slate-300/80 bg-white px-3 py-2 text-xs text-slate-900 dark:border-white/10 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="user">Benutzer (Standard)</option>
            <option value="admin">Administrator</option>
          </select>
        </div>
      </form>

      <template #footer>
        <Button variant="secondary" size="sm" @click="isCreateOpen = false">Abbrechen</Button>
        <Button variant="primary" size="sm" :loading="isSaving" @click="handleCreateUser">Erstellen</Button>
      </template>
    </Modal>
  </div>
</template>
