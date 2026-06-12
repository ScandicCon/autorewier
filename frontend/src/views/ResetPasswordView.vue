<script setup>
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { resetPassword } from '../api/inspectionApi'

const route = useRoute()
const router = useRouter()
const token = ref('')
const password = ref('')
const passwordConfirm = ref('')
const loading = ref(false)
const error = ref('')
const done = ref(false)

onMounted(() => {
  token.value = (route.query.token || '').toString()
  if (!token.value) {
    error.value = 'Ссылка недействительна: отсутствует токен. Запросите восстановление заново.'
  }
})

async function submit() {
  if (!token.value) { error.value = 'Ссылка недействительна. Запросите восстановление заново.'; return }
  if (password.value.length < 6) { error.value = 'Пароль должен быть не короче 6 символов'; return }
  if (password.value !== passwordConfirm.value) { error.value = 'Пароли не совпадают'; return }
  loading.value = true
  error.value = ''
  try {
    await resetPassword(token.value, password.value)
    done.value = true
    setTimeout(() => router.push('/login'), 1800)
  } catch (e) {
    error.value = e.message || 'Не удалось сбросить пароль. Возможно, ссылка устарела.'
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
        Новый пароль — и снова в дело
      </div>
    </div>

    <section class="auth-side">
      <div class="auth-card">
        <router-link to="/login" class="auth-back-inline">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>
          Ко входу
        </router-link>

        <div class="auth-badge" style="margin-top:14px"><span class="led"></span> НОВЫЙ ПАРОЛЬ</div>
        <h1>Сброс пароля</h1>
        <p class="sub">Придумайте новый пароль для входа.</p>

        <div v-if="done" class="auth-success-msg">
          Пароль изменён! Перенаправляем на страницу входа...
        </div>
        <div v-else>
          <div v-if="error" class="auth-error-msg">{{ error }}</div>
          <form @submit.prevent="submit">
            <div class="form-field">
              <label>Новый пароль</label>
              <input v-model="password" type="password" placeholder="Минимум 6 символов" :disabled="loading" required>
            </div>
            <div class="form-field">
              <label>Повторите пароль</label>
              <input v-model="passwordConfirm" type="password" placeholder="Ещё раз" :disabled="loading" required>
            </div>
            <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
              <span v-if="loading" class="btn-spinner"></span>
              {{ loading ? 'Сохраняем...' : 'Сменить пароль' }}
            </button>
          </form>
        </div>

        <div class="auth-foot">
          <router-link to="/forgot-password">Запросить ссылку заново</router-link>
        </div>
      </div>
    </section>
  </main>
</template>
