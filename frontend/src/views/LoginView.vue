<script setup>
import SocialLogin from '../components/SocialLogin.vue'
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

        <SocialLogin />

        <div class="auth-foot">
          Нет аккаунта? <router-link to="/register">Зарегистрироваться</router-link>
        </div>
      </div>
    </section>
  </main>
</template>
