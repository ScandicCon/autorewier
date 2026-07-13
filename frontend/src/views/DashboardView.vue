<script setup>
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { fetchInspectionsHistory, fetchCurrentUser, logoutUser, subscribePro, getReportPacks, buyReportPack } from '../api/inspectionApi'

const router = useRouter()
const loading = ref(true)
const history = ref([])
const currentUser = ref(null)
const error = ref('')
const activeTab = ref('checks')
const goingPro = ref(false)
const payError = ref('')
const packsInfo = ref(null)
const buyingPack = ref(0)

onMounted(async () => {
  try {
    const [user, items] = await Promise.all([fetchCurrentUser(), fetchInspectionsHistory()])
    currentUser.value = user
    history.value = items
    getReportPacks().then((p) => { packsInfo.value = p }).catch(() => {})
  } catch (e) {
    if (e.status === 401) router.push('/login')
    else error.value = e.message || 'Не удалось загрузить данные'
  } finally {
    loading.value = false
  }
})

async function handleLogout() {
  try { await logoutUser() } catch {}
  router.push('/login')
}

async function goPro() {
  goingPro.value = true
  payError.value = ''
  try {
    const { confirmation_url } = await subscribePro()
    if (confirmation_url) {
      window.location.href = confirmation_url
    } else {
      payError.value = 'Не удалось получить ссылку на оплату. Попробуйте позже.'
      goingPro.value = false
    }
  } catch (e) {
    payError.value = e.status === 503
      ? 'Оплата временно недоступна. Попробуйте позже.'
      : (e.message || 'Не удалось начать оплату. Попробуйте позже.')
    goingPro.value = false
  }
}

async function buyPack(size) {
  buyingPack.value = size
  payError.value = ''
  try {
    const { confirmation_url } = await buyReportPack(size)
    if (confirmation_url) {
      window.location.href = confirmation_url
    } else {
      payError.value = 'Не удалось получить ссылку на оплату.'
      buyingPack.value = 0
    }
  } catch (e) {
    payError.value = e.message || 'Не удалось купить пакет.'
    buyingPack.value = 0
  }
}

// verdict: "worth_looking" | "caution" | "skip"
function verdictPill(verdict) {
  if (verdict === 'worth_looking') return { label: 'Рекомендуем', cls: 'safe' }
  if (verdict === 'caution') return { label: 'Осторожно', cls: 'cau' }
  if (verdict === 'skip') return { label: 'Отказ', cls: 'crit' }
  return null
}

// stage: "draft" | "pre_inspection" | "post_inspection"
function statusLabel(stage) {
  if (stage === 'pre_inspection' || stage === 'post_inspection') return 'Готово'
  if (stage === 'draft') return 'Анализ…'
  return 'Ожидание'
}

function carTitle(item) {
  const parts = [item.brand, item.model, item.year].filter(Boolean)
  return parts.length ? parts.join(' ') : 'Автомобиль'
}

function carInitials(item) {
  const b = (item.brand || '?')[0]
  const m = (item.model || '?')[0]
  return (b + m).toUpperCase()
}

function fmt(n) {
  if (n == null) return '—'
  return Number(n).toLocaleString('ru-RU')
}
</script>

