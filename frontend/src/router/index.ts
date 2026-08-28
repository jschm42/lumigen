import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'generate',
    component: () => import('@/features/generate/GenerateView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/gallery',
    name: 'gallery',
    component: () => import('@/features/gallery/GalleryView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/profiles',
    name: 'profiles',
    component: () => import('@/features/profiles/ProfilesView.vue'),
    meta: { requiresAuth: true },
  },
  {
    path: '/admin',
    name: 'admin',
    component: () => import('@/features/admin/AdminView.vue'),
    meta: { requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/features/auth/LoginView.vue'),
    meta: { isGuestOnly: true },
  },
  {
    path: '/onboarding',
    name: 'onboarding',
    component: () => import('@/features/auth/OnboardingView.vue'),
    meta: { isGuestOnly: true },
  },
  {
    path: '/:pathMatch(.*)*',
    redirect: '/',
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach(async (to, _from, next) => {
  const authStore = useAuthStore()

  // Ensure auth status is checked on initial load
  if (authStore.isLoading) {
    await authStore.checkAuth()
  }

  // Redirect to onboarding if studio is not initialized yet
  if (authStore.needsOnboarding && to.path !== '/onboarding') {
    return next('/onboarding')
  }

  // Redirect away from onboarding if already configured
  if (!authStore.needsOnboarding && to.path === '/onboarding') {
    return next('/login')
  }

  // Guard protected routes
  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    return next('/login')
  }

  // Guard admin routes
  if (to.meta.requiresAdmin && !authStore.isAdmin) {
    return next('/')
  }

  // Redirect away from login if already authenticated
  if (to.meta.isGuestOnly && authStore.isAuthenticated) {
    return next('/')
  }

  next()
})

export default router
