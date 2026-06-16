<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import { fetchInspectionDetails, getToken } from '../api/inspectionApi'

const route = useRoute()
const inspection = ref(null)
const loading = ref(true)
const error = ref('')

// Lightbox
const lightboxIdx = ref(null)
const lightboxOpen = computed(() => lightboxIdx.value !== null)
function openLightbox(i) { lightboxIdx.value = i }
function closeLightbox() { lightboxIdx.value = null }
function prevPhoto() { if (lightboxIdx.value > 0) lightboxIdx.value-- }
function nextPhoto() { if (lightboxIdx.value < photos.value.length - 1) lightboxIdx.value++ }

function onKeydown(e) {
  if (!lightboxOpen.value) return
  if (e.key === 'Escape') closeLightbox()
  if (e.key === 'ArrowLeft') prevPhoto()
  if (e.key === 'ArrowRight') nextPhoto()
}

// Post-inspection notes
const postNotes = ref('')
const postNotesSaving = ref(false)
const postNotesSaved = ref(false)

async function savePostNotes() {
  postNotesSaving.value = true
  postNotesSaved.value = false
  try {
    const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
    await fetch(`${API_BASE}/api/v1/inspections/${route.params.id}/post`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}) },
      credentials: 'include',
      body: JSON.stringify({ post_notes: postNotes.value })
    })
    postNotesSaved.value = true
    setTimeout(() => { postNotesSaved.value = false }, 3000)
  } catch {}
  finally { postNotesSaving.value = false }
}

// Checklist checked state (local only)
const checkedItems = ref({})
function toggleCheck(key) {
  checkedItems.value[key] = !checkedItems.value[key]
}

onMounted(async () => {
  window.addEventListener('keydown', onKeydown)
  try {
    inspection.value = await fetchInspectionDetails(route.params.id)
    postNotes.value = inspection.value?.post_notes || ''
  } catch (e) {
    error.value = e.message || 'Не удалось загрузить проверку'
  } finally {
    loading.value = false
  }
})
onUnmounted(() => { window.removeEventListener('keydown', onKeydown) })

// ── Helpers ──────────────────────────────────────────────────────
function carTitle(insp) {
  if (!insp) return '—'
  const parts = [insp.brand, insp.model, insp.year ? String(insp.year) : null].filter(Boolean)
  return parts.length ? parts.join(' · ') : (insp.listing_url ? 'Автомобиль' : 'Без названия')
}

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('ru-RU')
}

const photos = computed(() => {
  if (!inspection.value) return []
  const meta = inspection.value.photos_metadata || []
  return meta.map(p => (typeof p === 'string' ? p : p?.photo_url)).filter(Boolean)
})

const isDone = computed(() =>
  inspection.value && ['pre_inspection', 'post_inspection'].includes(inspection.value.stage)
)

// verdict: "worth_looking" | "caution" | "skip"
const verdictInfo = computed(() => {
  const v = inspection.value?.verdict
  if (v === 'worth_looking') return {
    label: 'Рекомендуем', cls: 'v-safe', color: 'var(--safe)',
    gradient: 'linear-gradient(135deg,rgba(55,210,126,.18),transparent)', icon: 'check'
  }
  if (v === 'caution') return {
    label: 'Осторожно', cls: 'v-cau', color: 'var(--cau)',
    gradient: 'linear-gradient(135deg,rgba(255,183,77,.18),transparent)', icon: 'warn'
  }
  if (v === 'skip') return {
    label: 'Не рекомендуем', cls: 'v-risk', color: 'var(--risk)',
    gradient: 'linear-gradient(135deg,rgba(255,99,71,.18),transparent)', icon: 'x'
  }
  return {
    label: 'Анализ', cls: '', color: 'var(--cyan)',
    gradient: 'linear-gradient(135deg,rgba(63,208,255,.1),transparent)', icon: 'scan'
  }
})

const report = computed(() => inspection.value?.pre_report || null)
const riskScore = computed(() => report.value?.risk_score ?? null)

const repairRange = computed(() => {
  const insp = inspection.value
  if (!insp) return null
  const rmin = insp.repair_min_rub ?? report.value?.repair_total_min
  const rmax = insp.repair_max_rub ?? report.value?.repair_total_max
  if (rmin != null && rmax != null) return `${fmt(rmin)} – ${fmt(rmax)} ₽`
  return null
})

const risks = computed(() => report.value?.risks || [])

const p1Count = computed(() =>
  risks.value.filter(r => r.severity === 'high' || r.priority === 'high').length
)

const recommendations = computed(() => {
  const r = report.value
  if (!r) return []
  return [
    ...(r.preference_notes || []),
    ...(r.negotiation_tips || []),
  ].filter(Boolean)
})

