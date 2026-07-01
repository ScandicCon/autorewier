import { createRouter, createWebHistory } from 'vue-router'
import { checkAuth, startGuestSession } from '../api/inspectionApi'

const routes = [
  { path: '/', component: () => import('../views/LandingView.vue'), meta: { public: true } },
  { path: '/login', component: () => import('../views/LoginView.vue'), meta: { public: true } },
  { path: '/register', component: () => import('../views/RegisterView.vue'), meta: { public: true } },
  { path: '/verify-email', component: () => import('../views/VerifyEmailView.vue'), meta: { public: true } },
  { path: '/forgot-password', component: () => import('../views/ForgotPasswordView.vue'), meta: { public: true } },
  { path: '/reset-password', component: () => import('../views/ResetPasswordView.vue'), meta: { public: true } },
  { path: '/oferta', component: () => import('../views/OfertaView.vue'), meta: { public: true } },
  { path: '/privacy', component: () => import('../views/PrivacyView.vue'), meta: { public: true } },
  { path: '/contacts', component: () => import('../views/ContactsView.vue'), meta: { public: true } },
  { path: '/oauth-callback', component: () => import('../views/OAuthCallbackView.vue'), meta: { public: true } },
  { path: '/app', component: () => import('../views/DashboardView.vue') },
  { path: '/app/new', component: () => import('../views/NewInspectionView.vue') },
  { path: '/app/parts', component: () => import('../views/PartFinderView.vue') },
  { path: '/app/inspection/:id', component: () => import('../views/InspectionDetailView.vue') },
]

const router = createRouter({
  history: createWebHistory('/'),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    if (to.hash) return { el: to.hash, behavior: 'smooth' }
    return { top: 0 }
  }
})

router.beforeEach(async (to) => {
  if (to.meta.public) return true
  try {
    await checkAuth()
    return true
  } catch {
    // Новая проверка доступна без регистрации: молча создаём гостевую сессию.
    if (to.path === '/app/new') {
      try {
        await startGuestSession()
        return true
      } catch { /* rate limit или бэкенд недоступен — уводим на логин */ }
    }
    return '/login'
  }
})

export default router
