import { createApp } from 'vue'
import App from './App.vue'
import router from './router/index.js'
import './styles.css'
import * as Sentry from '@sentry/vue'

const app = createApp(App)

// Sentry — мониторинг ошибок (включается при VITE_SENTRY_DSN).
if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    app,
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,
  })
}

// PostHog — продуктовая аналитика. Грузим лениво и только при VITE_POSTHOG_KEY,
// и ТОЛЬКО после согласия пользователя на аналитические cookie (152-ФЗ).
// initAnalytics() вызывается из баннера CookieConsent при согласии, либо сразу
// при загрузке, если согласие было дано ранее.
let _analyticsInited = false
function initAnalytics() {
  if (_analyticsInited) return
  if (!import.meta.env.VITE_POSTHOG_KEY) return
  _analyticsInited = true
  import('posthog-js').then(({ default: posthog }) => {
    posthog.init(import.meta.env.VITE_POSTHOG_KEY, {
      api_host: import.meta.env.VITE_POSTHOG_HOST || 'https://eu.i.posthog.com',
      capture_pageview: true,
    })
  }).catch(() => { _analyticsInited = false })
}
// Доступно глобально, чтобы баннер согласия мог запустить аналитику.
window.__initAnalytics = initAnalytics
// Если пользователь уже согласился ранее — стартуем без баннера.
try {
  if (localStorage.getItem('analytics_consent') === 'granted') initAnalytics()
} catch (e) { /* localStorage недоступен (приватный режим) */ }

app.use(router).mount('#app')
