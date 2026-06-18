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
// чтобы не утяжелять основной бандл, когда аналитика не настроена.
if (import.meta.env.VITE_POSTHOG_KEY) {
  import('posthog-js').then(({ default: posthog }) => {
    posthog.init(import.meta.env.VITE_POSTHOG_KEY, {
      api_host: import.meta.env.VITE_POSTHOG_HOST || 'https://eu.i.posthog.com',
      capture_pageview: true,
    })
  }).catch(() => {})
}

app.use(router).mount('#app')
