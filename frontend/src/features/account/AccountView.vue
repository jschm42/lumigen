<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { accountApi } from '@/api/account'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import { useCreditsStore } from '@/stores/credits'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import Badge from '@/components/ui/Badge.vue'

const authStore = useAuthStore()
const toastStore = useToastStore()
const creditsStore = useCreditsStore()

const username = ref('')
const displayName = ref('')
const email = ref('')
const isSavingProfile = ref(false)
const profileError = ref('')

const currentPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const isSavingPassword = ref(false)
const passwordError = ref('')

function fillForm() {
  const user = authStore.user
  username.value = user?.username || ''
  displayName.value = user?.display_name || ''
  email.value = user?.email || ''
}

onMounted(async () => {
  fillForm()
  try {
    authStore.setUser(await accountApi.getAccount())
    fillForm()
  } catch (_error) {
    // Keep the data from the auth status call.
  }
})

const isProfileDirty = computed(() => {
  const user = authStore.user
  if (!user) return false
  return (
    username.value.trim() !== user.username ||
    displayName.value.trim() !== (user.display_name || '') ||
    email.value.trim().toLowerCase() !== (user.email || '')
  )
})

const passwordStrength = computed(() => {
  const value = newPassword.value
  if (!value) return null
  let score = 0
  if (value.length >= authStore.passwordMinLength) score++
  if (value.length >= 14) score++
  if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score++
  if (/\d/.test(value)) score++
  if (/[^A-Za-z0-9]/.test(value)) score++
  if (score <= 2) return { label: 'Weak', width: '33%', color: 'bg-rose-500' }
  if (score <= 3) return { label: 'Okay', width: '66%', color: 'bg-amber-500' }
  return { label: 'Strong', width: '100%', color: 'bg-emerald-500' }
})

function formatDate(value?: string | null) {
  if (!value) return '—'
  return new Date(value).toLocaleString()
}

async function saveProfile() {
  profileError.value = ''
  isSavingProfile.value = true
  try {
    const updated = await accountApi.updateAccount({
      username: username.value.trim(),
      display_name: displayName.value.trim(),
      email: email.value.trim(),
    })
    authStore.setUser(updated)
    fillForm()
    toastStore.success('Profile saved.')
  } catch (error: any) {
    profileError.value = error?.response?.data?.detail || 'Profile could not be saved.'
  } finally {
    isSavingProfile.value = false
  }
}

async function savePassword() {
  passwordError.value = ''
  if (newPassword.value.trim().length < authStore.passwordMinLength) {
    passwordError.value = `New password must be at least ${authStore.passwordMinLength} characters.`
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    passwordError.value = 'New passwords do not match.'
    return
  }
  isSavingPassword.value = true
  try {
    await accountApi.changePassword(currentPassword.value, newPassword.value)
    currentPassword.value = ''
    newPassword.value = ''
    confirmPassword.value = ''
    toastStore.success('Password changed. Other sessions were signed out.')
  } catch (error: any) {
    passwordError.value = error?.response?.data?.detail || 'Password could not be changed.'
  } finally {
    isSavingPassword.value = false
  }
}
</script>

