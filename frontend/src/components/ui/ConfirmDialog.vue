<script setup lang="ts">
import Modal from './Modal.vue'
import Button from './Button.vue'

interface Props {
  open: boolean
  title?: string
  message: string
  confirmText?: string
  cancelText?: string
  variant?: 'danger' | 'primary'
  loading?: boolean
}

withDefaults(defineProps<Props>(), {
  title: 'Bestätigung erforderlich',
  confirmText: 'Bestätigen',
  cancelText: 'Abbrechen',
  variant: 'danger',
  loading: false,
})

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

function handleConfirm() {
  emit('confirm')
}

function handleCancel() {
  emit('update:open', false)
  emit('cancel')
}
</script>

<template>
  <Modal :open="open" :title="title" size="sm" @update:open="emit('update:open', $event)">
    <p class="text-sm text-slate-600 dark:text-slate-300">
      {{ message }}
    </p>

    <template #footer>
      <Button variant="secondary" size="sm" @click="handleCancel" :disabled="loading">
        {{ cancelText }}
      </Button>
      <Button :variant="variant" size="sm" :loading="loading" @click="handleConfirm">
        {{ confirmText }}
      </Button>
    </template>
  </Modal>
</template>
