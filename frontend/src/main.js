import { createApp } from 'vue'
import App from './App.vue'
import router from './router/index.js'
import './styles.css'
import * as Sentry from '@sentry/vue'

const app = createApp(App)

// Sentry на фронте — включается только при заданном VITE_SENTRY_DSN.
if (import.meta.env.VITE_SENTRY_DSN) {
  Sentry.init({
    app,
    dsn: import.meta.env.VITE_SENTRY_DSN,
    environment: import.meta.env.MODE,
    tracesSampleRate: 0.1,
  })
}

app.use(router).mount('#app')
