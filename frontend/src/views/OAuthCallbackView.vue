<script setup>
import { onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { setToken } from '../api/inspectionApi'

const route = useRoute()
const router = useRouter()

onMounted(() => {
  const t = route.query.token
  if (t) {
    setToken(String(t))
    router.replace('/app')
  } else {
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
