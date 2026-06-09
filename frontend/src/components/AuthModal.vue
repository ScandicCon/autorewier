<script setup>
import { ref } from 'vue'
import { loginUser, registerUser } from '../api/inspectionApi'

const emit = defineEmits(['auth-success', 'close'])
const tab = ref('login')  // 'login' | 'register'
const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  loading.value = true
  error.value = ''
  try {
    if (tab.value === 'login') {
      await loginUser(email.value, password.value)
    } else {
      await registerUser(email.value, password.value)
    }
    emit('auth-success')
  } catch (e) {
    error.value = e.message || 'Ошибка авторизации'
  } finally {
    loading.value = false
  }
}

function switchTab(newTab) {
  tab.value = newTab
  error.value = ''
}
</script>

<template>
  <Transition name="modal">
    <div class="auth-modal-overlay" @click.self="emit('close')">
      <div class="auth-modal glass-block" role="dialog" aria-modal="true" :aria-label="tab === 'login' ? 'Вход' : 'Регистрация'">

        <button class="auth-modal__close" type="button" aria-label="Закрыть" @click="emit('close')">
          <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
            <line x1="2" y1="2" x2="16" y2="16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
            <line x1="16" y1="2" x2="2" y2="16" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
          </svg>
        </button>

        <div class="auth-modal__header">
          <div class="auth-modal__icon">
            <svg width="28" height="28" viewBox="0 0 28 28" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="14" cy="10" r="5" stroke="var(--accent)" stroke-width="2"/>
              <path d="M4 24c0-5.523 4.477-10 10-10s10 4.477 10 10" stroke="var(--accent)" stroke-width="2" stroke-linecap="round"/>
            </svg>
          </div>
          <h2 class="auth-modal__title">{{ tab === 'login' ? 'Вход в аккаунт' : 'Регистрация' }}</h2>
        </div>

        <div class="auth-tabs" role="tablist">
          <button
            class="auth-tab"
            :class="{ 'auth-tab--active': tab === 'login' }"
            role="tab"
            :aria-selected="tab === 'login'"
            type="button"
            @click="switchTab('login')"
          >
            Войти
          </button>
          <button
            class="auth-tab"
            :class="{ 'auth-tab--active': tab === 'register' }"
            role="tab"
            :aria-selected="tab === 'register'"
            type="button"
            @click="switchTab('register')"
          >
            Регистрация
          </button>
        </div>

        <form class="auth-modal__form" @submit.prevent="submit" novalidate>
          <label class="auth-modal__label">
            <span class="auth-modal__label-text">Email</span>
            <input
              v-model="email"
              type="email"
              class="auth-modal__input"
              placeholder="your@email.com"
              autocomplete="email"
              required
              :disabled="loading"
            />
          </label>

          <label class="auth-modal__label">
            <span class="auth-modal__label-text">Пароль</span>
            <input
              v-model="password"
              type="password"
              class="auth-modal__input"
              placeholder="••••••••"
              :autocomplete="tab === 'login' ? 'current-password' : 'new-password'"
              required
              :disabled="loading"
            />
          </label>

          <Transition name="fade-error">
            <p v-if="error" class="auth-modal__error" role="alert">
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style="flex-shrink:0">
                <circle cx="8" cy="8" r="7" stroke="var(--accent-2)" stroke-width="1.5"/>
                <line x1="8" y1="4.5" x2="8" y2="8.5" stroke="var(--accent-2)" stroke-width="1.5" stroke-linecap="round"/>
                <circle cx="8" cy="11" r="0.75" fill="var(--accent-2)"/>
              </svg>
              {{ error }}
            </p>
          </Transition>

          <button
            class="cta cta--gradient auth-modal__submit"
            type="submit"
            :disabled="loading || !email || !password"
          >
            <span v-if="loading" class="auth-modal__spinner" aria-hidden="true"></span>
            <span>{{ loading ? 'Подождите...' : (tab === 'login' ? 'Войти' : 'Создать аккаунт') }}</span>
          </button>
        </form>

        <div class="auth-modal__footer">
          <a href="/cabinet/login" class="auth-modal__cabinet-link">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" style="flex-shrink:0">
              <path d="M5 2H2a1 1 0 0 0-1 1v8a1 1 0 0 0 1 1h3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
              <path d="M9 10l3-3-3-3" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" stroke-linejoin="round"/>
              <line x1="4" y1="7" x2="12" y2="7" stroke="currentColor" stroke-width="1.3" stroke-linecap="round"/>
            </svg>
            Войти через кабинет
          </a>
        </div>

      </div>
    </div>
  </Transition>
</template>
