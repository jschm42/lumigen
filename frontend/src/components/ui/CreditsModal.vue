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
    notes: 'Gemäß Lizenzbestimmungen von Black Forest Labs ist bei Veröffentlichung oder Weitergabe von mit FLUX.1 [dev] generierten Bildern ein Urhebernachweis anzubringen.',
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
    notes: 'Gemäß den OpenAI Terms of Service & Brand Guidelines wird bei Veröffentlichung von KI-generierten Bildern Transparenz über den Einsatz von OpenAI-Modellen empfohlen/gefordert.',
    website: 'https://openai.com',
    docsUrl: 'https://platform.openai.com/docs/guides/images',
  },
  {
    name: 'Google DeepMind / Google Cloud',
    badgeText: 'Imagen & Gemini',
    badgeVariant: 'blue',
    models: 'Imagen 3 (imagen-3.0-generate-002), Gemini 2.0 / 1.5 Flash',
    licenseType: 'Google Generative AI Terms of Service',
    attributionText: 'Generiert mit Google Imagen / Powered by Google Generative AI.',
    notes: 'Unterliegt den Google Terms of Service und der Generative AI Prohibited Use Policy (Kennzeichnungspflicht von synthetischen Inhalten bei Veröffentlichung).',
    website: 'https://ai.google.dev',
    docsUrl: 'https://ai.google.dev/gemini-api/docs/image-generation',
  },
  {
    name: 'fal.ai',
    badgeText: 'Cloud Inference',
    badgeVariant: 'amber',
    models: 'Serverless FLUX Inferenz, Nano Banana 2, Upscaling (AuraSR, CCSR)',
    licenseType: 'fal.ai Platform Terms of Service',
    attributionText: 'Inferenz & Upscaling powered by fal.ai.',
    notes: 'Schnelle Serverless-GPU-Infrastruktur für Bildgenerierung und hochauflösendes Upscaling.',
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
    notes: 'Fortschrittliches multimodales Bildgenerierungsmodell via MiniMax Open Platform.',
    website: 'https://www.minimaxi.com',
  },
  {
    name: 'OpenRouter',
    badgeText: 'API Gateway',
    badgeVariant: 'indigo',
    models: 'Multimodale Bild- und Vision-Modelle verschiedener Provider',
    licenseType: 'OpenRouter Terms of Service',
    attributionText: 'Unified model routing powered by OpenRouter.',
    notes: 'Zentrales Gateway für den Zugriff auf diverse Open-Source- und proprietäre Bildmodelle.',
    website: 'https://openrouter.ai',
    docsUrl: 'https://openrouter.ai/docs',
  },
  {
    name: 'Hugging Face',
    badgeText: 'Hub & Models',
    badgeVariant: 'slate',
    models: 'huggingface_hub Client & Model Repository',
    licenseType: 'Apache License 2.0',
    attributionText: 'Model discovery & assets powered by Hugging Face Hub.',
    notes: 'Open-Source-Ökosystem und Python-Client für vortrainierte Gewichte und Modell-Metadaten.',
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
    usage: 'Monospace-Schrift für Metadaten, Prompts, Seeds und Code-Ansichten.',
    url: 'https://github.com/JetBrains/JetBrainsMono',
  },
  {
    name: 'Space Grotesk',
    author: 'Florian Karsten',
    license: 'SIL Open Font License 1.1',
    licenseFile: 'licenses/OFL-1.1.txt',
    usage: 'Primäre Schriftart für Überschriften, Brand-Elemente und UI-Typografie.',
    url: 'https://github.com/floriankarsten/space-grotesk',
  },
  {
    name: 'Bootstrap Icons',
    author: 'The Bootstrap Authors (Mark Otto & Contributors)',
    license: 'MIT License',
    licenseFile: 'licenses/bootstrap-icons-MIT.txt',
    usage: 'Redistribuierte Web-Fonts (WOFF/WOFF2) für System- und Bedienelemente.',
    url: 'https://github.com/twbs/icons',
  },
  {
    name: 'Lucide Icons',
    author: 'Lucide Contributors & Cole Bemis',
    license: 'ISC License',
    licenseFile: 'https://lucide.dev/license',
    usage: 'Moderne SVG-Icons für die Vue-Benutzeroberfläche.',
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
    description: 'Hochmodernes, asynchrones Web-Framework für Python 3.12+.',
  },
  {
    name: 'Vue.js & Pinia',
    category: 'Frontend UI',
    license: 'MIT',
    author: 'Evan You & Vue Community',
    url: 'https://vuejs.org',
    description: 'Reaktives Frontend-Framework und modernes State Management.',
  },
  {
    name: 'Tailwind CSS',
    category: 'Styling',
    license: 'MIT',
    author: 'Tailwind Labs Inc.',
    url: 'https://tailwindcss.com',
    description: 'Utility-First CSS-Framework für das Lumigen Studio UI.',
  },
  {
    name: 'SQLAlchemy & Alembic',
    category: 'Datenbank',
    license: 'MIT',
    author: 'Mike Bayer & Contributors',
    url: 'https://www.sqlalchemy.org',
    description: 'Robuste Datenbank-Abstraktionsschicht und Schema-Migrationen.',
  },
  {
    name: 'Pillow (PIL)',
    category: 'Bildverarbeitung',
    license: 'HPND / Historical Permission',
    author: 'Alex Clark & Pillow Contributors',
    url: 'https://python-pillow.org',
    description: 'Bildmanipulation, Farbkorrekturen, Exif-Handling und Thumbnail-Generierung.',
  },
  {
    name: 'HTTPX',
    category: 'Netzwerk',
    license: 'BSD-3-Clause',
    author: 'Encode (Tom Christie & Contributors)',
    url: 'https://www.encode.io/httpx',
    description: 'Asynchroner HTTP-Client für schnelle Kommunikation mit allen Provider-APIs.',
  },
  {
    name: 'Cryptography',
    category: 'Sicherheit',
    license: 'Apache 2.0 / BSD',
    author: 'Python Cryptographic Authority (PyCA)',
    url: 'https://cryptography.io',
    description: 'Verschlüsselung sensibler Provider-API-Keys in der lokalen Datenbank.',
  },
]
</script>

