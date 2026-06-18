<script setup>
import SocialLogin from '../components/SocialLogin.vue'
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
          <p style="margin-top:12px;font-size:12px;color:var(--muted,#94a3b8);text-align:center">
            Регистрируясь, вы принимаете
            <router-link to="/oferta">оферту</router-link> и
            <router-link to="/privacy">политику конфиденциальности</router-link>.
          </p>
        </form>

        <SocialLogin />

        <div class="auth-foot">
          Уже есть аккаунт? <router-link to="/login">Войти</router-link>
        </div>
      </div>
    </section>
  </main>
</template>
