<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { checkAuth, fetchCurrentUser } from '../api/inspectionApi'

const router = useRouter()
const menuOpen = ref(false)
const listingUrl = ref('')
const manualForm = ref({ brand: '', model: '', year: '', mileage: '', price: '', vin: '' })
const isLoggedIn = ref(false)
const userName = ref('')

const faqItems = ref([
  { q: 'Откуда берутся данные о рисках?', a: 'Система анализирует объявление, фотографии и типовые слабые места модели по базе знаний. Вероятность каждого риска рассчитывается на основе пробега, возраста и визуальных признаков.', open: true },
  { q: 'Работает ли сервис с Drom и Auto.ru?', a: 'Да. Вставь ссылку — парсер автоматически определит площадку и извлечёт параметры объявления. Поддерживаются Avito, Drom, Auto.ru и ряд других площадок.', open: false },
  { q: 'Нужен ли VIN для анализа?', a: 'VIN необязателен. Базовый анализ работает по марке, модели, году и пробегу. Если VIN указан — сервис дополнительно проверяет историю по открытым базам.', open: false },
  { q: 'За сколько делается анализ?', a: 'Обычно 20–40 секунд. Если добавлены фото, время может быть немного больше из-за обработки изображений.', open: false },
  { q: 'Это замена выездному осмотру?', a: 'Нет. Сервис помогает подготовиться: узнать риски ДО встречи и прийти с готовым чеклистом. Итоговое решение — за живым осмотром.', open: false },
])

function toggleFaq(idx) {
  faqItems.value[idx].open = !faqItems.value[idx].open
}

function toggleMenu() {
  menuOpen.value = !menuOpen.value
}

function goAnalyze() {
  // Первая проверка доступна без регистрации (гостевая сессия создаётся
  // роутер-гардом), поэтому ведём в /app/new независимо от логина.
  const url = listingUrl.value.trim()
  if (url) {
    router.push({ path: '/app/new', query: { url } })
  } else {
    router.push('/app/new')
  }
}

onMounted(async () => {
  try { const u = await fetchCurrentUser(); isLoggedIn.value = true; userName.value = u.email?.split('@')[0] || '' } catch {}

  const io = new IntersectionObserver((es) => {
    es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('reveal'); io.unobserve(e.target) } })
  }, { threshold: 0.12 })
  document.querySelectorAll('[data-reveal]').forEach(el => io.observe(el))
})
</script>