<template>
  <Modal
    :open="creditsStore.isOpen"
    title="Credits, Danksagungen & Lizenzen"
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
              Verwendete APIs, Bibliotheken und Schriften
            </h4>
            <p class="text-slate-600 dark:text-slate-400 leading-relaxed">
              Lumigen ist ein lokales KI-Bildstudio, das auf fortschrittlichen Bildmodellen und Open-Source-Software aufbaut.
              Hier findest du die Übersicht aller angebundenen KI-APIs mit ihren jeweiligen Lizenz- und Attributionsbestimmungen
              sowie die Danksagungen an beteiligte Open-Source-Projekte.
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
          <span>KI-APIs & Provider ({{ providers.length }})</span>
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
          <span>Schriften & Icons ({{ fontsAndIcons.length }})</span>
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

      <!-- TAB 1: KI Provider & APIs -->
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
                  Dokumentation ↗
                </a>
              </div>
            </div>

            <div class="grid grid-cols-1 sm:grid-cols-2 gap-2 text-[11px]">
              <div>
                <span class="text-slate-500 block">Modelle / Einsatz:</span>
                <span class="font-medium text-slate-800 dark:text-slate-200">{{ provider.models }}</span>
              </div>
              <div>
                <span class="text-slate-500 block">Lizenzbasis:</span>
                <span class="font-medium text-slate-800 dark:text-slate-200">{{ provider.licenseType }}</span>
              </div>
            </div>

            <!-- Attribution Note -->
            <div class="rounded-lg bg-white/80 p-2.5 border border-slate-200/80 dark:bg-slate-950/60 dark:border-white/5 space-y-1">
              <span class="text-[10px] font-bold uppercase tracking-wider text-slate-400 dark:text-slate-500">
                Erforderlicher / Empfohlener Urhebernachweis (Attribution):
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
          <strong>Wichtiger Hinweis zur Veröffentlichung von KI-Inhalten:</strong>
          Modelle wie <em>FLUX.1 [dev]</em> von Black Forest Labs sind für nicht-kommerzielle Zwecke lizenziert und verlangen
          bei Veröffentlichung oder Weitergabe zwingend die Namensnennung. Überprüfe bei kommerzieller Nutzung die Nutzungsbedingungen
          des jeweiligen Anbieters und deiner individuellen API-Schlüssel.
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
                Urheber: <span class="font-medium text-slate-700 dark:text-slate-300">{{ font.author }}</span>
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
                Projektseite ↗
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
              Kategorie: {{ sw.category }} · {{ sw.author }}
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
          Schließen
        </Button>
      </div>
    </template>
  </Modal>
</template>
