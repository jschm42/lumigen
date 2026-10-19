<script setup lang="ts">
import { ref } from 'vue'
import { authApi } from '@/api/auth'
import Button from '@/components/ui/Button.vue'
import Input from '@/components/ui/Input.vue'
import AuthShell from './components/AuthShell.vue'

const identifier = ref('')
const isLoading = ref(false)
const errorMessage = ref('')
const isSubmitted = ref(false)

async function handleSubmit() {
  if (!identifier.value.trim()) {
    errorMessage.value = 'Please enter your username or e-mail address.'
    return
  }
  isLoading.value = true
  errorMessage.value = ''
  try {
    await authApi.forgotPassword(identifier.value.trim())
    isSubmitted.value = true
  } catch (error: any) {
    errorMessage.value = error?.response?.data?.detail || 'Request failed. Please try again.'
  } finally {
    isLoading.value = false
  }
}
</script>

<template>
  <AuthShell title="Forgot password" subtitle="We will create a single-use link to choose a new password.">
    <div v-if="isSubmitted" class="space-y-4 text-sm" data-testid="forgot-password-success">
      <div class="p-3 rounded-xl bg-emerald-50 border border-emerald-200 text-emerald-800 dark:bg-emerald-950/40 dark:border-emerald-800/60 dark:text-emerald-300">
        If an account matches <strong>{{ identifier }}</strong>, a reset link has been issued.
      </div>
      <ul class="list-disc pl-5 space-y-1 text-xs text-slate-500 dark:text-slate-400">
        <li>With e-mail delivery configured, check your inbox (the link is valid for a limited time).</li>
        <li>Otherwise ask your studio administrator — they can find the link in the server log or create a new one under Admin → Users.</li>
      </ul>
      <router-link to="/login">
        <Button variant="secondary" size="md" fullWidth>Back to login</Button>
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
        id="identifier"
        label="Username or e-mail"
        placeholder="admin or you@example.com"
        v-model="identifier"
        :disabled="isLoading"
        autofocus
      />

      <Button type="submit" variant="primary" size="lg" fullWidth :loading="isLoading">
        Send reset link
      </Button>
    </form>

    <template #footer>
      <router-link to="/login" class="hover:text-sky-500 transition-colors">← Back to login</router-link>
    </template>
  </AuthShell>
</template>
