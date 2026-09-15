import { createApp } from 'vue'
import { createPinia } from 'pinia'
import App from './App.vue'
import router from './router'
import './style.css'

const app = createApp(App)
const pinia = createPinia()

// Handle stale Vite chunk loads after new builds/deployments
window.addEventListener('vite:preloadError', () => {
  const reloadKey = 'lumigen_preload_reload'
  const lastReload = sessionStorage.getItem(reloadKey)
  const now = Date.now()
  if (!lastReload || now - Number(lastReload) > 10000) {
    sessionStorage.setItem(reloadKey, String(now))
    window.location.reload()
  }
})

app.use(pinia)
app.use(router)

app.mount('#app')
