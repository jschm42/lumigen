/**
 * Lumigen Tailwind Configuration
 * 
 * Custom Tailwind config for Lumigen app.
 * This file is loaded before Tailwind via CDN.
 */

var lumigenTailwindConfig = {
  darkMode: 'class',
  safelist: [
    // Gallery preview image classes
    'group',
    'relative',
    'h-20',
    'w-20',
    'overflow-hidden',
    'rounded-xl',
    'border',
    'border-white/15',
    'bg-slate-950/80',
    'shadow-md',
    'shadow-slate-950/60',
    'ring-1',
    'ring-sky-300/25',
    'h-full',
    'w-full',
    'object-cover',
    'absolute',
    'right-1',
    'top-1',
    'inline-flex',
    'h-5',
    'w-5',
    'items-center',
    'justify-center',
    'rounded-full',
    'border-white/35',
    'bg-slate-900/90',
    'text-[11px]',
    'font-bold',
    'text-white',
    'transition',
    'hover:border-rose-200',
    'hover:bg-rose-500/80',
    'ring-2',
    'ring-sky-300',
    'border-sky-300/70',
    // Preview image classes built dynamically in app.js
    'border-slate-300/55',
    'bg-white/95',
    'text-slate-900',
    'shadow-slate-200/60',
    'dark:border-white/15',
    'dark:bg-slate-900/80',
    'dark:text-white',
    'dark:shadow-slate-950/60',
    'dark:border-white/35',
    'dark:bg-slate-900/90',
    'border-slate-300/85',
    'bg-rose-500/90',
    'dark:border-rose-200',
    'dark:bg-rose-500/80'
  ],
  theme: {
    extend: {
      colors: {
        lumigen: {
          50: '#f0f9ff',
          100: '#e0f2fe',
          200: '#bae6fd',
          300: '#7dd3fc',
          400: '#38bdf8',
          500: '#0ea5e9'
        }
      },
      fontFamily: {
        sans: ['Space Grotesk', 'ui-sans-serif', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace']
      },
      boxShadow: {
        panel: '0 28px 90px -45px rgba(56, 189, 248, 0.42)'
      }
    }
  }
};

window.__lumigenTailwindConfig = lumigenTailwindConfig;

if (window.tailwind && typeof window.tailwind === 'object') {
  window.tailwind.config = lumigenTailwindConfig;
} else {
  window.tailwind = { config: lumigenTailwindConfig };
}
