<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { loginUser, requestVerificationCode } from '../api/inspectionApi'

const router = useRouter()
const route = useRoute()
const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const justRegistered = ref(false)

onMounted(() => {
  justRegistered.value = route.query.registered === '1'
})

async function submit() {
  if (!email.value || !password.value) { error.value = 'Введите email и пароль'; return }
  loading.value = true
  error.value = ''
  try {
    const user = await loginUser(email.value, password.value)
    // if email not verified, send code and redirect to verify
    if (!user.email_verified) {
      try { await requestVerificationCode({ channel: 'email' }) } catch {}
      router.push('/verify-email')
    } else {
      router.push('/app')
    }
  } catch (e) {
    error.value = e.message || 'Неверный email или пароль'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth">
    <div class="auth-art">
      <img src="/img/login.png" alt="" onerror="this.style.display='none'">
      <div class="art-cap">
        <b>ПОДКАПОТ</b>
        Твой диагност уже завёл мотор
      </div>
    </div>

    <section class="auth-side">
      <div class="auth-card">
        <router-link to="/" class="auth-back-inline">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>
          На главную
        </router-link>

        <div class="auth-badge" style="margin-top:14px"><span class="led"></span> ВХОД</div>
        <h1>С возвращением</h1>
        <p class="sub">Войди, чтобы открыть свои проверки, отчёты и сравнения авто.</p>

        <div v-if="justRegistered" class="auth-success-msg">
          Аккаунт создан! Войдите, чтобы подтвердить email.
        </div>
        <div v-if="error" class="auth-error-msg">{{ error }}</div>

        <form @submit.prevent="submit">
          <div class="form-field">
            <label>Email</label>
            <input v-model="email" type="email" placeholder="mail@example.com" :disabled="loading" required>
          </div>
          <div class="form-field">
            <label>Пароль</label>
            <input v-model="password" type="password" placeholder="Введите пароль" :disabled="loading" required>
          </div>
          <div class="field-row">
            <span></span>
            <router-link to="/forgot-password">Забыли пароль?</router-link>
          </div>
          <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
            <span v-if="loading" class="btn-spinner"></span>
            {{ loading ? 'Входим...' : 'Войти' }}
          </button>
        </form>

        <div class="divider">или войдите через</div>

        <div class="social-row social-row--2col">
          <a class="social-btn social-btn--tg" href="#">
            <svg viewBox="0 0 48 48" width="22" height="22" aria-hidden="true">
              <circle cx="24" cy="24" r="24" fill="#29B6F6"/>
              <path fill="#fff" d="M34.1 14.2l-4.3 20.2c-.3 1.4-1.1 1.8-2.3 1.1l-6.4-4.7-3.1 3c-.3.3-.6.6-1.3.6l.5-6.5 11.8-10.7c.5-.5-.1-.7-.8-.3L11.4 26.9l-6.3-2c-1.4-.4-1.4-1.4.3-2l24.6-9.5c1.1-.4 2.1.3 1.8 1.9z"/>
            </svg>
            Telegram
          </a>
          <a class="social-btn social-btn--ya" href="#">
            <svg viewBox="0 0 48 48" width="22" height="22" aria-hidden="true">
              <circle cx="24" cy="24" r="24" fill="#FC3F1D"/>
              <path fill="#fff" d="M27.8 34h-4V20.1h-2.1c-2.4 0-3.7 1.2-3.7 3.1 0 2.1 1 3.1 2.8 4.3l1.6 1-4.6 7.4h-4.2l4.2-6.6c-2.4-1.7-3.7-3.4-3.7-6.3 0-3.8 2.7-6.3 7.5-6.3h6.2V34z"/>
            </svg>
            Яндекс
          </a>
        </div>

        <div class="auth-foot">
          Нет аккаунта? <router-link to="/register">Зарегистрироваться</router-link>
        </div>
      </div>
    </section>
  </main>
</template>
