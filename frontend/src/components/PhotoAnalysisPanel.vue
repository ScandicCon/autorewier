<script setup>
import { ref } from 'vue'
import { analyzePhotos } from '../api/inspectionApi'

const MAX_FILES = 5

const files = ref([])
const previews = ref([])
const findings = ref([])
const loading = ref(false)
const error = ref('')
const done = ref(false)

function onSelect(event) {
  error.value = ''
  done.value = false
  findings.value = []
  const picked = Array.from(event.target.files || [])
  const images = picked.filter((f) => f.type.startsWith('image/'))
  if (images.length === 0) {
    error.value = 'Выберите изображения (jpg, png).'
    return
  }
  const limited = images.slice(0, MAX_FILES)
  files.value = limited
  previews.value.forEach((u) => URL.revokeObjectURL(u))
  previews.value = limited.map((f) => URL.createObjectURL(f))
}

async function run() {
  if (files.value.length === 0) {
    error.value = 'Сначала добавьте фото.'
    return
  }
  loading.value = true
  error.value = ''
  findings.value = []
  done.value = false
  try {
    findings.value = await analyzePhotos(files.value)
    done.value = true
  } catch (e) {
    error.value = e?.message || 'Не удалось проанализировать фото. Попробуйте ещё раз.'
  } finally {
    loading.value = false
  }
}

function confidenceLabel(c) {
  return { high: 'высокая', medium: 'средняя', low: 'низкая' }[c] || c
}
</script>

<template>
  <div class="composer-section">
    <div class="composer-label">
      <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><polyline points="21 15 16 10 5 21"/></svg>
      АНАЛИЗ ФОТО НЕЙРОСЕТЬЮ (до {{ MAX_FILES }})
    </div>

    <p class="pa-hint">Загрузите фото кузова — ИИ подсветит возможные повреждения по зонам.</p>

    <label class="btn btn-ghost pa-pick">
      <input type="file" accept="image/*" multiple @change="onSelect" hidden>
      Выбрать фото
    </label>

    <div v-if="previews.length" class="photo-preview-row" style="margin-top:10px">
      <img v-for="(url, i) in previews" :key="i" :src="url" alt="" class="photo-preview-thumb">
    </div>

    <button
      v-if="files.length"
      class="btn btn-primary btn-block"
      style="margin-top:10px"
      @click="run"
      :disabled="loading"
    >
      <span v-if="loading" class="btn-spinner"></span>
      {{ loading ? 'Анализируем…' : `Проанализировать (${files.length})` }}
    </button>

    <p v-if="error" class="auth-error-msg" style="margin-top:10px">{{ error }}</p>

    <div v-if="done && findings.length" class="pa-results">
      <div v-for="(f, i) in findings" :key="i" class="pa-finding">
        <div class="pa-finding__head">
          <span class="pa-zone">{{ f.zone || 'Зона не определена' }}</span>
          <span class="pa-conf" :class="`pa-conf--${f.confidence}`">{{ confidenceLabel(f.confidence) }}</span>
        </div>
        <div class="pa-issue">{{ f.issue }}</div>
        <div v-if="f.rationale" class="pa-rationale">{{ f.rationale }}</div>
        <div v-if="f.action" class="pa-action">→ {{ f.action }}</div>
      </div>
    </div>

    <p v-else-if="done && !findings.length" class="pa-hint" style="margin-top:10px">
      Явных повреждений по фото не выявлено — проверьте лично на осмотре.
    </p>
  </div>
</template>

<style scoped>
.pa-hint { color: var(--muted); font-size: 13px; margin: 4px 0 10px; }
.pa-pick { display: inline-flex; cursor: pointer; }
.pa-results { margin-top: 14px; display: flex; flex-direction: column; gap: 10px; }
.pa-finding {
  border: 1px solid var(--line, rgba(255,255,255,0.12));
  border-radius: 10px;
  padding: 10px 12px;
  background: rgba(255,255,255,0.02);
}
.pa-finding__head { display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 4px; }
.pa-zone { font-weight: 600; font-size: 13px; letter-spacing: .02em; }
.pa-conf { font-size: 11px; text-transform: uppercase; padding: 2px 8px; border-radius: 999px; border: 1px solid currentColor; }
.pa-conf--high { color: #ff5d5d; }
.pa-conf--medium { color: #ffb454; }
.pa-conf--low { color: #7bd88f; }
.pa-issue { font-size: 14px; }
.pa-rationale { color: var(--muted); font-size: 12.5px; margin-top: 3px; }
.pa-action { color: var(--accent, #6cf); font-size: 12.5px; margin-top: 4px; }
</style>
