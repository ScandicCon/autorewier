<script setup>
import { ref, computed } from 'vue'
import { findPartByPhoto } from '../api/partFinderApi'

const file = ref(null)
const preview = ref('')
const hint = ref('')
const result = ref(null)
const loading = ref(false)
const error = ref('')

function onSelect(event) {
  error.value = ''
  result.value = null
  const picked = (event.target.files || [])[0]
  if (!picked) return
  if (!picked.type.startsWith('image/')) {
    error.value = 'Выберите изображение (jpg, png).'
    return
  }
  if (picked.size > 8 * 1024 * 1024) {
    error.value = 'Файл больше 8 МБ — выберите фото поменьше.'
    return
  }
  file.value = picked
  if (preview.value) URL.revokeObjectURL(preview.value)
  preview.value = URL.createObjectURL(picked)
}

async function run() {
  if (!file.value) {
    error.value = 'Сначала добавьте фото детали.'
    return
  }
  loading.value = true
  error.value = ''
  result.value = null
  try {
    result.value = await findPartByPhoto(file.value, hint.value)
  } catch (e) {
    error.value = e?.message || 'Не удалось выполнить поиск. Попробуйте ещё раз.'
  } finally {
    loading.value = false
  }
}

const ident = computed(() => result.value?.identification || null)

const confClass = computed(() => {
  const c = ident.value?.confidence ?? 0
  if (c >= 70) return 'pf-conf--high'
  if (c >= 40) return 'pf-conf--medium'
  return 'pf-conf--low'
})

function formatPrice(rub) {
  return new Intl.NumberFormat('ru-RU').format(rub) + ' ₽'
}
</script>

<template>
  <div class="composer-section">
    <div class="composer-label">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
      ПОИСК Б/У ДЕТАЛИ ПО ФОТО
    </div>

    <p class="pf-hint">Сфотографируйте деталь — ИИ распознает её и найдёт похожие объявления на Авито. Можно добавить подсказку (марка/модель) для точности.</p>

    <label class="btn btn-ghost pf-pick">
      <input type="file" accept="image/*" @change="onSelect" hidden>
      Выбрать фото детали
    </label>

    <div v-if="preview" class="pf-preview-wrap">
      <img :src="preview" alt="" class="pf-preview">
    </div>

    <input
      v-model="hint"
      type="text"
      class="input pf-input"
      maxlength="120"
      placeholder="Подсказка (необязательно): напр. Toyota Camry 2015"
      style="margin-top:10px"
    >

    <button
      v-if="file"
      class="btn btn-primary btn-block"
      style="margin-top:10px"
      @click="run"
      :disabled="loading"
    >
      <span v-if="loading" class="btn-spinner"></span>
      {{ loading ? 'Ищем…' : 'Найти деталь' }}
    </button>

    <p v-if="error" class="auth-error-msg" style="margin-top:10px">{{ error }}</p>

    <!-- Результат -->
    <div v-if="result" class="pf-result">
      <div class="pf-ident">
        <div class="pf-ident__head">
          <span class="pf-part">{{ ident.part_name }}</span>
          <span class="pf-conf" :class="confClass">уверенность {{ ident.confidence }}%</span>
        </div>
        <div class="pf-meta">
          <span v-if="ident.category">{{ ident.category }}</span>
          <span v-if="ident.vehicle_hint">· {{ ident.vehicle_hint }}</span>
        </div>
        <div v-if="result.demo" class="pf-badge-demo">Демо-режим (ИИ-распознавание выключено)</div>
        <p v-if="ident.notes" class="pf-notes">{{ ident.notes }}</p>
      </div>

      <div v-if="result.offers.length" class="pf-offers">
        <div v-for="(o, i) in result.offers" :key="i" class="pf-offer">
          <a :href="o.url" target="_blank" rel="noopener noreferrer" class="pf-offer__title">{{ o.title }}</a>
          <span class="pf-offer__price">{{ formatPrice(o.price_rub) }}</span>
        </div>
      </div>
      <p v-else class="pf-hint" style="margin-top:10px">
        Похожих объявлений не нашлось. Попробуйте уточнить подсказку или открыть поиск на Авито.
      </p>

      <a v-if="result.search_url" :href="result.search_url" target="_blank" rel="noopener noreferrer" class="btn btn-ghost btn-block" style="margin-top:10px">
        Открыть все результаты на Авито
      </a>

      <p class="pf-disclaimer">{{ result.disclaimer }}</p>
    </div>
  </div>
</template>

<style scoped>
.pf-hint { color: var(--muted); font-size: 13px; margin: 4px 0 10px; }
.pf-pick { display: inline-flex; cursor: pointer; }
.pf-input { width: 100%; box-sizing: border-box; }
.pf-preview-wrap { margin-top: 10px; }
.pf-preview { max-height: 180px; border-radius: 10px; border: 1px solid var(--line, rgba(255,255,255,0.12)); }
.pf-result { margin-top: 16px; display: flex; flex-direction: column; gap: 12px; }
.pf-ident {
  border: 1px solid var(--line, rgba(255,255,255,0.12));
  border-radius: 10px;
  padding: 12px 14px;
  background: rgba(255,255,255,0.02);
}
.pf-ident__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
.pf-part { font-weight: 700; font-size: 15px; }
.pf-conf { font-size: 11px; text-transform: uppercase; padding: 2px 8px; border-radius: 999px; border: 1px solid currentColor; white-space: nowrap; }
.pf-conf--high { color: #7bd88f; }
.pf-conf--medium { color: #ffb454; }
.pf-conf--low { color: #ff5d5d; }
.pf-meta { color: var(--muted); font-size: 13px; margin-top: 4px; }
.pf-badge-demo { display: inline-block; margin-top: 8px; font-size: 11px; color: #ffb454; border: 1px solid #ffb454; border-radius: 999px; padding: 2px 8px; }
.pf-notes { color: var(--muted); font-size: 12.5px; margin-top: 8px; }
.pf-offers { display: flex; flex-direction: column; gap: 8px; }
.pf-offer {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  border: 1px solid var(--line, rgba(255,255,255,0.12));
  border-radius: 10px;
  padding: 10px 12px;
  background: rgba(255,255,255,0.02);
}
.pf-offer__title { font-size: 14px; color: var(--accent, #6cf); text-decoration: none; }
.pf-offer__title:hover { text-decoration: underline; }
.pf-offer__price { font-weight: 600; font-size: 14px; white-space: nowrap; }
.pf-disclaimer { color: var(--muted); font-size: 11.5px; line-height: 1.45; margin-top: 4px; }
</style>
