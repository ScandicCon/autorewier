<script setup>
import { ref, reactive, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { createInspection, getToken } from '../api/inspectionApi'
import PhotoAnalysisPanel from '../components/PhotoAnalysisPanel.vue'
import PlateCheckPanel from '../components/PlateCheckPanel.vue'

const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')

const router = useRouter()
const route = useRoute()

onMounted(() => {
  const urlParam = route.query.url
  if (urlParam) { form.listing_url = urlParam }
})
const step = ref(1)
const loading = ref(false)
const parsing = ref(false)
const parseError = ref('')
const parseFailed = ref(false)
const error = ref('')
const parsedPhotos = ref([])
const ownPhotoFindings = ref([])

// Поэтапный прогресс генерации отчёта (анализ идёт 10–40 сек одним запросом —
// без этого пользователь видит замерший экран и уходит).
const analysisStages = ref([])
const stageIndex = ref(0)
const elapsedSec = ref(0)
let stageTimer = null
let elapsedTimer = null

function buildStages() {
  const stages = []
  if (form.listing_url) stages.push({ label: 'Парсим объявление', dur: 8 })
  if (parsedPhotos.value.length || ownPhotoFindings.value.length) {
    stages.push({ label: 'Анализируем фото нейросетью', dur: 14 })
  }
  stages.push({ label: 'Считаем риски и смету ремонта', dur: 10 })
  stages.push({ label: 'Готовим торг и чеклист', dur: 8 })
  return stages
}

function startProgress() {
  analysisStages.value = buildStages()
  stageIndex.value = 0
  elapsedSec.value = 0
  elapsedTimer = setInterval(() => { elapsedSec.value += 1 }, 1000)
  scheduleNextStage()
}

function scheduleNextStage() {
  const cur = analysisStages.value[stageIndex.value]
  // Последний этап держим активным до ответа сервера
  if (!cur || stageIndex.value >= analysisStages.value.length - 1) return
  stageTimer = setTimeout(() => {
    stageIndex.value += 1
    scheduleNextStage()
  }, cur.dur * 1000)
}

function stopProgress() {
  clearTimeout(stageTimer)
  clearInterval(elapsedTimer)
  stageTimer = null
  elapsedTimer = null
}

const form = reactive({
  listing_url: '',
  listing_source: 'auto',
  brand: '',
  model: '',
  year: new Date().getFullYear() - 3,
  mileage_km: '',
  price_rub: '',
  vin: '',
  user_preferences: 'Ищу максимально ликвидный вариант с адекватной стоимостью владения.',
  photo_note: ''
})

function detectSource(url) {
  const s = String(url || '').toLowerCase()
  if (s.includes('avito.ru')) return 'avito'
  if (s.includes('drom.ru')) return 'drom'
  if (s.includes('auto.ru')) return 'auto_ru'
  return 'generic'
}

// Auto-parse listing when URL is entered
let parseDebounce = null
watch(() => form.listing_url, (url) => {
  clearTimeout(parseDebounce)
  parsedPhotos.value = []
  parseError.value = ''
  parseFailed.value = false
  if (!url || !url.startsWith('http')) return
  parseDebounce = setTimeout(() => fetchListing(url), 800)
})

// Честные сообщения вместо молчания: бэкенд различает капчу, блокировку и
// прочие фейлы (parse_status) — показываем, что случилось и что делать.
const PARSE_FAIL_MESSAGES = {
  captcha: 'Avito показал капчу и не отдал данные. Заполните поля вручную — анализ будет таким же полным.',
  blocked: 'Avito временно ограничил доступ к объявлению. Попробуйте позже или заполните поля вручную.',
  transient_error: 'Площадка не ответила. Попробуйте ещё раз или заполните поля вручную.',
}
const PARSE_FAIL_DEFAULT = 'Не удалось прочитать объявление — заполните поля вручную, анализ от этого не пострадает.'

async function fetchListing(url) {
  parsing.value = true
  parseError.value = ''
  parseFailed.value = false
  try {
    const res = await fetch(`${API_BASE}/api/v1/parse-listing`, {
      method: 'POST',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json', ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}) },
      body: JSON.stringify({ url })
    })
    if (!res.ok) throw new Error('parse_failed')
    const data = await res.json()
    if (data.parse_ok === false) {
      parseFailed.value = true
      parseError.value = PARSE_FAIL_MESSAGES[data.parse_status] || data.parse_error || PARSE_FAIL_DEFAULT
      return
    }
    if (data.vehicle) {
      if (data.vehicle.brand && !form.brand) form.brand = data.vehicle.brand
      if (data.vehicle.model && !form.model) form.model = data.vehicle.model
      if (data.vehicle.year && !form.year) form.year = data.vehicle.year
      if (data.vehicle.mileage_km && !form.mileage_km) form.mileage_km = data.vehicle.mileage_km
      if (data.vehicle.price_rub && !form.price_rub) form.price_rub = data.vehicle.price_rub
      if (data.vehicle.vin && !form.vin) form.vin = data.vehicle.vin
    }
    if (data.photo_urls?.length) parsedPhotos.value = data.photo_urls
    // Парсинг «успешен», но ничего не извлечено — тоже честно сообщаем
    const v = data.vehicle || {}
    const gotAnything = data.photo_urls?.length || v.brand || v.model || v.price_rub || v.mileage_km
    if (!gotAnything) {
      parseFailed.value = true
      parseError.value = PARSE_FAIL_DEFAULT
    }
  } catch {
    parseFailed.value = true
    parseError.value = PARSE_FAIL_DEFAULT
  } finally {
    parsing.value = false
  }
}

onUnmounted(stopProgress)

function onOwnPhotoFindings(findings) {
  ownPhotoFindings.value = findings || []
}

function goNext() {
  if (!form.brand && !form.listing_url) { error.value = 'Введите ссылку или марку автомобиля'; return }
  error.value = ''
  step.value = 2
}

async function submit() {
  loading.value = true
  error.value = ''
  startProgress()
  const source = form.listing_source === 'auto' ? detectSource(form.listing_url) : form.listing_source
  try {
    const created = await createInspection({
      listing_url: form.listing_url || null,
      vehicle: {
        brand: form.brand || null,
        model: form.model || null,
        year: Number(form.year) || null,
        mileage_km: form.mileage_km ? Number(form.mileage_km) : null,
        price_rub: form.price_rub ? Number(form.price_rub) : null,
        vin: form.vin || null
      },
      user_preferences: form.user_preferences,
      photos_metadata: parsedPhotos.value.map((url, i) => ({
        photo_url: url,
        zone: null,
        note: form.photo_note?.trim() ? `${form.photo_note.trim()} · фото ${i + 1}` : null
      })),
      extra_image_findings: ownPhotoFindings.value,
      // Only re-parse on backend when the frontend pre-parse succeeded (photos loaded).
      // If pre-parse failed the user filled data manually — skip the slow backend fetch.
      require_avito_parse: Boolean(form.listing_url) && source === 'avito' && parsedPhotos.value.length > 0
    })
    stageIndex.value = analysisStages.value.length // все этапы — done
    router.push(`/app/inspection/${created.id}`)
  } catch (e) {
    error.value = e.message || 'Не удалось создать проверку. Попробуйте ещё раз.'
  } finally {
    stopProgress()
    loading.value = false
  }
}
</script>

<template>
  <div class="page-bg-art" aria-hidden="true">
    <img src="/img/new-insp.png" alt="" class="page-bg-img">
  </div>

  <!-- NAV -->
  <header class="nav">
    <div class="wrap">
      <router-link class="back-link" to="/app" style="text-decoration:none">
        <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>
        Мои проверки
      </router-link>
      <router-link class="logo" to="/"><img class="logo-ico" src="/img/logo-mark.png" alt="" aria-hidden="true">ПОДКАПОТ</router-link>
      <div style="width:120px"></div>
    </div>
  </header>

  <div class="wrap new-insp-content">
    <!-- PROGRESS -->
    <div class="form-progress" style="margin-top:20px">
      <div class="form-progress__step" :class="{ active: step >= 1 }"></div>
      <div class="form-progress__step" :class="{ active: step >= 2 }"></div>
    </div>

    <!-- BANNER -->
    <div class="pbanner" style="grid-template-columns:1fr;padding:0 0 20px">
      <div>
        <div class="carline">// НОВАЯ ПРОВЕРКА</div>
        <h1 style="font-family:'Unbounded',sans-serif;font-size:clamp(24px,4vw,38px);margin:8px 0">
          {{ step === 1 ? 'Укажи данные авто' : 'Предпочтения и запуск' }}
        </h1>
        <p style="color:var(--muted);font-size:16px">
          {{ step === 1 ? 'Ссылка на объявление или параметры вручную' : 'Расскажи, что важно при покупке' }}
        </p>
      </div>
    </div>

    <div v-if="error" class="auth-error-msg" style="margin-bottom:16px">{{ error }}</div>

    <!-- STEP 1 -->
    <div v-if="step === 1" class="panel hud">
      <div class="panel-b">
        <!-- URL -->
        <div class="composer-section">
          <div class="composer-label">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
            ИСТОЧНИК ОБЪЯВЛЕНИЯ
          </div>
          <div class="composer-grid">
            <label class="wide" style="position:relative">
              Ссылка на объявление
              <input
                v-model="form.listing_url"
                type="url"
                placeholder="https://www.avito.ru/... или https://auto.drom.ru/..."
                :disabled="loading"
                style="padding-right:36px"
              >
              <span v-if="parsing" style="position:absolute;right:12px;bottom:13px;width:16px;height:16px;border:2px solid var(--line);border-top-color:var(--cyan);border-radius:50%;animation:spin .8s linear infinite;display:inline-block"></span>
            </label>
            <label>
              Площадка
              <select v-model="form.listing_source" :disabled="loading">
                <option value="auto">Определить автоматически</option>
                <option value="avito">Avito</option>
                <option value="drom">Drom</option>
                <option value="auto_ru">Auto.ru</option>
                <option value="generic">Другая</option>
              </select>
            </label>
            <label style="align-content:end">
              <span v-if="parseError" style="color:var(--cau);font-size:12px;line-height:1.4">{{ parseError }}</span>
              <span v-else-if="parsedPhotos.length" style="color:var(--safe);font-size:12px">
                Найдено {{ parsedPhotos.length }} фото · данные авто заполнены
              </span>
              <span v-else style="color:var(--faint);font-size:12px;line-height:1.4">
                Данные заполнятся автоматически после вставки ссылки
              </span>
            </label>
          </div>
        </div>

        <!-- ПАРАМЕТРЫ -->
        <div class="composer-section" :style="parseFailed ? 'border:1px solid rgba(255,177,61,.45);border-radius:12px;padding:14px;transition:border-color .3s' : ''">
          <div v-if="parseFailed" style="color:var(--cau);font-size:13px;margin-bottom:10px;display:flex;align-items:center;gap:6px">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 9v4"/><path d="M12 17h.01"/><circle cx="12" cy="12" r="10"/></svg>
            Введите данные вручную — этого достаточно для полного анализа
          </div>
          <div class="composer-label">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h11a2 2 0 012 2v3"/><rect x="9" y="11" width="14" height="10" rx="2"/></svg>
            ПАРАМЕТРЫ АВТОМОБИЛЯ
          </div>
          <div class="composer-grid">
            <label>Марка<input v-model="form.brand" placeholder="Toyota" :disabled="loading"></label>
            <label>Модель<input v-model="form.model" placeholder="Camry" :disabled="loading"></label>
            <label>Год<input v-model.number="form.year" type="number" min="1980" max="2030" :disabled="loading"></label>
            <label>Пробег, км<input v-model.number="form.mileage_km" type="number" min="0" placeholder="83000" :disabled="loading"></label>
            <label>Цена, ₽<input v-model.number="form.price_rub" type="number" min="0" placeholder="2450000" :disabled="loading"></label>
            <label>VIN<input v-model="form.vin" placeholder="Опционально" :disabled="loading"></label>
          </div>
        </div>

        <!-- PARSED PHOTO PREVIEW -->
        <div v-if="parsedPhotos.length" class="composer-section">
          <div class="composer-label">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
            ФОТО ИЗ ОБЪЯВЛЕНИЯ ({{ parsedPhotos.length }})
          </div>
          <div class="photo-preview-row">
            <img
              v-for="(url, i) in parsedPhotos.slice(0, 5)"
              :key="i"
              :src="url"
              :alt="`Фото ${i+1}`"
              class="photo-preview-thumb"
              onerror="this.style.display='none'"
            >
            <span v-if="parsedPhotos.length > 5" style="color:var(--muted);font-size:13px;align-self:center">+{{ parsedPhotos.length - 5 }}</span>
          </div>
        </div>

        <button class="btn btn-primary btn-block" style="margin-top:8px" @click="goNext" :disabled="parsing">
          {{ parsing ? 'Загружаем данные…' : 'Далее →' }}
        </button>
      </div>
    </div>

    <!-- STEP 2 -->
    <div v-else class="panel hud">
      <div class="panel-b">
        <div class="composer-section">
          <div class="composer-label">
            <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 2a10 10 0 100 20 10 10 0 000-20z"/><path d="M12 8v4l3 3"/></svg>
            ПРЕДПОЧТЕНИЯ
          </div>
          <div class="composer-grid">
            <label class="wide">
              Цель и приоритеты
              <textarea v-model="form.user_preferences" rows="4" placeholder="Ищу ликвидный вариант с адекватной стоимостью владения. Важна надёжность коробки и подвески." :disabled="loading"></textarea>
            </label>
            <label class="wide">
              Особое внимание при осмотре
              <input v-model="form.photo_note" placeholder="Зазоры кузова, ржавчина порогов, состояние салона" :disabled="loading">
            </label>
          </div>
        </div>

        <PhotoAnalysisPanel @analyzed="onOwnPhotoFindings" />

        <PlateCheckPanel />

        <!-- ПРОГРЕСС АНАЛИЗА: этапы вместо замершего экрана на 10–40 сек -->
        <div v-if="loading" class="composer-section" style="border:1px solid rgba(63,208,255,.25);border-radius:12px;padding:18px;background:rgba(63,208,255,.03)">
          <div class="composer-label" style="margin-bottom:12px">АНАЛИЗИРУЕМ АВТОМОБИЛЬ</div>
          <div v-for="(st, i) in analysisStages" :key="i" style="display:flex;align-items:center;gap:10px;padding:5px 0">
            <!-- done -->
            <svg v-if="i < Math.min(stageIndex, analysisStages.length)" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="var(--safe)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
            <!-- active -->
            <span v-else-if="i === Math.min(stageIndex, analysisStages.length - 1)" style="width:16px;height:16px;border:2px solid var(--line);border-top-color:var(--cyan);border-radius:50%;animation:spin .8s linear infinite;flex-shrink:0"></span>
            <!-- pending -->
            <span v-else style="width:16px;height:16px;display:inline-flex;align-items:center;justify-content:center;flex-shrink:0"><span style="width:6px;height:6px;border-radius:50%;background:var(--line)"></span></span>
            <span :style="{ fontSize:'14px', color: i <= Math.min(stageIndex, analysisStages.length - 1) ? 'var(--ink)' : 'var(--faint)' }">{{ st.label }}</span>
          </div>
          <div style="margin-top:10px;font-size:12px;color:var(--faint)">
            Обычно 15–40 секунд · прошло {{ elapsedSec }} с
          </div>
        </div>

        <div style="display:flex;gap:10px;margin-top:8px">
          <button class="btn btn-ghost" style="flex:1" @click="step = 1" :disabled="loading">← Назад</button>
          <button class="btn btn-primary" style="flex:2" @click="submit" :disabled="loading">
            <span v-if="loading" class="btn-spinner"></span>
            {{ loading ? 'Анализируем…' : 'Запустить анализ' }}
          </button>
        </div>

        <p v-if="error" class="auth-error-msg" style="margin-top:12px">{{ error }}</p>
      </div>
    </div>
  </div>
</template>
