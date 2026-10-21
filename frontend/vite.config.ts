import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'
import path from 'path'
import fs from 'fs'

const versionFilePath = path.resolve(__dirname, '../VERSION')
const appVersion = fs.existsSync(versionFilePath) ? fs.readFileSync(versionFilePath, 'utf-8').trim() : '0.4.0-beta'

export default defineConfig(({ mode }) => {
  const envDir = path.resolve(__dirname, '..')
  const env = loadEnv(mode, envDir, '')

  const frontendPort = parseInt(env.FRONTEND_PORT || env.VITE_PORT || '5173', 10)
  const backendPort = env.BACKEND_PORT || env.PORT || '8010'
  const backendHost = env.BACKEND_HOST || env.HOST || '127.0.0.1'
  const targetHost = backendHost === '0.0.0.0' ? '127.0.0.1' : backendHost
  const backendTarget = `http://${targetHost}:${backendPort}`

  return {
    envDir,
    define: {
      __APP_VERSION__: JSON.stringify(appVersion),
    },
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
      port: frontendPort,
      ...(env.FRONTEND_HOST ? { host: env.FRONTEND_HOST } : {}),
      proxy: {
        '/api': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/jobs': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/assets': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/static': {
          target: backendTarget,
          changeOrigin: true,
        },
        '/temp': {
          target: backendTarget,
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: path.resolve(__dirname, '../app/web/dist'),
      assetsDir: 'spa-assets',
      emptyOutDir: false,
    },
  }
})