// New report sections
const modelWeakPoints = computed(() => report.value?.model_weak_points || [])
const repairLines = computed(() => report.value?.repair_lines || [])
const checklistItems = computed(() => report.value?.checklist || [])
const partsPricing = computed(() => report.value?.parts_pricing || [])

const repairTotal = computed(() => {
  const lines = repairLines.value
  if (!lines.length) return null
  const minTotal = lines.reduce((s, l) => s + (l.min_rub || 0), 0)
  const maxTotal = lines.reduce((s, l) => s + (l.max_rub || 0), 0)
  return { min: minTotal, max: maxTotal }
})

const checklistGroups = computed(() => {
  const items = checklistItems.value
  if (!items.length) return []
  const groups = {}
  items.forEach((item, idx) => {
    const g = item.zone || item.group || 'Общее'
    if (!groups[g]) groups[g] = []
    groups[g].push({ ...item, _idx: idx })
  })
  return Object.entries(groups).map(([group, items]) => ({ group, items }))
})

function priorityBadgeClass(priority) {
  if (priority === 'critical') return 'priority-badge priority-critical'
  if (priority === 'important') return 'priority-badge priority-important'
  return 'priority-badge priority-normal'
}

function priorityLabel(priority) {
  if (priority === 'critical') return 'Критично'
  if (priority === 'important') return 'Важно'
  return 'Норма'
}
</script>

