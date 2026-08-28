import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'

export default defineConfig({
  plugins: [
    vue(),
    tailwindcss(),
  ],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
      },
      '/jobs': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
      },
      '/assets': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
      },
      '/static': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
      },
      '/temp': {
        target: 'http://127.0.0.1:8010',
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: path.resolve(__dirname, '../app/web/dist'),
    assetsDir: 'spa-assets',
    emptyOutDir: true,
  },
})