<template>
  <div class="h-full overflow-y-auto pb-16">
    <div class="mx-auto w-full max-w-3xl space-y-5 py-2">
      <!-- Identity header -->
      <section class="flex flex-col sm:flex-row sm:items-center gap-4 rounded-2xl border border-slate-200/80 bg-white/75 p-5 shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/75">
        <div class="flex h-16 w-16 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-tr from-sky-400 to-indigo-500 text-xl font-bold text-white shadow-lg shadow-sky-500/20">
          {{ authStore.initials }}
        </div>
        <div class="min-w-0 flex-1 space-y-1">
          <div class="flex flex-wrap items-center gap-2">
            <h2 class="truncate text-lg font-bold text-slate-900 dark:text-white">{{ authStore.displayName }}</h2>
            <Badge :variant="authStore.isAdmin ? 'sky' : 'slate'" size="xs" class="uppercase">
              {{ authStore.user?.role }}
            </Badge>
          </div>
          <p class="text-xs text-slate-500 dark:text-slate-400">
            @{{ authStore.user?.username }}
            <span v-if="authStore.user?.email"> · {{ authStore.user?.email }}</span>
          </p>
          <p class="text-[11px] text-slate-400">
            Member since {{ formatDate(authStore.user?.created_at) }} · Last login {{ formatDate(authStore.user?.last_login_at) }}
          </p>
        </div>
        <div class="flex gap-2 sm:flex-col">
          <Button variant="secondary" size="sm" @click="creditsStore.open()">Credits & Licenses</Button>
          <Button variant="ghost" size="sm" class="text-rose-500 hover:text-rose-600" @click="authStore.logout()">Sign out</Button>
        </div>
      </section>

      <!-- Profile -->
      <section class="rounded-2xl border border-slate-200/80 bg-white/75 p-5 shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/75">
        <div class="mb-4 space-y-0.5">
          <h3 class="text-sm font-bold text-slate-900 dark:text-white">Profile</h3>
          <p class="text-xs text-slate-500">Your e-mail address is used to deliver password reset links.</p>
        </div>
        <form @submit.prevent="saveProfile" class="grid gap-4 sm:grid-cols-2">
          <Input id="account-username" label="Username" v-model="username" :disabled="isSavingProfile" />
          <Input id="account-display-name" label="Display name" placeholder="Optional" v-model="displayName" :disabled="isSavingProfile" />
          <div class="sm:col-span-2">
            <Input id="account-email" type="email" label="E-mail" placeholder="you@example.com" v-model="email" :disabled="isSavingProfile" />
          </div>
          <p v-if="profileError" class="sm:col-span-2 text-xs font-medium text-rose-500">{{ profileError }}</p>
          <div class="sm:col-span-2 flex justify-end gap-2">
            <Button variant="ghost" size="sm" :disabled="!isProfileDirty || isSavingProfile" @click="fillForm">Reset</Button>
            <Button type="submit" variant="primary" size="sm" :loading="isSavingProfile" :disabled="!isProfileDirty">Save profile</Button>
          </div>
        </form>
      </section>

      <!-- Password -->
      <section class="rounded-2xl border border-slate-200/80 bg-white/75 p-5 shadow-sm backdrop-blur-xl dark:border-white/10 dark:bg-slate-900/75">
        <div class="mb-4 space-y-0.5">
          <h3 class="text-sm font-bold text-slate-900 dark:text-white">Password</h3>
          <p class="text-xs text-slate-500">Changing your password signs out all your other sessions.</p>
        </div>
        <form @submit.prevent="savePassword" class="grid gap-4 sm:grid-cols-2">
          <div class="sm:col-span-2">
            <Input id="account-current-password" type="password" label="Current password" v-model="currentPassword" :disabled="isSavingPassword" />
          </div>
          <div class="space-y-1.5">
            <Input id="account-new-password" type="password" label="New password" :placeholder="`Min. ${authStore.passwordMinLength} characters`" v-model="newPassword" :disabled="isSavingPassword" />
            <div v-if="passwordStrength" class="flex items-center gap-2">
              <div class="h-1 flex-1 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
                <div :class="['h-full rounded-full transition-all', passwordStrength.color]" :style="{ width: passwordStrength.width }" />
              </div>
              <span class="text-[10px] font-semibold text-slate-500">{{ passwordStrength.label }}</span>
            </div>
          </div>
          <Input id="account-confirm-password" type="password" label="Confirm new password" v-model="confirmPassword" :disabled="isSavingPassword" />
          <p v-if="passwordError" class="sm:col-span-2 text-xs font-medium text-rose-500">{{ passwordError }}</p>
          <div class="sm:col-span-2 flex justify-end">
            <Button
              type="submit"
              variant="primary"
              size="sm"
              :loading="isSavingPassword"
              :disabled="!currentPassword || !newPassword || !confirmPassword"
            >
              Change password
            </Button>
          </div>
        </form>
      </section>
    </div>
  </div>
</template>