<template>
  <!-- PAGE BG ART -->
  <div class="page-bg-art" aria-hidden="true">
    <img src="/img/service-output.png" alt="" class="page-bg-img">
  </div>

  <!-- NAV -->
  <header class="nav">
    <div class="wrap">
      <div style="display:flex;align-items:center;gap:16px">
        <router-link class="back-link" to="/app" style="text-decoration:none">
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 18l-6-6 6-6"/></svg>
          Мои проверки
        </router-link>
      </div>
      <router-link class="logo" to="/app">ПОДКАПОТ</router-link>
      <div style="width:120px"></div>
    </div>
  </header>

  <!-- LIGHTBOX -->
  <Teleport to="body">
    <div v-if="lightboxOpen" class="lightbox" @click.self="closeLightbox">
      <button class="lightbox-close" @click="closeLightbox" aria-label="Закрыть">✕</button>
      <button v-if="lightboxIdx > 0" class="lightbox-nav lightbox-prev" @click.stop="prevPhoto" aria-label="Назад">‹</button>
      <img :src="photos[lightboxIdx]" :alt="`Фото ${lightboxIdx + 1}`">
      <button v-if="lightboxIdx < photos.length - 1" class="lightbox-nav lightbox-next" @click.stop="nextPhoto" aria-label="Вперёд">›</button>
      <div class="lightbox-counter">{{ lightboxIdx + 1 }} / {{ photos.length }}</div>
    </div>
  </Teleport>

  <!-- LOADING -->
  <div v-if="loading" style="display:flex;justify-content:center;align-items:center;min-height:60vh">
    <div class="btn-spinner" style="width:40px;height:40px;border-width:3px"></div>
  </div>

  <!-- ERROR -->
  <div v-else-if="error" class="wrap" style="padding-top:60px;text-align:center">
    <p style="color:var(--risk)">{{ error }}</p>
    <router-link to="/app" class="btn btn-ghost" style="margin-top:16px;display:inline-flex">← Назад</router-link>
  </div>

  <!-- CONTENT -->
  <div v-else-if="inspection" class="wrap" style="padding-top:24px;padding-bottom:60px">

    <!-- BANNER -->
    <div class="pbanner">
      <div>
        <div class="carline">// ОТЧЁТ #{{ inspection.id }}</div>
        <h1 style="font-family:'Unbounded',sans-serif;font-size:clamp(22px,3.5vw,36px);margin:8px 0">
          {{ carTitle(inspection) }}
        </h1>
        <p style="color:var(--muted);font-size:15px">
          {{ new Date(inspection.created_at).toLocaleDateString('ru-RU', {day:'numeric',month:'long',year:'numeric'}) }}
        </p>
      </div>
      <div style="display:flex;align-items:flex-start;padding-top:8px">
        <img
          v-if="photos.length"
          :src="photos[0]"
          alt="Главное фото"
          style="width:100%;max-width:260px;aspect-ratio:4/3;object-fit:cover;border-radius:var(--r-sm);border:1px solid var(--line2);cursor:zoom-in"
          @click="openLightbox(0)"
          onerror="this.style.display='none'"
        >
        <img
          v-else
          src="/img/report-detail.png"
          alt=""
          style="width:100%;max-width:260px;border-radius:var(--r-sm);border:1px solid var(--line2);opacity:.55"
          onerror="this.style.display='none'"
        >
      </div>
    </div>

    <!-- PHOTO GALLERY (Avito-style) -->
    <div v-if="photos.length > 1" class="photo-avito" style="margin-bottom:24px">
      <!-- Main large photo -->
      <div class="photo-main" @click="openLightbox(0)">
        <img :src="photos[0]" alt="Фото 1" onerror="this.style.display='none'">
      </div>
      <!-- 2x2 thumbnails grid -->
      <div class="photo-grid">
        <div
          v-for="(url, i) in photos.slice(1, 5)"
          :key="i"
          class="photo-thumb"
          @click="openLightbox(i + 1)"
        >
          <img :src="url" :alt="`Фото ${i+2}`" onerror="this.style.display='none'">
          <!-- "+N ещё" overlay on last thumb if there are more than 5 photos -->
          <div v-if="i === 3 && photos.length > 5" class="photo-more-overlay">
            +{{ photos.length - 5 }} ещё
          </div>
        </div>
      </div>
    </div>

    <!-- REPORT GRID -->
    <div class="report-grid">

      <!-- MAIN -->
      <main class="report-main">

        <!-- PENDING -->
        <div v-if="!isDone" class="panel hud" style="text-align:center;padding:48px 24px">
          <div class="btn-spinner" style="width:36px;height:36px;border-width:3px;margin:0 auto 16px"></div>
          <p style="color:var(--muted)">Анализ выполняется. Обновите страницу через минуту.</p>
          <button class="btn btn-ghost" style="margin-top:20px" @click="()=>window.location.reload()">Обновить</button>
        </div>

        <!-- DONE -->
        <template v-if="isDone && report">

          <!-- SUMMARY -->
          <div class="panel hud" style="margin-bottom:16px">
            <div class="panel-h">
              <svg class="ico" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              <h2>Итоговый вывод</h2>
            </div>
            <div class="panel-b">
              <p style="font-size:15px;line-height:1.75;color:var(--fg)">{{ report.summary }}</p>
            </div>
          </div>

          <!-- RISKS -->
          <div v-if="risks.length" class="panel hud" style="margin-bottom:16px">
            <div class="panel-h">
              <svg class="ico" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
              <h2>Найденные риски</h2>
              <span class="sp"></span>
              <span style="font-size:12px;color:var(--muted)">{{ risks.length }} всего</span>
            </div>
            <div class="panel-b">
              <div
                v-for="(risk, i) in risks"
                :key="i"
                class="issue-row"
                :class="risk.severity === 'high' ? 'issue-p1' : 'issue-p2'"
              >
                <span class="issue-badge">{{ risk.severity === 'high' ? 'P1' : 'P2' }}</span>
                <div>
                  <div class="issue-title">{{ risk.title }}</div>
                  <div class="issue-desc">{{ risk.description }}</div>
                </div>
              </div>
            </div>
          </div>

          <!-- СЛАБЫЕ МЕСТА МОДЕЛИ -->
          <div v-if="modelWeakPoints.length" class="panel hud" style="margin-bottom:16px">
            <div class="panel-h">
              <svg class="ico" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
              <h2>Слабые места модели</h2>
            </div>
            <div class="panel-b">
              <ul style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:8px">
                <li
                  v-for="(point, i) in modelWeakPoints"
                  :key="i"
                  style="display:flex;gap:10px;align-items:flex-start;font-size:14px;color:var(--fg);line-height:1.5"
                >
                  <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--cyan)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex-shrink:0;margin-top:3px"><polyline points="9 18 15 12 9 6"/></svg>
                  <span>{{ point }}</span>
                </li>
              </ul>
            </div>
          </div>

          <!-- СМЕТА РЕМОНТА -->
          <div v-if="repairLines.length" class="panel hud" style="margin-bottom:16px">
            <div class="panel-h">
              <svg class="ico" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="3" width="20" height="14" rx="2"/><line x1="8" y1="21" x2="16" y2="21"/><line x1="12" y1="17" x2="12" y2="21"/></svg>
              <h2>Смета ремонта</h2>
            </div>
            <div class="panel-b">
              <table class="repair-table">
                <thead>
                  <tr>
                    <th style="text-align:left;color:var(--muted);font-size:11px;font-weight:600;padding:0 0 10px;text-transform:uppercase;letter-spacing:.5px">Работа / деталь</th>
                    <th style="text-align:right;color:var(--muted);font-size:11px;font-weight:600;padding:0 0 10px;text-transform:uppercase;letter-spacing:.5px">Стоимость</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(line, i) in repairLines" :key="i" class="repair-row">
                    <td style="padding:10px 0;border-bottom:1px solid var(--line)">
                      <div style="font-size:14px;font-weight:500;color:var(--fg)">{{ line.description }}</div>
                      <div style="font-size:11px;color:var(--muted);margin-top:2px">{{ line.category }}</div>
                    </td>
                    <td style="padding:10px 0;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap;font-variant-numeric:tabular-nums;font-weight:600;font-size:13px">
                      {{ fmt(line.min_rub) }} – {{ fmt(line.max_rub) }} ₽
                    </td>
                  </tr>
                </tbody>
              </table>
              <div v-if="repairTotal" class="repair-total">
                <span style="color:var(--muted);font-size:13px">Итого:</span>
                <span style="font-family:'Unbounded',sans-serif;font-size:15px;font-weight:700;color:var(--cyan)">
                  {{ fmt(repairTotal.min) }} – {{ fmt(repairTotal.max) }} ₽
                </span>
              </div>

              <!-- ЧТО КУПИТЬ (merged from Запчасти) -->
              <div v-if="partsPricing.length" style="margin-top:20px;border-top:1px solid var(--line);padding-top:16px">
                <div style="font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px;font-weight:600">Что купить</div>
                <div class="parts-grid">
                  <div v-for="(part, i) in partsPricing" :key="i" class="part-card">
                    <div style="flex:1;min-width:0">
                      <div style="font-size:14px;font-weight:600;color:var(--fg);margin-bottom:4px">{{ part.part_name }}</div>
                      <div style="font-size:13px;color:var(--cyan);font-variant-numeric:tabular-nums;font-weight:700">
                        <template v-if="part.estimate_min || part.min_rub">
                          {{ fmt(part.estimate_min || part.min_rub) }} – {{ fmt(part.estimate_max || part.max_rub) }} ₽
                        </template>
                        <template v-else>— — ₽</template>
                      </div>
                      <div v-if="part.note" style="font-size:11px;color:var(--faint);margin-top:3px">{{ part.note }}</div>
                    </div>
                    <a v-if="part.search_url" :href="part.search_url" target="_blank" rel="noopener"
                       class="btn btn-ghost" style="font-size:12px;padding:7px 12px;white-space:nowrap;flex-shrink:0" @click.stop>
                      Найти на Авито
                      <svg viewBox="0 0 24 24" width="11" height="11" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
                    </a>
                  </div>
                </div>
              </div>

            </div>
          </div>

          <!-- ЧЕКЛИСТ ОСМОТРА -->
          <div v-if="checklistGroups.length" class="panel hud" style="margin-bottom:16px">
            <div class="panel-h">
              <svg class="ico" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
              <h2>Чеклист осмотра</h2>
            </div>
            <div class="panel-b">
              <div v-for="grp in checklistGroups" :key="grp.group" class="checklist-group">
                <div class="checklist-group-title">{{ grp.group }}</div>
                <div
                  v-for="item in grp.items"
                  :key="item._idx"
                  class="checklist-item"
                  :class="{ 'checklist-item--done': checkedItems[item._idx] }"
                  @click="toggleCheck(item._idx)"
                >
                  <div class="checklist-check-box">
                    <svg v-if="checkedItems[item._idx]" viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                  </div>
                  <div style="flex:1;min-width:0">
                    <div style="font-size:14px;font-weight:500;color:var(--fg)">{{ item.title || item.item }}</div>
                  </div>
                  <span :class="priorityBadgeClass(item.priority)">{{ priorityLabel(item.priority) }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- RECOMMENDATIONS -->
          <div v-if="recommendations.length" class="panel hud">
            <div class="panel-h">
              <svg class="ico" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 11 12 14 22 4"/><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11"/></svg>
              <h2>Рекомендации</h2>
            </div>
            <div class="panel-b">
              <div v-for="(rec, i) in recommendations" :key="i" class="rec-row">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--cyan)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="9 18 15 12 9 6"/></svg>
                <span>{{ rec }}</span>
              </div>
            </div>
          </div>

          <!-- POST-INSPECTION NOTES -->
          <div class="panel hud" style="margin-top:16px">
            <div class="panel-h">📋 <h2>Заметки после осмотра</h2></div>
            <div class="panel-b">
              <p style="color:var(--muted);font-size:14px;margin-bottom:12px">Что обнаружили при очном осмотре</p>
              <textarea v-model="postNotes" class="form-inp" rows="4" placeholder="Опишите дефекты..." style="width:100%;background:rgba(8,14,32,.6);border:1px solid var(--line2);border-radius:9px;color:var(--fg);padding:10px 12px;font-family:inherit;font-size:14px;outline:none;transition:border-color .18s;resize:vertical"></textarea>
              <div v-if="postNotesSaved" style="color:var(--safe);font-size:13px;margin-top:8px">✓ Сохранено</div>
              <button class="btn btn-primary" style="margin-top:12px" @click="savePostNotes" :disabled="postNotesSaving">
                {{ postNotesSaving ? 'Сохранение...' : 'Сохранить заметки' }}
              </button>
            </div>
          </div>

        </template>
      </main>

      <!-- ASIDE -->
      <aside class="report-aside">
        <div class="panel hud">
          <div class="verdict-top" :style="{ background: verdictInfo.gradient }">
            <div class="vstatus" :class="verdictInfo.cls" :style="{ color: verdictInfo.color }">
              <svg v-if="verdictInfo.icon === 'check'" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>
              <svg v-else-if="verdictInfo.icon === 'warn'" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>
              <svg v-else-if="verdictInfo.icon === 'x'" viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              <svg v-else viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
              {{ verdictInfo.label }}
            </div>
            <div class="vsub">{{ carTitle(inspection) }}</div>

            <!-- GAUGE -->
            <div v-if="riskScore != null" class="gauge">
              <svg width="120" height="120" viewBox="0 0 120 120">
                <circle cx="60" cy="60" r="48" fill="none" stroke="rgba(255,255,255,.08)" stroke-width="10"/>
                <circle
                  cx="60" cy="60" r="48" fill="none"
                  :stroke="verdictInfo.color"
                  stroke-width="10"
                  stroke-linecap="round"
                  stroke-dasharray="301.6"
                  :stroke-dashoffset="301.6 - 301.6 * (riskScore / 100)"
                  transform="rotate(-90 60 60)"
                  style="transition:stroke-dashoffset .6s ease"
                />
              </svg>
              <div class="gauge__center">
                <b :style="{ color: verdictInfo.color }">{{ riskScore }}%</b>
                <span>risk score</span>
              </div>
            </div>
          </div>

          <div class="panel-b">
            <div v-if="repairRange" class="kv kv--accent">
              <span class="k">Ремонт</span>
              <span class="v">{{ repairRange }}</span>
            </div>
            <div v-if="inspection.price_rub" class="kv">
              <span class="k">Цена</span>
              <span class="v">{{ fmt(inspection.price_rub) }} ₽</span>
            </div>
            <div v-if="inspection.mileage_km" class="kv">
              <span class="k">Пробег</span>
              <span class="v">{{ fmt(inspection.mileage_km) }} км</span>
            </div>
            <div v-if="p1Count" class="kv">
              <span class="k">Высокий риск</span>
              <span class="v" style="color:var(--risk)">{{ p1Count }}</span>
            </div>
            <div v-if="inspection.year" class="kv">
              <span class="k">Год</span>
              <span class="v">{{ inspection.year }}</span>
            </div>

            <div class="act-row">
              <button class="btn btn-ghost act-half" onclick="window.print()">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 6 2 18 2 18 9"/><path d="M6 18H4a2 2 0 01-2-2v-5a2 2 0 012-2h16a2 2 0 012 2v5a2 2 0 01-2 2h-2"/><rect x="6" y="14" width="12" height="8"/></svg>
                Сохранить
              </button>
              <button
                class="btn btn-ghost act-half"
                @click="() => navigator.share ? navigator.share({ title: carTitle(inspection), url: window.location.href }) : navigator.clipboard.writeText(window.location.href)"
              >
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="18" cy="5" r="3"/><circle cx="6" cy="12" r="3"/><circle cx="18" cy="19" r="3"/><line x1="8.59" y1="13.51" x2="15.42" y2="17.49"/><line x1="15.41" y1="6.51" x2="8.59" y2="10.49"/></svg>
                Поделиться
              </button>
            </div>

            <a
              v-if="inspection.listing_url"
              :href="inspection.listing_url"
              target="_blank"
              rel="noopener"
              class="btn btn-primary"
              style="width:100%;margin-top:8px;justify-content:center;font-size:13px;display:flex"
            >
              Открыть объявление
              <svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="margin-left:4px"><path d="M18 13v6a2 2 0 01-2 2H5a2 2 0 01-2-2V8a2 2 0 012-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
            </a>
          </div>
        </div>
      </aside>
    </div>
  </div>

  <footer class="footer">
    <div class="wrap"><div class="copy">© 2026 ПОДКАПОТ</div></div>
  </footer>
</template>
