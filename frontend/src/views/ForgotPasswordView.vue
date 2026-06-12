<script setup>
import { ref } from 'vue'
import { requestPasswordReset } from '../api/inspectionApi'

const email = ref('')
const loading = ref(false)
const sent = ref(false)
const error = ref('')

async function submit() {
  if (!email.value) { error.value = 'Введите email'; return }
  loading.value = true
  error.value = ''
  try {
    await requestPasswordReset(email.value)
    sent.value = true
  } catch (e) {
    error.value = e.message || 'Не удалось отправить письмо. Попробуйте позже.'
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
        Восстановим доступ за минуту
      </div>
    </div>

    <section class="auth-side">
      <div class="auth-card">
        <router-link to="/login" class="auth-back-inline">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>
          Ко входу
        </router-link>

        <div class="auth-badge" style="margin-top:14px"><span class="led"></span> ВОССТАНОВЛЕНИЕ</div>
        <h1>Забыли пароль?</h1>
        <p class="sub">Введите email — пришлём ссылку для сброса пароля.</p>

        <div v-if="sent" class="auth-success-msg">
          Если аккаунт с таким email существует, мы отправили на него ссылку для сброса пароля. Проверьте почту (и папку «Спам»).
        </div>
        <div v-else>
          <div v-if="error" class="auth-error-msg">{{ error }}</div>
          <form @submit.prevent="submit">
            <div class="form-field">
              <label>Email</label>
              <input v-model="email" type="email" placeholder="mail@example.com" :disabled="loading" required>
            </div>
            <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
              <span v-if="loading" class="btn-spinner"></span>
              {{ loading ? 'Отправляем...' : 'Отправить ссылку' }}
            </button>
          </form>
        </div>

        <div class="auth-foot">
          Вспомнили пароль? <router-link to="/login">Войти</router-link>
        </div>
      </div>
    </section>
  </main>
</template>
