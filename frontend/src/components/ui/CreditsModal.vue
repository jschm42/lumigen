<script setup lang="ts">
import { ref } from 'vue'
import { useCreditsStore } from '@/stores/credits'
import Modal from '@/components/ui/Modal.vue'
import Button from '@/components/ui/Button.vue'
import Badge from '@/components/ui/Badge.vue'

const creditsStore = useCreditsStore()
const activeCategory = ref<'providers' | 'fonts' | 'software'>('providers')

interface ProviderCredit {
  name: string
  badgeText: string
  badgeVariant: 'sky' | 'blue' | 'indigo' | 'emerald' | 'rose' | 'amber' | 'slate' | 'violet'
  models: string
  licenseType: string
  attributionText: string
  notes?: string
  website: string
  docsUrl?: string
}

const providers: ProviderCredit[] = [
  {
    name: 'Black Forest Labs (BFL)',
    badgeText: 'FLUX.1',
    badgeVariant: 'emerald',
    models: 'FLUX.1 [dev], FLUX.1 [schnell], FLUX.1 [pro]',
    licenseType: 'BFL Non-Commercial (dev) / Apache 2.0 (schnell) / Commercial API (pro)',
    attributionText: 'FLUX.1 [dev] is licensed by Black Forest Labs under the Non-Commercial License.',
    notes: 'Per Black Forest Labs license terms (Section 2b), explicit attribution is required when distributing or publishing assets created with FLUX.1 [dev].',
    website: 'https://blackforestlabs.ai',
    docsUrl: 'https://docs.bfl.ai',
  },
  {
    name: 'OpenAI',
    badgeText: 'DALL·E',
    badgeVariant: 'sky',
    models: 'DALL·E 3, DALL·E 2, GPT Vision Models',
    licenseType: 'OpenAI Commercial API License',
    attributionText: 'Images generated with OpenAI API / Powered by OpenAI.',
    notes: 'Per OpenAI Terms of Service & Brand Guidelines, user transparency regarding the use of OpenAI models is required when publishing AI-generated images.',
    website: 'https://openai.com',
    docsUrl: 'https://platform.openai.com/docs/guides/images',
  },
  {
    name: 'Google DeepMind / Google Cloud',
    badgeText: 'Imagen & Gemini',
    badgeVariant: 'blue',
    models: 'Imagen 3 (imagen-3.0-generate-002), Gemini 2.0 / 1.5 Flash',
    licenseType: 'Google Generative AI Terms of Service',
    attributionText: 'Generated with Google Imagen / Powered by Google Generative AI.',
    notes: 'Subject to Google Terms of Service and Generative AI Prohibited Use Policy (transparency required when publishing synthetic media).',
    website: 'https://ai.google.dev',
    docsUrl: 'https://ai.google.dev/gemini-api/docs/image-generation',
  },
  {
    name: 'fal.ai',
    badgeText: 'Cloud Inference',
    badgeVariant: 'amber',
    models: 'Serverless FLUX Inference, Nano Banana 2, Upscaling (AuraSR, CCSR)',
    licenseType: 'fal.ai Platform Terms of Service',
    attributionText: 'Inference & upscaling powered by fal.ai.',
    notes: 'High-performance serverless GPU infrastructure for low-latency generation and super-resolution upscaling.',
    website: 'https://fal.ai',
    docsUrl: 'https://fal.ai/docs',
  },
  {
    name: 'MiniMax / Hailuo AI',
    badgeText: 'MiniMax API',
    badgeVariant: 'violet',
    models: 'MiniMax Image-01',
    licenseType: 'MiniMax Open Platform Terms',
    attributionText: 'Powered by MiniMax Image Generation API.',
    notes: 'Advanced multimodal image generation models accessible via the MiniMax Open Platform.',
    website: 'https://www.minimaxi.com',
  },
  {
    name: 'OpenRouter',
    badgeText: 'API Gateway',
    badgeVariant: 'indigo',
    models: 'Multimodal vision and diffusion models across multiple providers',
    licenseType: 'OpenRouter Terms of Service',
    attributionText: 'Unified model routing powered by OpenRouter.',
    notes: 'Central gateway for accessing diverse open-weight and proprietary image generation models.',
    website: 'https://openrouter.ai',
    docsUrl: 'https://openrouter.ai/docs',
  },
  {
    name: 'Hugging Face',
    badgeText: 'Hub & Models',
    badgeVariant: 'slate',
    models: 'huggingface_hub Client & Model Repository',
    licenseType: 'Apache License 2.0',
    attributionText: 'Model discovery and assets powered by Hugging Face Hub.',
    notes: 'Open-source ecosystem and Python client for pre-trained weights, architectures, and model metadata.',
    website: 'https://huggingface.co',
  },
]

