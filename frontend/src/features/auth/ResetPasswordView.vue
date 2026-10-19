<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { authApi } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'
import { useToastStore } from '@/stores/toast'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import Spinner from '@/components/ui/Spinner.vue'
import AuthShell from './components/AuthShell.vue'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const toastStore = useToastStore()

const token = computed(() => String(route.query.token || ''))
const isValidating = ref(true)
const isTokenValid = ref(false)
const password = ref('')
const confirmPassword = ref('')
const isLoading = ref(false)
const errorMessage = ref('')

onMounted(async () => {
  if (!token.value) {
    isValidating.value = false
    return
  }
  try {
    const res = await authApi.validateResetToken(token.value)
    isTokenValid.value = res.valid
  } catch (_error) {
    isTokenValid.value = false
  } finally {
    isValidating.value = false
  }
})

async function handleSubmit() {
  errorMessage.value = ''
  if (password.value.trim().length < authStore.passwordMinLength) {
    errorMessage.value = `Password must be at least ${authStore.passwordMinLength} characters.`
    return
  }
  if (password.value !== confirmPassword.value) {
    errorMessage.value = 'Passwords do not match.'
    return
  }
  isLoading.value = true
  try {
    await authApi.resetPassword(token.value, password.value)
    toastStore.success('Password updated. Please log in with your new password.')
    // The reset signs out every session, including a possibly active one in this browser.
    await authStore.checkAuth()
    router.push('/login')
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || 'Password could not be reset.'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <AuthShell title="Choose a new password" subtitle="All other sessions of your account will be signed out.">
    <div v-if="isValidating" class="py-8 flex justify-center">
      <Spinner size="lg" class="text-sky-500" />
    </div>

    <div v-else-if="!isTokenValid" class="space-y-4 text-sm">
      <div class="p-3 rounded-xl bg-amber-50 border border-amber-200 text-amber-800 dark:bg-amber-950/40 dark:border-amber-800/60 dark:text-amber-300">
        This reset link is invalid, was already used or has expired.
      </div>
      <router-link to="/forgot-password">
        <Button variant="primary" size="md" fullWidth>Request a new link</Button>
      </router-link>
    </div>

    <form v-else @submit.prevent="handleSubmit" class="space-y-4">
      <div
        v-if="errorMessage"
        class="p-3 rounded-xl bg-rose-50 border border-rose-200 text-xs font-medium text-rose-700 dark:bg-rose-950/50 dark:border-rose-800/70 dark:text-rose-300"
      >
        {{ errorMessage }}
      </div>

      <Input
        id="new-password"
        type="password"
        label="New password"
        :placeholder="`At least ${authStore.passwordMinLength} characters`"
        v-model="password"
        :disabled="isLoading"
        autofocus
      />
      <Input
        id="confirm-password"
        type="password"
        label="Confirm new password"
        v-model="confirmPassword"
        :disabled="isLoading"
      />

      <Button type="submit" variant="primary" size="lg" fullWidth :loading="isLoading">
        Set new password
      </Button>
    </form>

    <template #footer>
      <router-link to="/login" class="hover:text-sky-500 transition-colors">← Back to login</router-link>
    </template>
  </AuthShell>
</template>
