<script setup lang="ts">
import { onMounted } from 'vue'
import { useGalleryStore } from '@/stores/gallery'
import { useGenerateStore } from '@/stores/generate'
import Modal from '@/components/ui/Modal.vue'
import Spinner from '@/components/ui/Spinner.vue'
import type { Asset } from '@/types'

interface Props {
  open: boolean
}

defineProps<Props>()

const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

const galleryStore = useGalleryStore()
const generateStore = useGenerateStore()

onMounted(() => {
  if (galleryStore.assets.length === 0) {
    galleryStore.fetchAssets(true)
  }
})

function selectAsset(asset: Asset) {
  generateStore.attachAssetAsImage(asset)
  emit('update:open', false)
}
</script>

<template>
  <Modal
    :open="open"
    title="Choose Input Image from Gallery"
    size="xl"
    @update:open="emit('update:open', $event)"
  >
    <div class="space-y-4">
      <p class="text-xs text-slate-500 dark:text-slate-400">
        Click an image from your gallery to use it as a reference or input image for your next prompt.
      </p>

      <!-- Loading spinner -->
      <div v-if="galleryStore.isLoading" class="py-16 flex justify-center">
        <Spinner size="lg" class="text-sky-500" />
      </div>

      <!-- Empty state -->
      <div
        v-else-if="galleryStore.assets.length === 0"
        class="py-12 text-center text-xs text-slate-500 dark:text-slate-400"
      >
        No gallery images available yet.
      </div>

      <!-- Gallery Grid for selection -->
      <div
        v-else
        class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5 gap-3 max-h-[60vh] overflow-y-auto p-1"
      >
        <div
          v-for="asset in galleryStore.assets"
          :key="asset.id"
          @click="selectAsset(asset)"
          class="group relative aspect-square rounded-xl overflow-hidden border border-slate-200 dark:border-white/10 hover:border-sky-500 dark:hover:border-sky-400 cursor-pointer shadow-sm hover:shadow-md transition-all duration-150 bg-slate-100 dark:bg-slate-800"
        >
          <img
            :src="asset.thumbnail_url || asset.image_url"
            :alt="asset.prompt"
            loading="lazy"
            class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-200"
          />
          <div class="absolute inset-0 bg-slate-900/60 opacity-0 group-hover:opacity-100 transition-opacity flex flex-col justify-end p-2 text-white">
            <span class="text-[10px] line-clamp-2 leading-tight">{{ asset.prompt }}</span>
            <span class="text-[9px] text-sky-300 mt-1 font-semibold">Select as input image ➔</span>
          </div>
        </div>
      </div>
    </div>
  </Modal>
</template>
