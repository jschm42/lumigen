<script setup lang="ts">
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import { useConfirmStore } from '@/stores/confirm'

const confirmStore = useConfirmStore()
</script>

<template>
  <ConfirmDialog
    :open="confirmStore.isOpen"
    :title="confirmStore.options.title"
    :message="confirmStore.options.message"
    :confirm-text="confirmStore.options.confirmText"
    :cancel-text="confirmStore.options.cancelText"
    :variant="confirmStore.options.variant"
    @confirm="confirmStore.settle(true)"
    @update:open="!$event && confirmStore.settle(false)"
  />
</template>
