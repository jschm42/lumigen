<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAdminStore } from '@/stores/admin'
import { useAuthStore } from '@/stores/auth'
import { adminApi } from '@/api/admin'
import { useToastStore } from '@/stores/toast'
import Button from '@/components/ui/Button.vue'
import Modal from '@/components/ui/Modal.vue'
import Input from '@/components/ui/Input.vue'
import Switch from '@/components/ui/Switch.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import type { User } from '@/types'

type Role = 'admin' | 'user'

const adminStore = useAdminStore()
const authStore = useAuthStore()
const toastStore = useToastStore()

const search = ref('')

// Create / edit modal
const isEditorOpen = ref(false)
const editingUser = ref<User | null>(null)
const formUsername = ref('')
const formDisplayName = ref('')
const formEmail = ref('')
const formPassword = ref('')
const formRole = ref<Role>('user')
const formActive = ref(true)
const formError = ref('')
const isSaving = ref(false)

// Password modal
const passwordUser = ref<User | null>(null)
const passwordValue = ref('')
const passwordError = ref('')
const isSavingPassword = ref(false)

// Reset link modal
const resetLink = ref<{ user: User; url: string; expiresAt: string } | null>(null)
const creatingLinkFor = ref<number | null>(null)

// Delete confirm
const deleteTarget = ref<User | null>(null)
const isDeleting = ref(false)

onMounted(() => {
  adminStore.fetchUsers()
})

const filteredUsers = computed(() => {
  const q = search.value.trim().toLowerCase()
  if (!q) return adminStore.users
  return adminStore.users.filter((u) =>
    [u.username, u.display_name, u.email, u.role].some((v) => (v || '').toLowerCase().includes(q))
  )
})

const stats = computed(() => {
  const users = adminStore.users
  return {
    total: users.length,
    admins: users.filter((u) => u.role === 'admin').length,
    inactive: users.filter((u) => u.is_active === false).length,
  }
})

function isSelf(user: User) {
  return authStore.user?.id === user.id
}

function formatDate(value?: string | null) {
  if (!value) return 'Never'
  return new Date(value).toLocaleString()
}

function openCreate() {
  editingUser.value = null
  formUsername.value = ''
  formDisplayName.value = ''
  formEmail.value = ''
  formPassword.value = ''
  formRole.value = 'user'
  formActive.value = true
  formError.value = ''
  isEditorOpen.value = true
}

function openEdit(user: User) {
  editingUser.value = user
  formUsername.value = user.username
  formDisplayName.value = user.display_name || ''
  formEmail.value = user.email || ''
  formPassword.value = ''
  formRole.value = user.role
  formActive.value = user.is_active !== false
  formError.value = ''
  isEditorOpen.value = true
}

async function saveUser() {
  formError.value = ''
  if (!formUsername.value.trim()) {
    formError.value = 'Username is required.'
    return
  }
  if (!editingUser.value && formPassword.value.trim().length < authStore.passwordMinLength) {
    formError.value = `Password must be at least ${authStore.passwordMinLength} characters.`
    return
  }
  isSaving.value = true
  const payload = {
    username: formUsername.value.trim(),
    display_name: formDisplayName.value.trim(),
    email: formEmail.value.trim(),
    role: formRole.value,
    is_active: formActive.value,
  }
  try {
    if (editingUser.value) {
      await adminApi.updateUser(editingUser.value.id, payload)
      toastStore.success('User updated.')
    } else {
      await adminApi.createUser({ ...payload, password: formPassword.value })
      toastStore.success('User created.')
    }
    isEditorOpen.value = false
    adminStore.fetchUsers()
  } catch (error: any) {
    formError.value = error?.response?.data?.detail || 'Saving failed.'
  } finally {
    isSaving.value = false
  }
}

async function toggleActive(user: User) {
  try {
    await adminApi.updateUser(user.id, { is_active: user.is_active === false })
    toastStore.success(user.is_active === false ? 'User activated.' : 'User deactivated and signed out.')
    adminStore.fetchUsers()
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Update failed.')
  }
}

function openPassword(user: User) {
  passwordUser.value = user
  passwordValue.value = ''
  passwordError.value = ''
}

async function savePassword() {
  if (!passwordUser.value) return
  if (passwordValue.value.trim().length < authStore.passwordMinLength) {
    passwordError.value = `Password must be at least ${authStore.passwordMinLength} characters.`
    return
  }
  isSavingPassword.value = true
  try {
    await adminApi.setUserPassword(passwordUser.value.id, passwordValue.value)
    toastStore.success(`Password for ${passwordUser.value.username} updated. Their sessions were signed out.`)
    passwordUser.value = null
  } catch (error: any) {
    passwordError.value = error?.response?.data?.detail || 'Password could not be set.'
  } finally {
    isSavingPassword.value = false
  }
}

async function createResetLink(user: User) {
  creatingLinkFor.value = user.id
  try {
    const res = await adminApi.createUserResetLink(user.id)
    resetLink.value = { user, url: res.reset_url, expiresAt: res.expires_at }
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Reset link could not be created.')
  } finally {
    creatingLinkFor.value = null
  }
}

