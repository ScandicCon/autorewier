<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { confirmVerificationCode, requestVerificationCode } from '../api/inspectionApi'

const router = useRouter()
const digits = ref(['', '', '', '', '', ''])
const loading = ref(false)
const error = ref('')
const success = ref('')
const resendTimer = ref(0)
let timerInterval = null

function startTimer() {
  resendTimer.value = 60
  clearInterval(timerInterval)
  timerInterval = setInterval(() => {
    resendTimer.value--
    if (resendTimer.value <= 0) clearInterval(timerInterval)
  }, 1000)
}

onMounted(async () => {
  startTimer()
  // auto-request code on mount
  try {
    await requestVerificationCode({ channel: 'email' })
  } catch {}
  const first = document.querySelector('.code-input')
  if (first) first.focus()
})
onUnmounted(() => { clearInterval(timerInterval) })

function onInput(index, event) {
  const val = event.target.value.replace(/\D/g, '')
  digits.value[index] = val.slice(-1)
  if (val && index < 5) {
    const next = document.querySelectorAll('.code-input')[index + 1]
    if (next) next.focus()
  }
  if (digits.value.every(d => d !== '')) submitCode()
}

function onKeydown(index, event) {
  if (event.key === 'Backspace' && !digits.value[index] && index > 0) {
    const prev = document.querySelectorAll('.code-input')[index - 1]
    if (prev) { digits.value[index - 1] = ''; prev.focus() }
  }
  if (event.key === 'ArrowLeft' && index > 0) document.querySelectorAll('.code-input')[index - 1]?.focus()
  if (event.key === 'ArrowRight' && index < 5) document.querySelectorAll('.code-input')[index + 1]?.focus()
}

function onPaste(event) {
  event.preventDefault()
  const text = (event.clipboardData || window.clipboardData).getData('text')
  const nums = text.replace(/\D/g, '').slice(0, 6).split('')
  nums.forEach((n, i) => { if (i < 6) digits.value[i] = n })
  if (digits.value.every(d => d !== '')) submitCode()
}

async function submitCode() {
  const code = digits.value.join('')
  if (code.length < 6) return
  loading.value = true
  error.value = ''
  success.value = ''
  try {
    await confirmVerificationCode({ channel: 'email', code })
    success.value = 'Email подтверждён!'
    setTimeout(() => router.push('/app'), 900)
  } catch (e) {
    error.value = e.message || 'Неверный код. Попробуйте ещё раз.'
    digits.value = ['', '', '', '', '', '']
    setTimeout(() => document.querySelector('.code-input')?.focus(), 50)
  } finally {
    loading.value = false
  }
}

async function resend() {
  if (resendTimer.value > 0) return
  error.value = ''
  success.value = ''
  try {
    await requestVerificationCode({ channel: 'email' })
    success.value = 'Код отправлен повторно'
    startTimer()
  } catch (e) {
    error.value = e.message || 'Не удалось отправить код'
  }
}
</script>

<template>
  <main class="auth">
    <div class="auth-art">
      <img src="/img/verify.png" alt="" onerror="this.style.display='none'">
      <div class="art-cap">
        <b>ПОДКАПОТ</b>
        Последний шаг — и ты внутри
      </div>
    </div>

    <section class="auth-side">
      <div class="auth-card">
        <router-link to="/" class="auth-back-inline">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>
          На главную
        </router-link>

        <div class="auth-badge" style="margin-top:14px"><span class="led"></span> ПОДТВЕРЖДЕНИЕ</div>
        <h1>Введите код</h1>
        <p class="sub">
          Мы отправили 6-значный код на ваш email.<br>
          Проверьте «Спам», если письмо не пришло.
        </p>

        <div v-if="error" class="auth-error-msg">{{ error }}</div>
        <div v-if="success" class="auth-success-msg">{{ success }}</div>

        <div class="code-inputs" @paste="onPaste">
          <input
            v-for="(digit, i) in digits"
            :key="i"
            v-model="digits[i]"
            type="text"
            inputmode="numeric"
            maxlength="1"
            class="code-input"
            :disabled="loading"
            @input="onInput(i, $event)"
            @keydown="onKeydown(i, $event)"
          />
        </div>

        <button
          class="btn btn-primary btn-block"
          style="height:54px;font-size:16px;margin-top:4px"
          :disabled="loading || digits.join('').length < 6"
          @click="submitCode"
        >
          <span v-if="loading" class="btn-spinner"></span>
          {{ loading ? 'Проверяем...' : 'Подтвердить' }}
        </button>

        <div class="verify-resend">
          <span v-if="resendTimer > 0" style="color:var(--faint)">Отправить повторно через {{ resendTimer }} с</span>
          <span v-else>
            Не получили код?
            <button class="link-btn" @click="resend" :disabled="loading">Отправить ещё раз</button>
          </span>
        </div>

        <div class="auth-foot">
          <router-link to="/app" style="color:var(--faint);font-size:13px">Пропустить пока →</router-link>
        </div>
      </div>
    </section>
  </main>
</template>