interface FontCredit {
  name: string
  author: string
  license: string
  licenseFile: string
  usage: string
  url: string
}

const fontsAndIcons: FontCredit[] = [
  {
    name: 'JetBrains Mono',
    author: 'JetBrains s.r.o. (Philipp Nurullin, Konstantin Bulenkov)',
    license: 'SIL Open Font License 1.1',
    licenseFile: 'licenses/OFL-1.1.txt',
    usage: 'Monospace typeface for metadata, prompt inspection, seeds, and code display.',
    url: 'https://github.com/JetBrains/JetBrainsMono',
  },
  {
    name: 'Space Grotesk',
    author: 'Florian Karsten',
    license: 'SIL Open Font License 1.1',
    licenseFile: 'licenses/OFL-1.1.txt',
    usage: 'Primary display font for headings, brand identity, and UI typography.',
    url: 'https://github.com/floriankarsten/space-grotesk',
  },
  {
    name: 'Bootstrap Icons',
    author: 'The Bootstrap Authors (Mark Otto & Contributors)',
    license: 'MIT License',
    licenseFile: 'licenses/bootstrap-icons-MIT.txt',
    usage: 'Redistributed web fonts (WOFF/WOFF2) for system and control elements.',
    url: 'https://github.com/twbs/icons',
  },
  {
    name: 'Lucide Icons',
    author: 'Lucide Contributors & Cole Bemis',
    license: 'ISC License',
    licenseFile: 'https://lucide.dev/license',
    usage: 'Modern, consistent vector SVG icons for the Vue user interface.',
    url: 'https://lucide.dev',
  },
]

interface SoftwareCredit {
  name: string
  category: string
  license: string
  author: string
  url: string
  description: string
}

const openSourceSoftware: SoftwareCredit[] = [
  {
    name: 'FastAPI & Uvicorn',
    category: 'Backend Core',
    license: 'MIT',
    author: 'Sebastián Ramírez & Encode',
    url: 'https://fastapi.tiangolo.com',
    description: 'High-performance, async Python web framework and ASGI server for Python 3.12+.',
  },
  {
    name: 'Vue.js & Pinia',
    category: 'Frontend UI',
    license: 'MIT',
    author: 'Evan You & Vue Community',
    url: 'https://vuejs.org',
    description: 'Progressive reactive UI framework and intuitive centralized state management.',
  },
  {
    name: 'Tailwind CSS',
    category: 'Styling',
    license: 'MIT',
    author: 'Tailwind Labs Inc.',
    url: 'https://tailwindcss.com',
    description: 'Utility-first styling system powering Lumigen Studio dark & light interfaces.',
  },
  {
    name: 'SQLAlchemy & Alembic',
    category: 'Database',
    license: 'MIT',
    author: 'Mike Bayer & Contributors',
    url: 'https://www.sqlalchemy.org',
    description: 'Database ORM, atomic transactions, and automated schema migration management.',
  },
  {
    name: 'Pillow (PIL)',
    category: 'Image Processing',
    license: 'HPND / Historical Permission',
    author: 'Alex Clark & Pillow Contributors',
    url: 'https://python-pillow.org',
    description: 'Image operations, format conversion, thumbnail rendering, and metadata extraction.',
  },
  {
    name: 'HTTPX',
    category: 'Networking',
    license: 'BSD-3-Clause',
    author: 'Encode (Tom Christie & Contributors)',
    url: 'https://www.encode.io/httpx',
    description: 'Async HTTP client for secure, low-latency communication with external provider APIs.',
  },
  {
    name: 'Cryptography',
    category: 'Security',
    license: 'Apache 2.0 / BSD',
    author: 'Python Cryptographic Authority (PyCA)',
    url: 'https://cryptography.io',
    description: 'Cryptographic primitives for securing sensitive API keys in the local database.',
  },
]
</script>

