<script setup>
import { ref } from 'vue'
import { checkByPlate } from '../api/inspectionApi'

const plate = ref('')
const loading = ref(false)
const error = ref('')
const report = ref(null)

async function run() {
  error.value = ''
  report.value = null
  const value = plate.value.trim()
  if (!value) {
    error.value = 'Введите гос-номер'
    return
  }
  loading.value = true
  try {
    report.value = await checkByPlate(value)
  } catch (e) {
    error.value = e?.status === 402
      ? 'Закончились VIN-отчёты. Оформите Pro или докупите пакет.'
      : (e?.message || 'Не удалось пробить номер. Проверьте формат (пример: А123ВС777).')
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="composer-section">
    <div class="composer-label">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="6" width="20" height="12" rx="2"/><path d="M6 10h.01M10 10h4M6 14h12"/></svg>
      ПРОБИВКА ПО ГОС-НОМЕРУ
    </div>

    <p class="pc-hint">Введите госномер — по нему определится VIN, история, ограничения и залоги.</p>

    <div class="pc-row">
      <input
        v-model="plate"
        class="pc-input"
        placeholder="А123ВС777"
        maxlength="9"
        :disabled="loading"
        @keyup.enter="run"
      >
      <button class="btn btn-primary" @click="run" :disabled="loading">
        <span v-if="loading" class="btn-spinner"></span>
        {{ loading ? 'Пробиваем…' : 'Пробить' }}
      </button>
    </div>

    <p v-if="error" class="auth-error-msg" style="margin-top:10px">{{ error }}</p>

    <div v-if="report" class="pc-result">
      <div class="pc-plate">{{ report.plate }}</div>
      <p class="pc-summary">{{ report.summary }}</p>
      <p v-if="report.demo" class="pc-demo">Демо-режим: для реальных данных подключается Autocode.</p>
    </div>
  </div>
</template>

<style scoped>
.pc-hint { color: var(--muted); font-size: 13px; margin: 4px 0 10px; }
.pc-row { display: flex; gap: 10px; align-items: stretch; }
.pc-input {
  flex: 1; text-transform: uppercase; letter-spacing: .08em; font-weight: 600;
}
.pc-result {
  margin-top: 14px; border: 1px solid var(--line, rgba(255,255,255,0.12));
  border-radius: 10px; padding: 12px; background: rgba(255,255,255,0.02);
}
.pc-plate { font-weight: 700; letter-spacing: .1em; font-size: 16px; margin-bottom: 6px; }
.pc-summary { font-size: 14px; }
.pc-demo { color: var(--muted); font-size: 12.5px; margin-top: 6px; }
</style>