<template>
  <!-- NAV -->
  <header class="nav">
    <div class="wrap">
      <router-link class="logo" :to="isLoggedIn ? '/app' : '/'">
        <svg width="32" height="32" viewBox="0 0 32 32" fill="none" aria-hidden="true">
          <rect width="32" height="32" rx="8" fill="#3fd0ff" fill-opacity=".15"/>
          <path d="M16 6 8 22h16z" stroke="#3fd0ff" stroke-width="1.8" stroke-linejoin="round" fill="none"/>
          <circle cx="16" cy="17" r="2" fill="#3fd0ff"/>
        </svg>
        ПОДКАПОТ
      </router-link>
      <nav class="nav-links" :class="{ open: menuOpen }">
        <router-link to="/" class="active">Главная</router-link>
        <a href="#how">Как работает</a>
        <a href="#result">Результат</a>
        <a href="#faq">FAQ</a>
        <router-link v-if="isLoggedIn" to="/app" class="btn btn-ghost" style="padding:8px 16px;font-size:13px">Кабинет</router-link>
        <router-link v-else to="/login" class="btn btn-ghost" style="padding:8px 16px;font-size:13px">Войти</router-link>
      </nav>
      <router-link class="btn btn-primary" to="/app/new">
        <svg class="ic-svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13 2 4.5 13.5H11l-1 8.5L19.5 10H13z"/></svg>
        Проверить авто
      </router-link>
      <button class="menu-btn" @click="toggleMenu">≡</button>
    </div>
  </header>

  <!-- HERO -->
  <section class="hero wrap">
    <div class="hero-grid">
      <div>
        <div class="hello">{{ isLoggedIn && userName ? 'ПРИВЕТ, ' + userName.toUpperCase() : 'HELLO, DRIVER' }}</div>
        <h1>Проверь тачку <span class="lite">до встречи</span> с продавцом</h1>
        <p class="sub">Кидаешь ссылку на объявление — система находит риски, считает ремонт и собирает персональный чеклист осмотра. За 30 секунд, без сюрпризов.</p>

        <div class="panel hud inputcard">
          <div class="panel-b">
            <div class="input-row">
              <label class="field">
                <span class="pfx">
                  <svg class="ic-svg" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 13a5 5 0 0 0 7 0l3-3a5 5 0 0 0-7-7l-1 1"/><path d="M15 11a5 5 0 0 0-7 0l-3 3a5 5 0 0 0 7 7l1-1"/></svg>
                </span>
                <input v-model="listingUrl" placeholder="Ссылка на объявление (Avito, Auto.ru, Drom…)">
              </label>
              <button class="btn btn-primary btn-block-h" @click="goAnalyze">Анализировать →</button>
            </div>
            <div class="or">— или заполни вручную —</div>
            <div class="manual">
              <input v-model="manualForm.brand" placeholder="Марка">
              <input v-model="manualForm.model" placeholder="Модель">
              <input v-model="manualForm.year" placeholder="Год">
              <input v-model="manualForm.mileage" placeholder="Пробег">
              <input v-model="manualForm.price" placeholder="Цена">
              <input v-model="manualForm.vin" placeholder="VIN">
            </div>
          </div>
        </div>

        <div class="hero-tags" style="margin-top:14px">
          <span class="htag"><span class="led"></span> Источник: Avito</span>
          <span class="htag">
            <svg class="ic-svg" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>
            Анализ 10–30 сек
          </span>
          <span class="htag"><span class="led"></span> Парсинг: успешно</span>
          <span class="htag">
            <svg class="ic-svg" viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13 2 4.5 13.5H11l-1 8.5L19.5 10H13z"/></svg>
            120+ пунктов проверки
          </span>
        </div>
      </div>

      <div class="hero-art">
        <div class="glowimg"></div>
        <img src="/img/hero-main.png" alt="Авто с HUD-диагностикой" onerror="this.style.display='none'">
      </div>
    </div>
  </section>

  <!-- STATS -->
  <div class="wrap">
    <div class="stats">
      <div class="panel hud stat"><b>30с</b><span>СРЕДНИЙ АНАЛИЗ</span></div>
      <div class="panel hud stat"><b>120+</b><span>ПУНКТОВ ПРОВЕРКИ</span></div>
      <div class="panel hud stat"><b>40К ₽</b><span>СРЕДНЯЯ ЭКОНОМИЯ</span></div>
      <div class="panel hud stat"><b>2</b><span>РЫНКА: ПОКУПКА · ПЕРЕПРОДАЖА</span></div>
    </div>
  </div>

  <!-- HOW -->
  <section class="section wrap" id="how">
    <div class="section-head">
      <div class="eyebrow">SETUP</div>
      <h2 class="h-sec">Как это работает</h2>
      <p class="lead">Четыре шага от ссылки до решения «брать или бежать».</p>
    </div>
    <div class="steps">
      <div class="panel hud step" data-reveal><div class="n">01</div><h3>Ссылка или вручную</h3><p>Вставь объявление с любой площадки или заполни марку, год, пробег и цену сам.</p></div>
      <div class="panel hud step" data-reveal><div class="n">02</div><h3>Фото и дефекты</h3><p>Добавь фото и то, что заметил по объявлению или со слов продавца.</p></div>
      <div class="panel hud step" data-reveal><div class="n">03</div><h3>Риски и чеклист</h3><p>Получи слабые места модели и персональный чеклист для очного осмотра.</p></div>
      <div class="panel hud step" data-reveal><div class="n">04</div><h3>Смета и вердикт</h3><p>Узнай стоимость ремонта, выгоду перепродажи и итог: брать / проверять / отказ.</p></div>
    </div>
  </section>

  <!-- AUDIENCES -->
  <section class="section wrap">
    <div class="section-head">
      <div class="eyebrow">ДЛЯ КОГО</div>
      <h2 class="h-sec">Две аудитории — одна цель</h2>
    </div>
    <div class="aud">
      <div class="panel hud" data-reveal>
        <div class="ic">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3 5 6v5c0 4.4 3 8.2 7 9.5 4-1.3 7-5.1 7-9.5V6z"/><path d="m9 12 2 2 4-4"/></svg>
        </div>
        <h3>Покупателю</h3>
        <p>Безопасно купить подержанное авто и не попасть на скрытый ремонт.</p>
        <ul>
          <li>Видишь риски ещё до встречи с продавцом</li>
          <li>Идёшь на осмотр с готовым чеклистом</li>
          <li>Знаешь реальную стоимость владения</li>
        </ul>
      </div>
      <div class="panel hud" data-reveal>
        <div class="ic">
          <svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 18V9l5-4 5 3 6-3v9"/><path d="M4 18l5-4 5 3 6-3"/></svg>
        </div>
        <h3>Перекупу</h3>
        <p>Быстро оценить риски, объём вложений и потенциальную прибыль по сделке.</p>
        <ul>
          <li>Считаешь экономику за 30 секунд</li>
          <li>Сравниваешь несколько вариантов разом</li>
          <li>Отсеиваешь убыточные сделки сразу</li>
        </ul>
      </div>
    </div>
  </section>

  <!-- WHAT YOU GET -->
  <section class="section wrap" id="result">
    <div class="section-head">
      <div class="eyebrow">РЕЗУЛЬТАТ</div>
      <h2 class="h-sec">Что выдаёт сервис</h2>
      <p class="lead">Структурированный отчёт, в котором сразу видно: риски, деньги, что менять и где купить.</p>
    </div>
    <div class="steps">
      <router-link class="panel hud step" data-reveal to="/app/new">
        <div class="n n-ic"><svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/></svg></div>
        <h3>Отчёт по авто</h3>
        <p>Вердикт, risk score, риски с доказательствами и смета ремонта.</p>
      </router-link>
      <router-link class="panel hud step" data-reveal to="/app/new">
        <div class="n n-ic"><svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="3.2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/></svg></div>
        <h3>Запчасти и ссылки</h3>
        <p>Что менять, наличие и ссылки на предложения с ценами.</p>
      </router-link>
      <router-link class="panel hud step" data-reveal to="/app/new">
        <div class="n n-ic"><svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M9 11l2 2 4-4"/><rect x="3" y="4" width="18" height="16" rx="2"/></svg></div>
        <h3>Чеклист осмотра</h3>
        <p>Что и как проверять лично: визуально, на тест-драйве, по OBD-II.</p>
      </router-link>
      <router-link class="panel hud step" data-reveal to="/app">
        <div class="n n-ic"><svg viewBox="0 0 24 24" width="26" height="26" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M7 4 3 8l4 4"/><path d="M3 8h13"/><path d="m17 20 4-4-4-4"/><path d="M21 16H8"/></svg></div>
        <h3>История и сравнение</h3>
        <p>Все прошлые проверки и сравнение вариантов между собой.</p>
      </router-link>
    </div>
  </section>

  <!-- FAQ -->
  <section class="section wrap" id="faq">
    <div class="section-head">
      <div class="eyebrow">FAQ</div>
      <h2 class="h-sec">Частые вопросы</h2>
    </div>
    <div class="faq">
      <div
        v-for="(item, i) in faqItems"
        :key="i"
        class="acc-item"
        :class="{ open: item.open }"
      >
        <div class="acc-head" @click="toggleFaq(i)">
          <span class="ico">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 8v4M12 16h.01"/></svg>
          </span>
          {{ item.q }}
          <span class="chev">▾</span>
        </div>
        <div class="acc-body" :style="item.open ? 'max-height:400px' : ''">
          <div class="inner">{{ item.a }}</div>
        </div>
      </div>
    </div>
  </section>

  <!-- CTA -->
  <section class="section wrap" style="text-align:center">
    <div class="eyebrow" style="justify-content:center;display:flex">ГОТОВ</div>
    <h2 class="h-sec" style="margin-bottom:16px">Проверь авто прямо сейчас</h2>
    <p class="lead" style="margin:0 auto 30px">Первые 3 проверки бесплатно. Без кредиток, без сюрпризов.</p>
    <div style="display:flex;gap:12px;justify-content:center;flex-wrap:wrap">
      <template v-if="isLoggedIn">
        <router-link class="btn btn-primary btn-lg" to="/app/new">Проверить авто</router-link>
        <router-link class="btn btn-ghost btn-lg" to="/app">Мои анализы</router-link>
      </template>
      <template v-else>
        <router-link class="btn btn-primary btn-lg" to="/register">Создать аккаунт</router-link>
        <router-link class="btn btn-ghost btn-lg" to="/login">Войти</router-link>
      </template>
    </div>
  </section>

  <!-- FOOTER -->
  <footer class="footer">
    <div class="wrap">
      <div class="cols">
        <div>
          <div class="logo" style="margin-bottom:12px;font-size:17px">ПОДКАПОТ</div>
          <p style="font-size:13px;color:var(--faint);max-width:260px">Интеллектуальный анализ подержанных авто перед покупкой.</p>
        </div>
        <div>
          <h4>Сервис</h4>
          <router-link to="/app/new">Новая проверка</router-link>
          <router-link to="/app">Кабинет</router-link>
          <a href="#how">Как работает</a>
        </div>
        <div>
          <h4>Аккаунт</h4>
          <template v-if="isLoggedIn">
            <router-link to="/app">Мой кабинет</router-link>
            <router-link to="/app/new">Новая проверка</router-link>
          </template>
          <template v-else>
            <router-link to="/login">Войти</router-link>
            <router-link to="/register">Регистрация</router-link>
          </template>
        </div>
        <div>
          <h4>Поддержка</h4>
          <a href="#faq">FAQ</a>
          <router-link to="/contacts">Контакты</router-link>
        </div>
        <div>
          <h4>Документы</h4>
          <router-link to="/oferta">Публичная оферта</router-link>
          <router-link to="/privacy">Политика конфиденциальности</router-link>
        </div>
      </div>
      <div class="copy">© 2026 ПОДКАПОТ · Проверяй авто до встречи с продавцом.</div>
    </div>
  </footer>
</template>
