<script setup>
import { reactive } from "vue";

const emit = defineEmits(["submit"]);

const form = reactive({
  listing_url: "",
  listing_source: "auto",
  photos_urls_raw: "",
  photo_note: "",
  brand: "Toyota",
  model: "Camry",
  year: 2020,
  mileage_km: 83000,
  price_rub: 2450000,
  vin: "",
  user_preferences: "Ищу максимально ликвидный вариант с адекватной стоимостью владения."
});

function detectSourceFromUrl(url) {
  const lowered = String(url || "").toLowerCase();
  if (lowered.includes("avito.ru")) return "avito";
  if (lowered.includes("auto.drom.ru") || lowered.includes("drom.ru")) return "drom";
  if (lowered.includes("auto.ru")) return "auto_ru";
  return "generic";
}

function parsePhotoUrls(raw) {
  if (!raw || typeof raw !== "string") return [];
  const seen = new Set();
  const urls = [];
  for (const chunk of raw.split(/[\n,;]/)) {
    const value = chunk.trim();
    if (!value) continue;
    if (!/^https?:\/\//i.test(value)) continue;
    if (seen.has(value)) continue;
    seen.add(value);
    urls.push(value);
  }
  return urls;
}

function submit() {
  const photoUrls = parsePhotoUrls(form.photos_urls_raw);
  const detectedSource = detectSourceFromUrl(form.listing_url);
  const source = form.listing_source === "auto" ? detectedSource : form.listing_source;
  emit("submit", {
    listing_url: form.listing_url || null,
    vehicle: {
      brand: form.brand || null,
      model: form.model || null,
      year: Number(form.year) || null,
      mileage_km: Number(form.mileage_km) || null,
      price_rub: Number(form.price_rub) || null,
      vin: form.vin || null
    },
    user_preferences: form.user_preferences,
    photos_metadata: photoUrls.map((url, index) => ({
      photo_url: url,
      zone: null,
      note: form.photo_note?.trim() ? `${form.photo_note.trim()} · фото ${index + 1}` : null
    })),
    require_avito_parse: Boolean(form.listing_url) && source === "avito"
  });
}
</script>

<template>
  <section class="glass-block" data-reveal>
    <div class="section-head">
      <h2>
        <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" style="flex:none"><path d="M14.5 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V7.5L14.5 2z"/><circle cx="10" cy="13" r="2"/><path d="M12 19l3.5-3.5M12 7h2"/></svg>
        Новая проверка
      </h2>
      <span class="badge--gradient-blue">Аналитический инструмент</span>
    </div>
    <p class="section-copy" style="margin-top: 4px;">
      Запустите анализ по ссылке объявления (Avito, Drom, Auto.ru) или вручную по параметрам автомобиля.
    </p>

    <form class="composer-wrap" @submit.prevent="submit" style="margin-top: 24px;">

      <!-- Источник -->
      <div class="composer-section">
        <div class="composer-section__label">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M10 13a5 5 0 007.54.54l3-3a5 5 0 00-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 00-7.54-.54l-3 3a5 5 0 007.07 7.07l1.71-1.71"/></svg>
          Источник объявления
        </div>
        <div class="composer-grid">
          <label class="wide">
            Ссылка на объявление
            <input
              v-model="form.listing_url"
              type="url"
              placeholder="https://www.avito.ru/... или https://auto.drom.ru/..."
            />
          </label>
          <label>
            Источник
            <select v-model="form.listing_source">
              <option value="auto">Определить автоматически</option>
              <option value="avito">Avito — строгий парсинг</option>
              <option value="drom">Drom</option>
              <option value="auto_ru">Auto.ru</option>
              <option value="generic">Другая площадка</option>
            </select>
          </label>
          <label style="align-content: end;">
            <span style="color: var(--text-muted); font-size: 0.78rem; line-height: 1.4;">
              Источник определяется автоматически по URL.
              <br>Переопределите вручную при необходимости.
            </span>
          </label>
        </div>
      </div>

      <!-- Автомобиль -->
      <div class="composer-section">
        <div class="composer-section__label">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M5 17H3a2 2 0 01-2-2V5a2 2 0 012-2h11a2 2 0 012 2v3"/><rect x="9" y="11" width="14" height="10" rx="2"/><circle cx="12" cy="21" r="1"/><circle cx="20" cy="21" r="1"/></svg>
          Параметры автомобиля
        </div>
        <div class="composer-grid">
          <label>
            Марка
            <input v-model="form.brand" placeholder="Toyota" />
          </label>
          <label>
            Модель
            <input v-model="form.model" placeholder="Camry" />
          </label>
          <label>
            Год выпуска
            <input v-model.number="form.year" type="number" min="1980" max="2030" />
          </label>
          <label>
            Пробег, км
            <input v-model.number="form.mileage_km" type="number" min="0" />
          </label>
          <label>
            Цена продавца, ₽
            <input v-model.number="form.price_rub" type="number" min="0" />
          </label>
          <label>
            VIN
            <input v-model="form.vin" placeholder="Опционально" style="font-family: var(--font-mono); letter-spacing: 0.06em;" />
          </label>
        </div>
      </div>

      <!-- Детали -->
      <div class="composer-section">
        <div class="composer-section__label">
          <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="9" y="2" width="6" height="4" rx="1"/><path d="M5 4h-1a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V6a2 2 0 00-2-2h-1"/><path d="M9 12h6M9 16h4"/></svg>
          Детали и фотоматериалы
        </div>
        <div class="composer-grid">
          <label class="wide">
            Цель и предпочтения покупателя
            <textarea v-model="form.user_preferences" rows="3" placeholder="Ищу ликвидный вариант с адекватной стоимостью владения..." />
          </label>
          <label class="wide">
            URL фотографий автомобиля
            <textarea
              v-model="form.photos_urls_raw"
              rows="3"
              placeholder="https://site.ru/car-1.jpg&#10;https://site.ru/car-2.jpg"
            />
            <small class="section-copy" style="font-size: 0.76rem; margin-top: 2px;">
              По одной ссылке на строку. Без фото — отчёт формируется без photo-findings.
            </small>
          </label>
          <label class="wide">
            Комментарий к фото
            <input
              v-model="form.photo_note"
              placeholder="Например: особое внимание на зазоры, ржавчину, состояние салона"
            />
          </label>
        </div>
      </div>

      <button class="cta cta--wide cta--gradient" type="submit">
        <span>Запустить анализ</span>
        <span style="font-size: 1.2rem; line-height: 1; font-weight: 400;">→</span>
      </button>

    </form>
  </section>
</template>