<template>
  <!-- NAV -->
  <header class="nav">
    <div class="wrap">
      <router-link class="logo" to="/app"><img class="logo-ico" src="/img/logo-mark.png" alt="" aria-hidden="true">ПОДКАПОТ</router-link>
      <nav class="nav-links">
        <router-link to="/app">Проверки</router-link>
      </nav>
      <div style="display:flex;align-items:center;gap:12px">
        <router-link to="/" style="color:var(--muted);font-size:13px;text-decoration:none;display:flex;align-items:center;gap:4px">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z"/><polyline points="9 22 9 12 15 12 15 22"/></svg>
          На главную
        </router-link>
        <span v-if="currentUser" style="color:var(--muted);font-size:13px">{{ currentUser.email }}</span>
        <button class="btn btn-ghost" style="font-size:13px;padding:6px 14px" @click="handleLogout">Выйти</button>
      </div>
    </div>
  </header>

  <div class="wrap" style="padding-top:32px;padding-bottom:60px">

    <!-- HERO -->
    <div class="pbanner" style="margin-bottom:28px">
      <div>
        <div class="carline">// МОЙ ГАРАЖ</div>
        <h1>Мои проверки</h1>
        <p>История анализов — все автомобили на одном экране</p>
      </div>
      <div style="display:flex;align-items:center;gap:12px">
        <img src="/img/empty.png" alt="" style="width:140px;opacity:.7;display:block" onerror="this.style.display='none'">
        <router-link to="/app/new" class="btn btn-primary" style="white-space:nowrap">
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
          Новая проверка
        </router-link>
      </div>
    </div>

    <!-- TAB BAR -->
    <div class="tab-bar" style="margin-bottom:24px">
      <button class="tab-btn" :class="{ active: activeTab === 'checks' }" @click="activeTab = 'checks'">Проверки</button>
      <button class="tab-btn" :class="{ active: activeTab === 'subscription' }" @click="activeTab = 'subscription'">Подписка</button>
    </div>

    <!-- TAB: CHECKS -->
    <template v-if="activeTab === 'checks'">

      <!-- ERROR -->
      <div v-if="error" class="auth-error-msg" style="margin-bottom:20px">{{ error }}</div>

      <!-- LOADING (скелетон с пульсацией — холодный старт API может длиться ~4 сек) -->
      <div v-if="loading">
        <div v-for="i in 3" :key="i" class="rep-card" style="margin-bottom:12px;pointer-events:none;animation:pulse 1.4s ease-in-out infinite">
          <div class="rep-thumb" style="background:rgba(63,208,255,.04)"></div>
          <div class="rep-main">
            <div style="height:14px;width:180px;background:var(--line);border-radius:6px;margin-bottom:8px"></div>
            <div style="height:11px;width:120px;background:var(--line);border-radius:6px"></div>
          </div>
        </div>
      </div>

      <!-- EMPTY -->
      <div v-else-if="!history.length" class="panel hud" style="text-align:center;padding:60px 24px">
        <img src="/img/empty.png" alt="" style="width:120px;opacity:.6;margin:0 auto 20px;display:block" onerror="this.style.display='none'">
        <p style="color:var(--muted);margin-bottom:20px">У вас пока нет проверок.<br>Начните с первого автомобиля.</p>
        <router-link to="/app/new" class="btn btn-primary">Начать первую проверку</router-link>
      </div>

      <!-- LIST -->
      <div v-else class="rep-list">
        <router-link
          v-for="item in history"
          :key="item.id"
          :to="`/app/inspection/${item.id}`"
          class="rep-card"
          style="text-decoration:none"
        >
          <!-- THUMBNAIL -->
          <div class="rep-thumb">
            <img
              v-if="item.photos_metadata?.length && item.photos_metadata[0]?.photo_url"
              :src="item.photos_metadata[0].photo_url"
              :alt="carTitle(item)"
              style="width:100%;height:100%;object-fit:cover;border-radius:inherit"
              onerror="this.style.display='none'"
            >
            <span v-else style="font-family:'Unbounded',sans-serif;font-size:13px;font-weight:700;color:var(--cyan)">{{ carInitials(item) }}</span>
          </div>

          <!-- INFO -->
          <div class="rep-main" style="flex:1;min-width:0">
            <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:4px">
              <span style="font-family:'Unbounded',sans-serif;font-size:14px;font-weight:700;color:var(--fg)">{{ carTitle(item) }}</span>
              <span
                v-if="verdictPill(item.verdict)"
                class="verdict-pill"
                :class="verdictPill(item.verdict).cls"
              >{{ verdictPill(item.verdict).label }}</span>
              <span v-else class="verdict-pill">{{ statusLabel(item.stage) }}</span>
            </div>
            <div style="display:flex;gap:16px;flex-wrap:wrap;align-items:center">
              <span v-if="item.price_rub" style="color:var(--muted);font-size:13px">{{ fmt(item.price_rub) }} ₽</span>
              <span v-if="item.mileage_km" style="color:var(--muted);font-size:13px">{{ fmt(item.mileage_km) }} км</span>
              <span style="color:var(--faint);font-size:12px">{{ new Date(item.created_at).toLocaleDateString('ru-RU') }}</span>
            </div>
            <!-- RISK BAR -->
            <div v-if="item.pre_report?.risk_score != null" style="margin-top:8px;max-width:200px">
              <div style="height:4px;border-radius:2px;background:var(--line);overflow:hidden">
                <div :style="{
                  height:'100%',
                  width: item.pre_report.risk_score + '%',
                  background: item.pre_report.risk_score > 66 ? 'var(--risk)' : item.pre_report.risk_score > 33 ? 'var(--cau)' : 'var(--safe)',
                  transition:'width .4s ease'
                }"></div>
              </div>
              <span style="font-size:11px;color:var(--faint);margin-top:3px;display:block">risk {{ item.pre_report.risk_score }}%</span>
            </div>
          </div>

          <!-- ARROW -->
          <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="var(--line2)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex-shrink:0"><path d="M9 18l6-6-6-6"/></svg>
        </router-link>
      </div>

    </template>

    <!-- TAB: SUBSCRIPTION -->
    <template v-if="activeTab === 'subscription'">
      <!-- BG art -->
      <div style="position:relative;overflow:hidden;border-radius:16px;margin-bottom:24px">
        <img src="/img/compare-cars.png" alt="" style="position:absolute;right:-20px;bottom:-20px;width:320px;opacity:.12;pointer-events:none;filter:blur(6px) saturate(.5)">

        <!-- CURRENT PLAN -->
        <div class="panel hud" style="position:relative;z-index:1;display:grid;grid-template-columns:1fr auto;gap:24px;align-items:center;padding:32px;margin-bottom:0">
          <div>
            <div class="carline" style="margin-bottom:8px">// ТЕКУЩИЙ ТАРИФ</div>
            <h2 style="font-family:'Unbounded',sans-serif;font-size:24px;margin-bottom:8px">Бесплатный</h2>
            <p style="color:var(--muted);margin-bottom:20px;font-size:14px">3 проверки в месяц · базовый анализ</p>
            <div style="display:flex;gap:8px;flex-wrap:wrap">
              <span style="background:rgba(55,210,126,.12);color:var(--safe);border-radius:6px;padding:4px 10px;font-size:12px;font-weight:600">✓ Чеклист</span>
              <span style="background:rgba(55,210,126,.12);color:var(--safe);border-radius:6px;padding:4px 10px;font-size:12px;font-weight:600">✓ Смета</span>
              <span style="background:rgba(72,85,99,.2);color:var(--muted);border-radius:6px;padding:4px 10px;font-size:12px;font-weight:600">✗ Фото-анализ</span>
              <span style="background:rgba(72,85,99,.2);color:var(--muted);border-radius:6px;padding:4px 10px;font-size:12px;font-weight:600">✗ Неограниченно</span>
            </div>
          </div>
          <img src="/img/parts-links.png" alt="" style="width:140px;opacity:.6;border-radius:12px" onerror="this.style.display='none'">
        </div>
      </div>

      <!-- PRO CARD -->
      <div style="position:relative;overflow:hidden;border-radius:16px;border:1.5px solid rgba(63,208,255,.25);background:linear-gradient(135deg,rgba(63,208,255,.06),rgba(63,208,255,.02));padding:32px">
        <img src="/img/compare-cars.png" alt="" style="position:absolute;right:-40px;top:-30px;width:380px;opacity:.1;pointer-events:none;filter:blur(4px) saturate(.4)">
        <div style="position:relative;z-index:1;display:grid;grid-template-columns:1fr auto;gap:24px;align-items:start">
          <div>
            <div class="carline" style="margin-bottom:8px;color:var(--cyan)">// PRO ТАРИФ</div>
            <h2 style="font-family:'Unbounded',sans-serif;font-size:28px;margin-bottom:4px;color:var(--fg)">990 <span style="font-size:16px;color:var(--muted)">₽/мес</span></h2>
            <p style="color:var(--muted);margin-bottom:20px;font-size:14px">Полный анализ без ограничений</p>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:24px">
              <div style="display:flex;align-items:center;gap:8px;font-size:13px;color:var(--fg)">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--cyan)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                Неограниченные проверки
              </div>
              <div style="display:flex;align-items:center;gap:8px;font-size:13px;color:var(--fg)">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--cyan)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                Анализ фотографий ИИ
              </div>
              <div style="display:flex;align-items:center;gap:8px;font-size:13px;color:var(--fg)">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--cyan)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                Запчасти с ценами
              </div>
              <div style="display:flex;align-items:center;gap:8px;font-size:13px;color:var(--fg)">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--cyan)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                VIN + история авто
              </div>
              <div style="display:flex;align-items:center;gap:8px;font-size:13px;color:var(--fg)">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--cyan)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                Сравнение вариантов
              </div>
              <div style="display:flex;align-items:center;gap:8px;font-size:13px;color:var(--fg)">
                <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="var(--cyan)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
                Приоритетная поддержка
              </div>
            </div>
            <button class="btn btn-primary" style="font-size:15px;padding:12px 28px" :disabled="goingPro" @click="goPro">
              {{ goingPro ? 'Переходим к оплате…' : 'Перейти на Pro — 990 ₽/мес' }}
            </button>
            <p v-if="payError" style="margin-top:10px;color:#ff6b6b;font-size:13px">{{ payError }}</p>
          </div>
          <img src="/img/checklist-smiles.png" alt="" style="width:160px;opacity:.7;border-radius:12px;margin-top:8px" onerror="this.style.display='none'">
        </div>
      </div>

      <!-- ПАКЕТЫ VIN-ОТЧЁТОВ -->
      <div v-if="packsInfo && packsInfo.packs && packsInfo.packs.length" style="margin-top:24px;border-radius:16px;border:1.5px solid rgba(148,163,184,.18);padding:24px">
        <div class="carline" style="margin-bottom:6px">// VIN-ОТЧЁТЫ</div>
        <p style="color:var(--muted);font-size:13px;margin-bottom:6px">
          <template v-if="packsInfo.is_pro">Включено в Pro: {{ packsInfo.included_per_month }}/мес · осталось в этом месяце: {{ packsInfo.quota_left }}.</template>
          <template v-else>VIN-отчёты доступны на Pro или по пакетам.</template>
          Куплено сверх: {{ packsInfo.report_credits }}.
        </p>
        <p style="color:var(--muted);font-size:13px;margin-bottom:16px">Нужно больше отчётов — докупи пакет:</p>
        <div style="display:flex;flex-wrap:wrap;gap:10px">
          <button v-for="p in packsInfo.packs" :key="p.pack_size" class="btn btn-ghost"
                  :disabled="buyingPack === p.pack_size" @click="buyPack(p.pack_size)"
                  style="font-size:14px;padding:10px 18px">
            {{ buyingPack === p.pack_size ? 'Оплата…' : `${p.pack_size} отчётов — ${p.price_rub} ₽` }}
          </button>
        </div>
      </div>
    </template>

  </div>

  <footer class="footer">
    <div class="wrap"><div class="copy">© 2026 ПОДКАПОТ</div></div>
  </footer>
</template>
