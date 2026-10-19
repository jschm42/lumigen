<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import Card from '@/components/ui/Card.vue'
import Checkbox from '@/components/ui/Checkbox.vue'

const router = useRouter()
const authStore = useAuthStore()
const toastStore = useToastStore()

const REMEMBER_USERNAME_KEY = 'lumigen_remember_username'

const username = ref('')
const password = ref('')
const rememberMe = ref(false)
const isLoading = ref(false)
const errorMessage = ref('')
const isUsernamePrefilled = ref(false)

const versionDisplay = computed(() => {
  const ver = authStore.appVersion
  if (!ver) return ''
  return ver.startsWith('v') ? ver : `v${ver}`
})

onMounted(() => {
  try {
    const savedUsername = localStorage.getItem(REMEMBER_USERNAME_KEY)
    if (savedUsername) {
      username.value = savedUsername
      rememberMe.value = true
      isUsernamePrefilled.value = true
    }
  } catch (_e) {
    // Local storage might be unavailable or restricted
  }
})

async function handleSubmit() {
  if (!username.value.trim() || !password.value) {
    errorMessage.value = 'Please enter username and password.'
    return
  }

  isLoading.value = true
  errorMessage.value = ''

  try {
    const res = await authStore.login({
      username: username.value.trim(),
      password: password.value,
      remember_me: rememberMe.value,
    })

    if (res.success) {
      try {
        if (rememberMe.value) {
          localStorage.setItem(REMEMBER_USERNAME_KEY, username.value.trim())
        } else {
          localStorage.removeItem(REMEMBER_USERNAME_KEY)
        }
      } catch (_e) {
        // Local storage might be unavailable
      }

      toastStore.success('Successfully logged in!')
      router.push('/')
    } else {
      errorMessage.value = res.message || 'Invalid credentials.'
    }
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || 'Invalid credentials.'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <div class="relative min-h-screen flex items-center justify-center p-4">
    <!-- Ambient background lighting -->
    <div class="pointer-events-none absolute inset-0 -z-10 flex items-center justify-center overflow-hidden">
      <div class="h-[440px] w-[440px] rounded-full bg-sky-500/10 blur-[100px]" />
      <div class="h-[340px] w-[340px] -translate-x-20 translate-y-16 rounded-full bg-indigo-500/10 blur-[90px]" />
    </div>

    <div class="w-full max-w-md space-y-6">
      <!-- Logo & Header -->
      <div class="text-center space-y-3">
        <div class="flex justify-center">
          <img
            src="/app-logo.svg"
            alt="Lumigen Logo"
            class="h-24 w-24 sm:h-28 sm:w-28 select-none invert dark:invert-0 drop-shadow-xl transition-transform duration-300 hover:scale-105"
          />
        </div>

        <div class="space-y-1.5">
          <div class="flex items-center justify-center gap-2.5">
            <h1 class="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-900 dark:text-white">
              Lumigen Studio
            </h1>
            <span
              v-if="versionDisplay"
              class="inline-flex items-center rounded-full bg-sky-500/10 px-2.5 py-0.5 text-xs font-semibold font-mono text-sky-600 dark:bg-sky-400/15 dark:text-sky-300 dark:border dark:border-sky-400/30"
              title="Studio Version"
            >
              {{ versionDisplay }}
            </span>
          </div>
          <p class="text-sm text-slate-500 dark:text-slate-400">
            Log in to access your studio
          </p>
        </div>
      </div>

      <!-- Login Form Card -->
      <Card padding="lg" class="shadow-2xl border border-slate-200/80 dark:border-white/10 dark:bg-slate-900/80 backdrop-blur-xl">
        <form @submit.prevent="handleSubmit" class="space-y-4">
          <!-- Error alert -->
          <div
            v-if="errorMessage"
            class="flex items-center gap-2.5 p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs font-medium text-rose-700 dark:bg-rose-950/50 dark:border-rose-800/70 dark:text-rose-300"
          >
            <svg class="h-4 w-4 shrink-0 text-rose-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
            </svg>
            <span>{{ errorMessage }}</span>
          </div>

          <!-- Username Input -->
          <Input
            id="username"
            label="Username"
            placeholder="admin"
            v-model="username"
            :disabled="isLoading"
            :autofocus="!isUsernamePrefilled"
          >
            <template #prefix>
              <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h14a7 7 0 00-7-7z" />
              </svg>
            </template>
          </Input>

          <!-- Password Input -->
          <Input
            id="password"
            type="password"
            label="Password"
            placeholder="••••••••"
            v-model="password"
            :disabled="isLoading"
            :autofocus="isUsernamePrefilled"
          >
            <template #prefix>
              <svg class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
              </svg>
            </template>
          </Input>

          <!-- Remember Me Checkbox -->
          <div class="flex items-center justify-between pt-1">
            <Checkbox
              id="remember-me"
              v-model="rememberMe"
              label="Remember me"
              :disabled="isLoading"
            />
          </div>

          <!-- Submit Button -->
          <div class="pt-2">
            <Button
              type="submit"
              variant="primary"
              size="lg"
              fullWidth
              :loading="isLoading"
            >
              Log in
            </Button>
          </div>
        </form>
      </Card>

      <!-- Footer Info -->
      <p v-if="versionDisplay" class="text-center text-xs text-slate-400 dark:text-slate-500 font-mono">
        Lumigen Studio {{ versionDisplay }}
      </p>
    </div>
  </div>
</template>
