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
const isLoading = ref(false)
const errorMessage = ref('')

async function handleSubmit() {
  if (!username.value.trim() || !password.value) {
    errorMessage.value = 'Bitte Benutzername und Passwort eingeben.'
    return
  }

  isLoading.value = true
  errorMessage.value = ''

  try {
    const res = await authStore.login({
      username: username.value.trim(),
      password: password.value,
    })

    if (res.success) {
      toastStore.success('Erfolgreich angemeldet!')
      router.push('/')
    } else {
      errorMessage.value = res.message || 'Ungültige Anmeldedaten.'
    }
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || 'Anmeldung fehlgeschlagen.'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="min-h-screen flex items-center justify-center p-4">
    <div class="w-full max-w-md space-y-6">
      <!-- Logo & Header -->
      <div class="text-center space-y-2">
        <div class="inline-flex h-14 w-14 items-center justify-center rounded-2xl border border-sky-400/40 bg-slate-200/80 dark:border-sky-300/30 dark:bg-slate-900/70 shadow-lg">
          <img src="/app-logo.svg" alt="Lumigen" class="h-12 w-12 rounded-xl invert dark:invert-0" />
        </div>
        <h1 class="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Lumigen Studio</h1>
        <p class="text-sm text-slate-500 dark:text-slate-400">Melde dich an, um auf dein Studio zuzugreifen</p>
      </div>

      <!-- Login Form -->
      <Card padding="lg">
        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div v-if="errorMessage" class="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs font-medium text-rose-700 dark:bg-rose-950/40 dark:border-rose-800/60 dark:text-rose-300">
            {{ errorMessage }}
          </div>

          <Input
            id="username"
            label="Benutzername"
            placeholder="admin"
            v-model="username"
            :disabled="isLoading"
            autofocus
          />

          <Input
            id="password"
            type="password"
            label="Passwort"
            placeholder="••••••••"
            v-model="password"
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
              Anmelden
            </Button>
          </div>
        </form>
      </Card>
    </div>
  </div>
</template>
