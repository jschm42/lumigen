<script setup lang="ts">
import { ref } from 'vue'
import { useGenerateStore } from '@/stores/generate'

const generateStore = useGenerateStore()
const isDragging = ref(false)
const fileInputRef = ref<HTMLInputElement | null>(null)

function handleDragOver(e: DragEvent) {
  e.preventDefault()
  isDragging.value = true
}

function handleDragLeave() {
  isDragging.value = false
}

function handleDrop(e: DragEvent) {
  e.preventDefault()
  isDragging.value = false
  if (e.dataTransfer?.files) {
    Array.from(e.dataTransfer.files).forEach((file) => {
      if (file.type.startsWith('image/')) {
        generateStore.addAttachedImage(file)
      }
    })
  }
}

function handleFileSelect(e: Event) {
  const target = e.target as HTMLInputElement
  if (target.files) {
    Array.from(target.files).forEach((file) => {
      generateStore.addAttachedImage(file)
    })
    target.value = ''
  }
}

function triggerFileInput() {
  fileInputRef.value?.click()
}
</script>

<template>
  <div
    class="space-y-2"
    @dragover="handleDragOver"
    @dragleave="handleDragLeave"
    @drop="handleDrop"
  >
    <!-- Thumbnail preview strip of attached reference images -->
    <div v-if="generateStore.attachedImages.length > 0" class="flex flex-wrap gap-2 items-center">
      <div
        v-for="img in generateStore.attachedImages"
        :key="img.id"
        class="relative group w-14 h-14 rounded-xl border border-slate-300/80 dark:border-white/20 overflow-hidden bg-slate-900 shadow-sm shrink-0"
      >
        <img :src="img.previewUrl" alt="" class="w-full h-full object-cover" />
        <button
          type="button"
          @click="generateStore.removeAttachedImage(img.id)"
          class="absolute top-1 right-1 w-4 h-4 rounded-full bg-rose-600 text-white flex items-center justify-center text-[10px] opacity-0 group-hover:opacity-100 transition-opacity"
          title="Entfernen"
        >
          ✕
        </button>
      </div>

      <button
        v-if="generateStore.attachedImages.length < 5"
        type="button"
        @click="triggerFileInput"
        class="w-14 h-14 rounded-xl border border-dashed border-slate-300 dark:border-white/20 hover:border-sky-400 flex flex-col items-center justify-center text-slate-400 hover:text-sky-500 transition-colors"
      >
        <span class="text-lg leading-none">+</span>
        <span class="text-[9px]">Bild</span>
      </button>
    </div>

    <!-- Upload trigger when empty -->
    <button
      v-else
      type="button"
      @click="triggerFileInput"
      :class="[
        'px-2.5 py-1 rounded-xl border transition-colors flex items-center gap-1 text-xs',
        isDragging
          ? 'border-sky-500 bg-sky-50 dark:bg-sky-950/40 text-sky-600'
          : 'border-slate-200 bg-white/80 text-slate-700 hover:border-slate-300 dark:border-white/10 dark:bg-slate-800/80 dark:text-slate-300',
      ]"
      title="Referenzbilder hochladen oder hineinziehen"
    >
      <span>🖼️</span> Bild
    </button>

    <input
      ref="fileInputRef"
      type="file"
      multiple
      accept="image/*"
      class="hidden"
      @change="handleFileSelect"
    />
  </div>
</template>
