<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { exchangeOAuthCode } from '../api/inspectionApi'

const route = useRoute()
const router = useRouter()

onMounted(async () => {
  // Бэкенд отдаёт одноразовый код (не JWT в URL) — меняем его на токен POST-ом.
  const code = route.query.code
  if (!code) {
    router.replace('/login?error=oauth')
    return
  }
  try {
    await exchangeOAuthCode(String(code))
    router.replace('/app')
  } catch {
    router.replace('/login?error=oauth')
  }
})
</script>

<template>
  <main class="auth">
    <section class="auth-side">
      <div class="auth-card" style="margin:auto;text-align:center">
        <p>Входим…</p>
      </div>
    </section>
  </main>
</template>
