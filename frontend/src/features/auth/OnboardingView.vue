<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import Card from '@/components/ui/Card.vue'

const router = useRouter()
const authStore = useAuthStore()
const toastStore = useToastStore()

const username = ref('')
const password = ref('')
const confirmPassword = ref('')
const isLoading = ref(false)
const errorMessage = ref('')

async function handleSetup() {
  if (!username.value.trim() || !password.value) {
    errorMessage.value = 'Please fill in all fields.'
    return
  }

  if (password.value !== confirmPassword.value) {
    errorMessage.value = 'Passwords do not match.'
    return
  }

  if (password.value.length < 6) {
    errorMessage.value = 'Password must be at least 6 characters.'
    return
  }

  isLoading.value = true
  errorMessage.value = ''

  try {
    const res = await authStore.setupAdmin({
      username: username.value.trim(),
      password: password.value,
    })

    if (res.success) {
      toastStore.success('Admin account successfully created!')
      router.push('/')
    } else {
      errorMessage.value = res.message || 'Setup failed.'
    }
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || 'Error during initialization.'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center p-4">
    <div class="w-full max-w-md space-y-6">
      <!-- Header -->
      <div class="text-center space-y-2">
        <div class="inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-sky-400/40 bg-slate-200/80 dark:border-sky-300/30 dark:bg-slate-900/70 shadow-lg">
          <img src="/app-logo.svg" alt="Lumigen" class="h-12 w-12 rounded-xl invert dark:invert-0" />
        </div>
        <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Welcome to Lumigen</h1>
        <p class="text-sm text-slate-500 dark:text-slate-400">Create the primary administrator account for your local studio</p>
      </div>

      <Card padding="lg">
        <form @submit.prevent="handleSetup" class="space-y-4">
          <div v-if="errorMessage" class="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs font-medium text-rose-700 dark:bg-rose-950/40 dark:border-rose-800/60 dark:text-rose-300">
            {{ errorMessage }}
          </div>

          <Input
            id="admin-username"
            label="Admin Username"
            placeholder="admin"
            v-model="username"
            :disabled="isLoading"
            autofocus
          />

          <Input
            id="admin-password"
            type="password"
            label="Password (min. 6 characters)"
            placeholder="••••••••"
            v-model="password"
            :disabled="isLoading"
          />

          <Input
            id="admin-confirm-password"
            type="password"
            label="Confirm Password"
            placeholder="••••••••"
            v-model="confirmPassword"
            :disabled="isLoading"
          />

          <div class="pt-2">
            <Button
              type="submit"
              variant="primary"
              size="lg"
              fullWidth
              :loading="isLoading"
            >
              Set up Studio
            </Button>
          </div>
        </form>
      </Card>
    </div>
  </div>
</template>
