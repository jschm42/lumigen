<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { Asset } from '@/types'
import { useGalleryStore } from '@/stores/gallery'
import Modal from '@/components/ui/Modal.vue'
import Button from '@/components/ui/Button.vue'

interface Props {
  open: boolean
  assets: Asset[]
}

const props = defineProps<Props>()
const emit = defineEmits<{
  (e: 'update:open', value: boolean): void
}>()

const galleryStore = useGalleryStore()

const ZOOM_LEVELS = [1, 2, 4] as const
const zoom = ref<(typeof ZOOM_LEVELS)[number]>(1)
// Shared pan position (percent) so every image shows the same region.
const origin = ref({ x: 50, y: 50 })
const removedIds = ref<number[]>([])

watch(
  () => props.open,
  (open) => {
    if (open) {
      zoom.value = 1
      origin.value = { x: 50, y: 50 }
      removedIds.value = []
    }
  }
)

const items = computed(() => props.assets.filter((a) => !removedIds.value.includes(a.id)).slice(0, 4))

const gridClass = computed(() => {
  switch (items.value.length) {
    case 1:
      return 'grid-cols-1'
    case 2:
      return 'grid-cols-1 md:grid-cols-2'
    case 3:
      return 'grid-cols-1 md:grid-cols-3'
    default:
      return 'grid-cols-1 md:grid-cols-2 xl:grid-cols-4'
  }
})

function cycleZoom() {
  const index = ZOOM_LEVELS.indexOf(zoom.value)
  zoom.value = ZOOM_LEVELS[(index + 1) % ZOOM_LEVELS.length]
}

function handlePan(e: MouseEvent) {
  if (zoom.value === 1) return
  const rect = (e.currentTarget as HTMLElement).getBoundingClientRect()
  origin.value = {
    x: Math.min(100, Math.max(0, ((e.clientX - rect.left) / rect.width) * 100)),
    y: Math.min(100, Math.max(0, ((e.clientY - rect.top) / rect.height) * 100)),
  }
}

function rate(asset: Asset, star: number) {
  galleryStore.rateAsset(asset, (asset.rating || 0) === star ? 0 : star)
}

function openDetails(asset: Asset) {
  emit('update:open', false)
  galleryStore.openDetailModal(asset)
}

function keepOnly(asset: Asset) {
  galleryStore.setSelection([asset.id])
  emit('update:open', false)
}
</script>

<template>
  <Modal :open="open" size="full" @update:open="emit('update:open', $event)">
    <template #header>
      <div class="flex w-full flex-wrap items-center justify-between gap-3 pr-6 text-xs">
        <h3 class="text-sm font-bold text-slate-900 dark:text-white">Compare {{ items.length }} images</h3>
        <div class="flex items-center gap-2">
          <span class="hidden text-[11px] text-slate-400 md:inline">
            Click an image to zoom; move the mouse to pan all images together.
          </span>
          <div class="inline-flex rounded-xl border border-slate-300/80 p-0.5 dark:border-white/10">
            <button
              v-for="level in ZOOM_LEVELS"
              :key="level"
              type="button"
              @click="zoom = level"
              :class="[
                'cursor-pointer rounded-lg px-2 py-1 text-[11px] font-bold',
                zoom === level ? 'bg-sky-500 text-white' : 'text-slate-500 hover:text-slate-900 dark:hover:text-white',
              ]"
            >
              {{ level }}×
            </button>
          </div>
        </div>
      </div>
    </template>

    <div :class="['grid h-full gap-3', gridClass]" data-testid="compare-grid">
      <section
        v-for="asset in items"
        :key="asset.id"
        class="flex min-h-0 flex-col gap-2 rounded-2xl border border-slate-200/80 bg-slate-50/50 p-2 dark:border-white/10 dark:bg-slate-950/40"
      >
        <div
          :class="[
            'relative flex min-h-[260px] flex-1 items-center justify-center overflow-hidden rounded-xl bg-slate-950',
            zoom === 1 ? 'cursor-zoom-in' : 'cursor-zoom-out',
          ]"
          @click="cycleZoom"
          @mousemove="handlePan"
        >
          <img
            :src="asset.image_url || asset.thumbnail_url"
            :alt="asset.prompt"
            draggable="false"
            class="max-h-[62vh] max-w-full select-none object-contain transition-transform duration-150 ease-out"
            :style="{ transform: `scale(${zoom})`, transformOrigin: `${origin.x}% ${origin.y}%` }"
          />
          <span class="absolute left-2 top-2 rounded-md bg-black/60 px-1.5 py-0.5 font-mono text-[10px] text-white">
            #{{ asset.id }}
          </span>
        </div>

        <div class="space-y-1.5 px-1 text-[11px]">
          <div class="flex items-center justify-between gap-2">
            <div class="flex items-center gap-0.5">
              <button
                v-for="star in [1, 2, 3, 4, 5]"
                :key="star"
                type="button"
                @click="rate(asset, star)"
                class="cursor-pointer text-base leading-none text-amber-400 transition-transform hover:scale-110"
                :title="`${star} stars`"
              >
                {{ (asset.rating || 0) >= star ? '★' : '☆' }}
              </button>
            </div>
            <span class="truncate font-mono text-slate-500">
              {{ asset.width && asset.height ? `${asset.width}×${asset.height}` : asset.aspect_ratio }}
            </span>
          </div>
          <div class="truncate font-medium text-sky-700 dark:text-sky-300" :title="asset.model">
            {{ asset.model || asset.provider }}
          </div>
          <p class="line-clamp-2 text-slate-600 dark:text-slate-300" :title="asset.prompt">{{ asset.prompt }}</p>
          <div class="flex flex-wrap gap-1.5 pt-0.5">
            <Button variant="secondary" size="xs" @click="openDetails(asset)">Details</Button>
            <Button variant="ghost" size="xs" @click="keepOnly(asset)" title="Close and keep only this image selected">
              Keep selected
            </Button>
            <Button
              v-if="items.length > 2"
              variant="ghost"
              size="xs"
              class="text-rose-500"
              @click="removedIds = [...removedIds, asset.id]"
            >
              Remove
            </Button>
          </div>
        </div>
      </section>
    </div>
  </Modal>
</template>
