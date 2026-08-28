import axios, { type AxiosInstance, type AxiosError } from 'axios'

function getCookie(name: string): string | null {
  const match = document.cookie.match(new RegExp('(^| )' + name + '=([^;]+)'))
  return match ? decodeURIComponent(match[2]) : null
}

export const apiClient: AxiosInstance = axios.create({
  baseURL: '',
  headers: {
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  },
  withCredentials: true,
})

apiClient.interceptors.request.use((config) => {
  const csrfToken = getCookie('csrf_token') || document.querySelector('meta[name="csrf-token"]')?.getAttribute('content')
  if (csrfToken && config.headers) {
    config.headers['X-CSRF-Token'] = csrfToken
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<{ detail?: string; error?: string; message?: string }>) => {
    if (error.response?.status === 401) {
      // Unauthorized: Let caller or router guard handle redirect if not on login page
      const currentPath = window.location.pathname
      if (currentPath !== '/login' && currentPath !== '/onboarding') {
        // Optional dispatch or redirect
      }
    }
    return Promise.reject(error)
  }
)

export default apiClient
