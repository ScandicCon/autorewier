<script setup>
import { ref, onMounted } from 'vue'

// Баннер согласия на аналитические cookie (152-ФЗ / GDPR-стиль).
// PostHog инициализируется ТОЛЬКО после явного согласия пользователя.
// Выбор сохраняется в localStorage, чтобы не показывать баннер повторно.

const CONSENT_KEY = 'analytics_consent' // 'granted' | 'denied'
const visible = ref(false)

function readConsent() {
  try { return localStorage.getItem(CONSENT_KEY) } catch { return null }
}

function saveConsent(value) {
  try { localStorage.setItem(CONSENT_KEY, value) } catch { /* приватный режим */ }
}

function accept() {
  saveConsent('granted')
  visible.value = false
  // Инициализируем аналитику сразу после согласия (функция определена в main.js).
  if (typeof window.__initAnalytics === 'function') window.__initAnalytics()
}

function decline() {
  saveConsent('denied')
  visible.value = false
}

onMounted(() => {
  // Показываем баннер только если выбор ещё не сделан.
  if (!readConsent()) visible.value = true
})
</script>

<template>
  <transition name="cc-fade">
    <div v-if="visible" class="cookie-consent" role="dialog" aria-live="polite" aria-label="Согласие на cookie">
      <div class="cc-text">
        Мы используем аналитические cookie, чтобы понимать, как улучшить сервис.
        Подробнее — в <RouterLink to="/privacy" class="cc-link">политике конфиденциальности</RouterLink>.
      </div>
      <div class="cc-actions">
        <button class="cc-btn cc-decline" type="button" @click="decline">Только необходимые</button>
        <button class="cc-btn cc-accept" type="button" @click="accept">Принять</button>
      </div>
    </div>
  </transition>
</template>

<style scoped>
.cookie-consent {
  position: fixed;
  left: 50%;
  bottom: 20px;
  transform: translateX(-50%);
  z-index: 9999;
  width: min(680px, calc(100vw - 32px));
  display: flex;
  align-items: center;
  gap: 16px;
  flex-wrap: wrap;
  justify-content: space-between;
  padding: 16px 20px;
  background: rgba(10, 18, 30, 0.96);
  border: 1px solid var(--line2, #243044);
  border-radius: 14px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.45);
  backdrop-filter: blur(8px);
  color: var(--muted, #c4d0e0);
  font-size: 13.5px;
  line-height: 1.5;
}
.cc-text { flex: 1 1 320px; }
.cc-link { color: var(--cyan, #3fd0ff); }
.cc-actions { display: flex; gap: 10px; flex: 0 0 auto; }
.cc-btn {
  padding: 9px 18px;
  border-radius: 9px;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  border: 1px solid transparent;
  transition: all .15s;
}
.cc-decline {
  background: transparent;
  border-color: var(--line2, #243044);
  color: var(--muted, #c4d0e0);
}
.cc-decline:hover { border-color: var(--muted, #c4d0e0); }
.cc-accept {
  background: linear-gradient(135deg, var(--cyan, #3fd0ff), var(--cyan2, #2aa8e0));
  color: #04101f;
}
.cc-accept:hover { filter: brightness(1.08); }
.cc-fade-enter-active, .cc-fade-leave-active { transition: opacity .25s, transform .25s; }
.cc-fade-enter-from, .cc-fade-leave-to { opacity: 0; transform: translateX(-50%) translateY(12px); }

/* Мобильная раскладка: компактнее, кнопки на всю ширину, ближе к краю экрана */
@media (max-width: 560px) {
  .cookie-consent {
    width: calc(100vw - 16px);
    bottom: 8px;
    padding: 14px 16px;
    gap: 12px;
    font-size: 13px;
  }
  .cc-actions { width: 100%; }
  .cc-btn { flex: 1 1 0; text-align: center; padding: 11px 12px; }
}
</style>
