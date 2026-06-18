<script setup>
import { onMounted, ref } from 'vue'
import { getOAuthProviders } from '../api/inspectionApi'

const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
const tgBot = import.meta.env.VITE_TELEGRAM_BOT || ''
const providers = ref([])
const tgEnabled = ref(false)
const tgBox = ref(null)

const labels = { yandex: 'Яндекс', vk: 'VK', google: 'Google' }
function oauth(p) { window.location.href = `${API_BASE}/api/v1/auth/oauth/${p}/start` }

onMounted(async () => {
  try {
    const info = await getOAuthProviders()
    providers.value = info.providers || []
    tgEnabled.value = !!info.telegram && !!tgBot
  } catch { /* провайдеры не настроены — просто не показываем */ }
  if (tgEnabled.value && tgBox.value) {
    const s = document.createElement('script')
    s.src = 'https://telegram.org/js/telegram-widget.js?22'
    s.async = true
    s.setAttribute('data-telegram-login', tgBot)
    s.setAttribute('data-size', 'large')
    s.setAttribute('data-auth-url', `${API_BASE}/api/v1/auth/telegram/callback`)
    s.setAttribute('data-request-access', 'write')
    tgBox.value.appendChild(s)
  }
})
</script>

<template>
  <div v-if="providers.length || tgEnabled" style="margin-top:8px">
    <div class="divider">или войдите через</div>
    <div style="display:flex;flex-direction:column;gap:10px">
      <button v-for="p in providers" :key="p" type="button" class="btn btn-ghost" @click="oauth(p)">
        Войти через {{ labels[p] || p }}
      </button>
      <div ref="tgBox" style="display:flex;justify-content:center"></div>
    </div>
  </div>
</template>