<template>
  <Modal
    :open="creditsStore.isOpen"
    title="Credits, Attributions & Licenses"
    size="xl"
    @close="creditsStore.close"
  >
    <div class="p-4 sm:p-6 space-y-6 text-xs text-slate-700 dark:text-slate-300">
      <!-- Intro description -->
      <div class="rounded-xl border border-sky-200/80 bg-sky-50/60 p-4 dark:border-sky-900/60 dark:bg-sky-950/30">
        <div class="flex items-start gap-3">
          <span class="text-xl leading-none">✨</span>
          <div class="space-y-1">
            <h4 class="text-sm font-semibold text-sky-950 dark:text-sky-200">
              Integrated APIs, Open-Source Libraries & Typography
            </h4>
            <p class="text-slate-600 dark:text-slate-400 leading-relaxed">
              Lumigen is a local-first AI image studio built upon state-of-the-art generative models and foundational
              open-source software. Below is a comprehensive overview of integrated AI providers, their required attribution
              notices, and credits to the open-source projects and fonts that make this studio possible.
            </p>
          </div>
        </div>
      </div>

      <!-- Navigation Tabs -->
      <div class="flex items-center gap-2 border-b border-slate-200 dark:border-white/10 pb-2">
        <button
          type="button"
          @click="activeCategory = 'providers'"
          :class="[
            'px-3.5 py-1.5 rounded-xl font-semibold transition-colors cursor-pointer text-xs flex items-center gap-1.5',
            activeCategory === 'providers'
              ? 'bg-sky-500 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-200/60 dark:text-slate-300 dark:hover:bg-white/10',
          ]"
        >
          <span>🤖</span>
          <span>AI APIs & Providers ({{ providers.length }})</span>
        </button>
        <button
          type="button"
          @click="activeCategory = 'fonts'"
          :class="[
            'px-3.5 py-1.5 rounded-xl font-semibold transition-colors cursor-pointer text-xs flex items-center gap-1.5',
            activeCategory === 'fonts'
              ? 'bg-sky-500 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-200/60 dark:text-slate-300 dark:hover:bg-white/10',
          ]"
        >
          <span>🖋️</span>
          <span>Fonts & Icons ({{ fontsAndIcons.length }})</span>
        </button>
        <button
          type="button"
          @click="activeCategory = 'software'"
          :class="[
            'px-3.5 py-1.5 rounded-xl font-semibold transition-colors cursor-pointer text-xs flex items-center gap-1.5',
            activeCategory === 'software'
              ? 'bg-sky-500 text-white shadow-sm'
              : 'text-slate-600 hover:bg-slate-200/60 dark:text-slate-300 dark:hover:bg-white/10',
          ]"
        >
          <span>⚡</span>
          <span>Open-Source Software ({{ openSourceSoftware.length }})</span>
        </button>
      </div>

      <!-- TAB 1: AI Provider & APIs -->
      <div v-if="activeCategory === 'providers'" class="space-y-4">
        <div class="grid grid-cols-1 gap-4">
          <div
            v-for="provider in providers"
            :key="provider.name"
            class="rounded-xl border border-slate-200/90 bg-slate-50/60 p-4 dark:border-white/10 dark:bg-slate-900/50 space-y-2.5 transition-all hover:border-slate-300 dark:hover:border-white/20"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="flex items-center gap-2">
                <span class="text-sm font-bold text-slate-900 dark:text-white">{{ provider.name }}</span>
                <Badge :variant="provider.badgeVariant" size="xs">{{ provider.badgeText }}</Badge>
              </div>
              <div class="flex items-center gap-2">
                <a
                  :href="provider.website"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-[11px] font-medium text-sky-600 hover:underline dark:text-sky-400"
                >
                  Website ↗
                </a>
                <span v-if="provider.docsUrl" class="text-slate-300 dark:text-slate-600">·</span>
                <a
                  v-if="provider.docsUrl"
                  :href="provider.docsUrl"
                  target="_blank"
                  rel="noopener noreferrer"
                  class="text-[11px] font-medium text-sky-600 hover:underline dark:text-sky-400"
                >
                  Documentation ↗
                </a>
              </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
              <div>
                <span class="text-slate-500 block">Models / Usage:</span>
                <span class="font-medium text-slate-800 dark:text-slate-200">{{ provider.models }}</span>
              </div>
              <div>
                <span class="text-slate-500 block">License Basis:</span>
                <span class="font-medium text-slate-800 dark:text-slate-200">{{ provider.licenseType }}</span>
              </div>
            </div>

            <!-- Attribution Note -->
            <div class="rounded-lg bg-white/80 p-2.5 border border-slate-200/80 dark:bg-slate-950/60 dark:border-white/5 space-y-1">
              <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Required / Recommended Attribution:
              </span>
              <p class="font-mono text-[11px] font-semibold text-slate-800 dark:text-slate-200 select-all">
                "{{ provider.attributionText }}"
              </p>
              <p v-if="provider.notes" class="text-[10px] text-slate-500 dark:text-slate-400 leading-snug">
                {{ provider.notes }}
              </p>
            </div>
          </div>
        </div>

        <!-- General Disclaimer -->
        <div class="rounded-xl border border-amber-200/80 bg-amber-50/60 p-3.5 dark:border-amber-900/60 dark:bg-amber-950/30 text-[11px] text-amber-900 dark:text-amber-200 leading-relaxed">
          <strong>Important Notice on Distributing AI-Generated Content:</strong>
          Models such as <em>FLUX.1 [dev]</em> by Black Forest Labs are licensed for non-commercial use and strictly require
          attribution upon public distribution. When utilizing models for commercial purposes, please check the respective provider
          terms and conditions as well as your individual API tier agreements.
        </div>
      </div>

      <!-- TAB 2: Fonts & Icons -->
      <div v-if="activeCategory === 'fonts'" class="space-y-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          <div
            v-for="font in fontsAndIcons"
            :key="font.name"
            class="rounded-xl border border-slate-200/90 bg-slate-50/60 p-4 dark:border-white/10 dark:bg-slate-900/50 space-y-2 flex flex-col justify-between"
          >
            <div class="space-y-1">
              <div class="flex items-center justify-between">
                <h5 class="text-sm font-bold text-slate-900 dark:text-white">{{ font.name }}</h5>
                <Badge variant="indigo" size="xs">{{ font.license }}</Badge>
              </div>
              <p class="text-[11px] text-slate-500 dark:text-slate-400">
                Author: <span class="font-medium text-slate-700 dark:text-slate-300">{{ font.author }}</span>
              </p>
              <p class="text-[11px] text-slate-600 dark:text-slate-300 pt-1">
                {{ font.usage }}
              </p>
            </div>

            <div class="pt-2 border-t border-slate-200 dark:border-white/5 flex items-center justify-between text-[10px]">
              <span class="font-mono text-slate-400">{{ font.licenseFile }}</span>
              <a
                :href="font.url"
                target="_blank"
                rel="noopener noreferrer"
                class="text-sky-600 hover:underline dark:text-sky-400 font-medium"
              >
                Project Website ↗
              </a>
            </div>
          </div>
        </div>
      </div>

      <!-- TAB 3: Open Source Software -->
      <div v-if="activeCategory === 'software'" class="space-y-4">
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
          <div
            v-for="sw in openSourceSoftware"
            :key="sw.name"
            class="rounded-xl border border-slate-200/90 bg-slate-50/60 p-3.5 dark:border-white/10 dark:bg-slate-900/50 space-y-1.5"
          >
            <div class="flex items-center justify-between">
              <div class="flex items-center gap-2">
                <strong class="text-xs text-slate-900 dark:text-white">{{ sw.name }}</strong>
                <Badge variant="slate" size="xs">{{ sw.license }}</Badge>
              </div>
              <a
                :href="sw.url"
                target="_blank"
                rel="noopener noreferrer"
                class="text-[10px] text-sky-600 hover:underline dark:text-sky-400"
              >
                Website ↗
              </a>
            </div>
            <p class="text-[10px] text-slate-500 dark:text-slate-400">
              Category: {{ sw.category }} · {{ sw.author }}
            </p>
            <p class="text-[11px] text-slate-600 dark:text-slate-300">
              {{ sw.description }}
            </p>
          </div>
        </div>
      </div>
    </div>

    <!-- Footer -->
    <template #footer>
      <div class="flex items-center justify-between w-full">
        <div class="text-[11px] text-slate-500">
          Lumigen AI Image Studio · Open-Source & Multi-Provider Architecture
        </div>
        <Button variant="secondary" size="sm" @click="creditsStore.close">
          Close
        </Button>
      </div>
    </template>
  </Modal>
</template>
