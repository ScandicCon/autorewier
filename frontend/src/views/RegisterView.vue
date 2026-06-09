<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { registerWithConfirm, requestVerificationCode } from '../api/inspectionApi'

const router = useRouter()
const role = ref('buyer')
const name = ref('')
const email = ref('')
const password = ref('')
const passwordConfirm = ref('')
const consent = ref(false)
const loading = ref(false)
const error = ref('')

async function submit() {
  error.value = ''
  if (!email.value || !password.value || !passwordConfirm.value) { error.value = 'Заполните все поля'; return }
  if (password.value !== passwordConfirm.value) { error.value = 'Пароли не совпадают'; return }
  if (password.value.length < 8) { error.value = 'Пароль минимум 8 символов'; return }
  if (!consent.value) { error.value = 'Необходимо согласие с условиями'; return }
  loading.value = true
  try {
    await registerWithConfirm(email.value, password.value, passwordConfirm.value)
    // Then login is needed before sending verify code — redirect to login with hint
    router.push('/login?registered=1')
  } catch (e) {
    error.value = e.message || 'Ошибка регистрации. Попробуйте ещё раз.'
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <main class="auth">
    <div class="auth-art">
      <img src="/img/register.png" alt="" onerror="this.style.display='none'">
      <div class="art-cap">
        <b>ПОДКАПОТ</b>
        Собери свой гараж
      </div>
    </div>

    <section class="auth-side">
      <div class="auth-card">
        <router-link to="/" class="auth-back-inline">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>
          На главную
        </router-link>

        <div class="auth-badge" style="margin-top:14px"><span class="led"></span> РЕГИСТРАЦИЯ</div>
        <h1>Создать аккаунт</h1>
        <p class="sub">Пара полей — и можно проверять первое авто.</p>

        <div v-if="error" class="auth-error-msg">{{ error }}</div>

        <form @submit.prevent="submit">
          <div class="role-pick">
            <label class="role-opt" :class="{ sel: role === 'buyer' }" @click="role = 'buyer'">
              <input type="radio" name="role" :checked="role === 'buyer'">
              <b>Покупатель</b>
              <span>Беру авто для себя</span>
            </label>
            <label class="role-opt" :class="{ sel: role === 'dealer' }" @click="role = 'dealer'">
              <input type="radio" name="role" :checked="role === 'dealer'">
              <b>Перекуп</b>
              <span>Оцениваю сделки</span>
            </label>
          </div>

          <div class="form-field">
            <label>Имя</label>
            <input v-model="name" type="text" placeholder="Как тебя зовут" :disabled="loading">
          </div>
          <div class="form-field">
            <label>Email</label>
            <input v-model="email" type="email" placeholder="mail@example.com" :disabled="loading" required>
          </div>
          <div class="form-field">
            <label>Пароль</label>
            <input v-model="password" type="password" placeholder="Минимум 8 символов" :disabled="loading" required>
          </div>
          <div class="form-field">
            <label>Повторите пароль</label>
            <input v-model="passwordConfirm" type="password" placeholder="Ещё раз" :disabled="loading" required>
          </div>

          <label class="consent-styled">
            <input v-model="consent" type="checkbox" :disabled="loading">
            <span class="consent-check"></span>
            <span class="consent-text">Соглашаюсь с <a href="#">условиями</a> и <a href="#">политикой</a></span>
          </label>

          <button type="submit" class="btn btn-primary btn-block" :disabled="loading">
            <span v-if="loading" class="btn-spinner"></span>
            {{ loading ? 'Создаём аккаунт...' : 'Создать аккаунт' }}
          </button>
        </form>

        <div class="divider">или зарегистрируйтесь через</div>

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
          Уже есть аккаунт? <router-link to="/login">Войти</router-link>
        </div>
      </div>
    </section>
  </main>
</template>