async function copyResetLink() {
  if (!resetLink.value) return
  try {
    await navigator.clipboard.writeText(resetLink.value.url)
    toastStore.success('Reset link copied to clipboard.')
  } catch (_error) {
    toastStore.error('Copy failed. Please select the link manually.')
  }
}

async function confirmDelete() {
  if (!deleteTarget.value) return
  isDeleting.value = true
  try {
    await adminApi.deleteUser(deleteTarget.value.id)
    toastStore.success('User deleted.')
    adminStore.fetchUsers()
    deleteTarget.value = null
  } catch (error: any) {
    toastStore.error(error?.response?.data?.detail || 'Deletion failed.')
  } finally {
    isDeleting.value = false
  }
}
</script>

<template>
  <div class="space-y-5 text-xs">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div class="space-y-0.5">
        <h3 class="text-sm font-bold text-slate-900 dark:text-white">User Management</h3>
        <p class="text-slate-500">
          {{ stats.total }} accounts · {{ stats.admins }} admins<span v-if="stats.inactive"> · {{ stats.inactive }} inactive</span>
        </p>
      </div>

      <div class="flex items-center gap-2">
        <input
          v-model="search"
          type="search"
          placeholder="Search users..."
          class="w-48 rounded-xl border border-slate-300/80 bg-white/70 px-3 py-1.5 text-xs text-slate-800 placeholder-slate-400 focus:outline-none focus:ring-1 focus:ring-sky-500 dark:border-white/10 dark:bg-slate-900/70 dark:text-slate-200"
        />
        <Button variant="primary" size="sm" @click="openCreate" data-testid="add-user">
          <template #icon>+</template>
          Add User
        </Button>
      </div>
    </div>

    <div class="overflow-x-auto rounded-2xl border border-slate-200/80 bg-white/70 shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/70">
      <table class="w-full min-w-[720px] border-collapse text-left">
        <thead>
          <tr class="border-b border-slate-200 bg-slate-50/50 text-[11px] font-semibold uppercase tracking-wider text-slate-500 dark:border-white/10 dark:bg-slate-950/40">
            <th class="p-3">User</th>
            <th class="p-3">Role</th>
            <th class="p-3">Status</th>
            <th class="p-3">Last login</th>
            <th class="p-3 text-right">Actions</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-200/60 dark:divide-white/10">
          <tr
            v-for="u in filteredUsers"
            :key="u.id"
            :class="['transition-colors hover:bg-slate-50/50 dark:hover:bg-white/5', u.is_active === false ? 'opacity-60' : '']"
          >
            <td class="p-3">
              <div class="flex items-center gap-2.5">
                <span class="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-gradient-to-tr from-sky-400 to-indigo-500 text-[11px] font-bold text-white">
                  {{ (u.display_name || u.username).charAt(0).toUpperCase() }}
                </span>
                <div class="min-w-0">
                  <div class="flex items-center gap-1.5 font-bold text-slate-900 dark:text-white">
                    <span class="truncate">{{ u.display_name || u.username }}</span>
                    <span v-if="isSelf(u)" class="rounded bg-sky-500/15 px-1 text-[9px] font-bold text-sky-600 dark:text-sky-300">YOU</span>
                  </div>
                  <div class="truncate text-[11px] text-slate-500">
                    @{{ u.username }}<span v-if="u.email"> · {{ u.email }}</span>
                    <span v-else class="italic text-amber-600 dark:text-amber-400"> · no e-mail</span>
                  </div>
                </div>
              </div>
            </td>
            <td class="p-3">
              <span
                :class="[
                  'rounded-full px-2 py-0.5 text-[10px] font-bold uppercase',
                  u.role === 'admin'
                    ? 'bg-sky-100 text-sky-800 dark:bg-sky-950/60 dark:text-sky-300'
                    : 'bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300',
                ]"
              >
                {{ u.role }}
              </span>
            </td>
            <td class="p-3">
              <span :class="['inline-flex items-center gap-1.5 text-[11px] font-medium', u.is_active === false ? 'text-slate-400' : 'text-emerald-600 dark:text-emerald-400']">
                <span :class="['h-1.5 w-1.5 rounded-full', u.is_active === false ? 'bg-slate-400' : 'bg-emerald-500']" />
                {{ u.is_active === false ? 'Inactive' : 'Active' }}
              </span>
            </td>
            <td class="p-3 text-[11px] text-slate-500">{{ formatDate(u.last_login_at) }}</td>
            <td class="p-3">
              <div class="flex flex-wrap items-center justify-end gap-1">
                <Button variant="ghost" size="xs" @click="openEdit(u)">Edit</Button>
                <Button variant="ghost" size="xs" @click="openPassword(u)">Set password</Button>
                <Button
                  variant="ghost"
                  size="xs"
                  :loading="creatingLinkFor === u.id"
                  :disabled="u.is_active === false"
                  @click="createResetLink(u)"
                >
                  Reset link
                </Button>
                <Button v-if="!isSelf(u)" variant="ghost" size="xs" @click="toggleActive(u)">
                  {{ u.is_active === false ? 'Activate' : 'Deactivate' }}
                </Button>
                <Button
                  v-if="!isSelf(u)"
                  variant="ghost"
                  size="xs"
                  class="text-rose-500 hover:text-rose-600"
                  @click="deleteTarget = u"
                >
                  Delete
                </Button>
              </div>
            </td>
          </tr>
          <tr v-if="filteredUsers.length === 0">
            <td colspan="5" class="p-6 text-center text-slate-400">No users found.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Create / Edit Modal -->
    <Modal
      :open="isEditorOpen"
      :title="editingUser ? `Edit ${editingUser.username}` : 'Create New User'"
      size="sm"
      @update:open="isEditorOpen = $event"
    >
      <form @submit.prevent="saveUser" class="space-y-4">
        <Input id="user-username" label="Username" v-model="formUsername" />
        <Input id="user-display-name" label="Display name" placeholder="Optional" v-model="formDisplayName" />
        <Input id="user-email" type="email" label="E-mail" placeholder="Optional, needed for reset e-mails" v-model="formEmail" />
        <Input
          v-if="!editingUser"
          id="user-password"
          type="password"
          label="Password"
          :placeholder="`Min. ${authStore.passwordMinLength} characters`"
          v-model="formPassword"
        />
        <div>
          <label class="mb-1.5 block text-[11px] font-semibold uppercase tracking-wider text-slate-500">Role</label>
          <select
            v-model="formRole"
            :disabled="!!editingUser && isSelf(editingUser)"
            class="w-full rounded-xl border border-slate-300/80 bg-white px-3 py-2 text-xs text-slate-900 disabled:opacity-50 dark:border-white/10 dark:bg-slate-900 dark:text-slate-100"
          >
            <option value="user">User (Standard)</option>
            <option value="admin">Administrator</option>
          </select>
        </div>
        <Switch
          v-if="!editingUser || !isSelf(editingUser)"
          v-model="formActive"
          label="Account active"
          description="Inactive users cannot sign in."
        />
        <p v-if="formError" class="text-xs font-medium text-rose-500">{{ formError }}</p>
      </form>

      <template #footer>
        <Button variant="secondary" size="sm" @click="isEditorOpen = false">Cancel</Button>
        <Button variant="primary" size="sm" :loading="isSaving" @click="saveUser">
          {{ editingUser ? 'Save' : 'Create' }}
        </Button>
      </template>
    </Modal>

    <!-- Set Password Modal -->
    <Modal
      :open="!!passwordUser"
      :title="`Set password for ${passwordUser?.username || ''}`"
      size="sm"
      @update:open="(v: boolean) => { if (!v) passwordUser = null }"
    >
      <form @submit.prevent="savePassword" class="space-y-3">
        <Input
          id="admin-set-password"
          type="password"
          label="New password"
          :placeholder="`Min. ${authStore.passwordMinLength} characters`"
          v-model="passwordValue"
          autofocus
        />
        <p class="text-[11px] text-slate-500">All active sessions of this user will be signed out.</p>
        <p v-if="passwordError" class="text-xs font-medium text-rose-500">{{ passwordError }}</p>
      </form>
      <template #footer>
        <Button variant="secondary" size="sm" @click="passwordUser = null">Cancel</Button>
        <Button variant="primary" size="sm" :loading="isSavingPassword" @click="savePassword">Set password</Button>
      </template>
    </Modal>

    <!-- Reset Link Modal -->
    <Modal
      :open="!!resetLink"
      title="Password reset link"
      size="md"
      @update:open="(v: boolean) => { if (!v) resetLink = null }"
    >
      <div v-if="resetLink" class="space-y-3 text-xs">
        <p class="text-slate-600 dark:text-slate-300">
          Send this single-use link to <strong>{{ resetLink.user.display_name || resetLink.user.username }}</strong>.
          It expires {{ formatDate(resetLink.expiresAt) }}. Creating a new link invalidates older ones.
        </p>
        <div class="flex items-center gap-2">
          <input
            :value="resetLink.url"
            readonly
            class="flex-1 rounded-xl border border-slate-300/80 bg-slate-50 px-3 py-2 font-mono text-[11px] text-slate-800 dark:border-white/10 dark:bg-slate-950 dark:text-slate-200"
            @focus="($event.target as HTMLInputElement).select()"
          />
          <Button variant="primary" size="sm" @click="copyResetLink">Copy</Button>
        </div>
      </div>
      <template #footer>
        <Button variant="secondary" size="sm" @click="resetLink = null">Close</Button>
      </template>
    </Modal>

    <ConfirmDialog
      :open="!!deleteTarget"
      title="Delete user"
      :message="`Do you really want to delete user “${deleteTarget?.username || ''}”? This cannot be undone.`"
      confirmText="Delete"
      variant="danger"
      :loading="isDeleting"
      @update:open="(v: boolean) => { if (!v) deleteTarget = null }"
      @confirm="confirmDelete"
    />
  </div>
</template>
