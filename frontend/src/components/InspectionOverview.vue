<script setup>
import { computed } from "vue";

const props = defineProps({
  inspection: Object
});

const report = computed(() => props.inspection?.post_report || props.inspection?.pre_report || {});
const riskCards = computed(() => report.value?.risks || []);
const checklist = computed(() => report.value?.checklist || []);
const repairs = computed(() => report.value?.repair_lines || []);
const replacementSuggestions = computed(() => report.value?.replacement_suggestions || []);
const partBlocks = computed(() => report.value?.parts_pricing || props.inspection?.parts_pricing || []);
const legacyPhotoMetadata = computed(() => report.value?.photos_metadata || []);
const reportPhotoFindings = computed(
  () => report.value?.image_findings || report.value?.photo_findings || report.value?.findings || []
);

function normalizeText(value) {
  return String(value || "")
    .toLowerCase()
    .replace(/[^\p{L}\p{N}\s]/gu, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function tokenize(value) {
  return normalizeText(value)
    .split(" ")
    .filter((token) => token.length >= 4);
}

function formatRub(value) {
  if (!Number.isFinite(value)) {
    return null;
  }
  return new Intl.NumberFormat("ru-RU").format(value);
}

function toArray(value) {
  if (Array.isArray(value)) {
    return value
      .map((entry) => {
        if (typeof entry === "string") {
          return entry.trim();
        }
        if (entry && typeof entry === "object") {
          const candidate = entry.details || entry.signal || entry.value;
          return typeof candidate === "string" ? candidate : String(candidate || "");
        }
        return "";
      })
      .filter((entry) => typeof entry === "string" && entry.trim());
  }
  if (value && typeof value === "object") {
    const detail = value.details || value.signal || value.value;
    return typeof detail === "string" && detail.trim() ? [detail] : [];
  }
  if (typeof value === "string" && value.trim()) {
    return [value.trim()];
  }
  return [];
}

function firstDefined(...values) {
  for (const value of values) {
    if (value !== undefined && value !== null && value !== "") {
      return value;
    }
  }
  return null;
}

function sourceFromUrl(url) {
  const lowered = String(url || "").toLowerCase();
  if (!lowered) {
    return "Не указан";
  }
  if (lowered.includes("avito.ru")) {
    return "Avito";
  }
  if (lowered.includes("drom.ru")) {
    return "Drom";
  }
  if (lowered.includes("auto.ru")) {
    return "Auto.ru";
  }
  return "Другая площадка";
}

function normalizeSource(raw, fallbackUrl) {
  const lowered = String(raw || "").toLowerCase();
  if (lowered === "avito") { return "Avito"; }
  if (lowered.includes("avito.ru")) { return "Avito"; }
  if (lowered === "drom") { return "Drom"; }
  if (lowered.includes("drom.ru")) { return "Drom"; }
  if (lowered === "auto_ru" || lowered === "auto.ru") { return "Auto.ru"; }
  if (lowered.includes("auto.ru")) { return "Auto.ru"; }
  if (lowered === "youla") { return "Youla"; }
  if (lowered === "yandex_market") { return "Яндекс Маркет"; }
  if (lowered === "generic") { return sourceFromUrl(fallbackUrl); }
  if (lowered) { return raw; }
  return sourceFromUrl(fallbackUrl);
}

function reliabilityLabel(raw) {
  const lowered = String(raw || "").toLowerCase();
  if (["high", "ok", "verified", "trusted", "confirmed", "complete"].includes(lowered)) {
    return "Высокая достоверность";
  }
  if (["medium", "partial", "warning", "fallback"].includes(lowered)) {
    return "Средняя достоверность";
  }
  if (["low", "failed", "error"].includes(lowered)) {
    return "Низкая достоверность";
  }
  return "Достоверность не указана";
}

function offersFromBlock(block) {
  const sources = [
    { key: "avito_offers", source: "Avito" },
    { key: "drom_offers", source: "Drom" },
    { key: "auto_ru_offers", source: "Auto.ru" },
    { key: "offers", source: "Маркетплейс" },
    { key: "market_offers", source: "Маркетплейс" }
  ];
  const collected = [];
  for (const source of sources) {
    const sourceOffers = Array.isArray(block?.[source.key]) ? block[source.key] : [];
    for (const offer of sourceOffers) {
      collected.push({
        source: source.source,
        title: offer?.title || block?.part_name || "Лот",
        priceRub: offer?.price_rub,
        url: offer?.url || null
      });
    }
  }
  if (block?.search_url) {
    collected.push({
      source: "Поиск",
      title: block?.part_name || "Запчасть",
      priceRub: block?.estimate_median || block?.avito_median || block?.market_median || null,
      url: block.search_url
    });
  }
  return collected;
}

function isRepairRelatedToRisk(riskTokens, line) {
  const haystack = normalizeText(`${line?.description || ""} ${line?.parts_hint || ""} ${line?.category || ""}`);
  return riskTokens.some((token) => haystack.includes(token));
}

function isPartBlockRelatedToRisk(riskTokens, block, linkedRepairs) {
  const blockText = normalizeText(`${block?.part_name || ""} ${block?.category || ""} ${block?.search_query || ""}`);
  const linkedCategories = linkedRepairs.map((line) => normalizeText(line?.category || ""));
  if (riskTokens.some((token) => blockText.includes(token))) { return true; }
  return linkedCategories.some((category) => category && normalizeText(block?.category || "").includes(category));
}

function priorityFor(risk) {
  const rawPriority = String(risk?.priority || risk?.risk_priority || "").toLowerCase();
  const map = { high: "P1", medium: "P2", low: "P3", p1: "P1", p2: "P2", p3: "P3" };
  if (map[rawPriority]) { return map[rawPriority]; }
  if (rawPriority) { return rawPriority.toUpperCase(); }
  if (risk?.severity === "high") { return "P1"; }
  if (risk?.severity === "medium") { return "P2"; }
  return "P3";
}

function confidenceFor(risk, evidenceCount, hasRepairLinks) {
  const explicit = firstDefined(risk?.confidence, risk?.confidence_level);
  if (typeof explicit === "number" && Number.isFinite(explicit)) {
    if (explicit >= 80) { return "high"; }
    if (explicit >= 60) { return "medium"; }
    return "low";
  }
  const normalized = String(explicit || "").toLowerCase();
  if (["high", "medium", "low"].includes(normalized)) { return normalized; }
  if ((risk?.estimated_cost_max || 0) > 0 && hasRepairLinks && evidenceCount >= 2) { return "high"; }
  if (evidenceCount >= 1 || hasRepairLinks) { return "medium"; }
  return "low";
}

const enrichedRisks = computed(() =>
  riskCards.value.map((risk, index) => {
    const riskTokens = tokenize(`${risk?.title || ""} ${risk?.description || ""}`);
    const linkedRepairs = repairs.value.filter((line) => isRepairRelatedToRisk(riskTokens, line)).slice(0, 3);
    const linkedPartBlocks = partBlocks.value
      .filter((block) => isPartBlockRelatedToRisk(riskTokens, block, linkedRepairs))
      .slice(0, 2);
    const evidence = [
      ...toArray(risk?.evidence),
      ...toArray(risk?.rationale),
      ...toArray(risk?.reasoning),
      ...toArray(risk?.action),
      ...linkedRepairs.map((line) => `${line.description}: ${formatRub(line.min_rub)}-${formatRub(line.max_rub)} ₽`)
    ].slice(0, 4);
    const partSuggestions = linkedPartBlocks.flatMap((block) => {
      const offers = offersFromBlock(block).slice(0, 2);
      if (!offers.length) { return []; }
      return offers.map((offer) => ({
        id: `${block.part_name}-${offer.title}-${offer.url || "no-url"}-${offer.source}`,
        partName: block.part_name || "Запчасть",
        title: offer.title || block.part_name || "Лот",
        priceRub: offer.priceRub,
        url: offer.url || null,
        source: offer.source
      }));
    });
    return {
      id: `${risk?.title || "risk"}-${index}`,
      title: risk?.title || "Риск без названия",
      description: risk?.description || "Описание риска не передано backend.",
      severity: risk?.severity || "unknown",
      priority: priorityFor(risk),
      confidence: confidenceFor(risk, evidence.length, linkedRepairs.length > 0),
      estimatedCostMin: risk?.estimated_cost_min,
      estimatedCostMax: risk?.estimated_cost_max,
      evidence,
      partSuggestions: partSuggestions.slice(0, 3)
    };
  })
);

const vehiclePassport = computed(() => {
  const inspection = props.inspection || {};
  const data = report.value || {};
  const passport = data.vehicle_passport || {};
  const listingUrl = firstDefined(inspection.listing_url, data.listing_url);
  const source = normalizeSource(
    firstDefined(passport.source_platform, data.listing_source, data.platform, data.source),
    firstDefined(passport.source_listing_url, listingUrl)
  );
  const reliability = reliabilityLabel(
    firstDefined(passport.source_quality, data.source_confidence, data.parse_status, data.source_reliability)
  );
  const reliabilityReason =
    firstDefined(data.parse_reason, data.action_required, data.parse_error) ||
    "Источник распознан по данным backend.";
  return {
    brand: firstDefined(inspection.brand, passport.brand, data.brand, data.vehicle?.brand),
    model: firstDefined(inspection.model, passport.model, data.model, data.vehicle?.model),
    year: firstDefined(inspection.year, passport.year, data.year, data.vehicle?.year),
    vin: firstDefined(inspection.vin, passport.vin, data.vin, data.vehicle?.vin),
    mileageKm: firstDefined(inspection.mileage_km, passport.mileage_km, data.mileage_km, data.vehicle?.mileage_km),
    priceRub: firstDefined(inspection.price_rub, passport.price_rub, data.price_rub, data.vehicle?.price_rub),
    source,
    reliability,
    reliabilityReason,
    listingUrl: firstDefined(passport.source_listing_url, listingUrl)
  };
});

const partsMarketplace = computed(() =>
  [
    ...replacementSuggestions.value.flatMap((suggestion, index) =>
      [
        ...(suggestion.offer_cards || []).map((offer, offerIndex) => ({
          id: `suggestion-card-${index}-${offerIndex}-${offer.url || "no-url"}`,
          partName: suggestion.part_name || "Запчасть",
          category: suggestion.category || "Категория не указана",
          source: normalizeSource(suggestion.source_platforms?.[0] || "generic", offer.url),
          title: offer.title || suggestion.part_name || "Лот",
          priceRub: offer.price_rub ?? suggestion.price_min_rub ?? null,
          url: offer.url || null
        })),
        ...(suggestion.offer_urls || []).map((url, offerIndex) => ({
          id: `suggestion-url-${index}-${offerIndex}-${url || "no-url"}`,
          partName: suggestion.part_name || "Запчасть",
          category: suggestion.category || "Категория не указана",
          source: normalizeSource(suggestion.source_platforms?.[0] || "generic", url),
          title: "Открыть предложение",
          priceRub: suggestion.price_min_rub ?? null,
          url: url || null
        }))
      ]
    ),
    ...partBlocks.value
    .flatMap((block, index) =>
      offersFromBlock(block).map((offer, offerIndex) => ({
        id: `${index}-${offerIndex}-${offer.source}-${offer.url || "no-url"}`,
        partName: block?.part_name || "Запчасть",
        category: block?.category || "Категория не указана",
        source: offer.source,
        title: offer.title,
        priceRub: offer.priceRub,
        url: offer.url
      }))
    )
  ]
    .slice(0, 10)
);

const photoFindings = computed(() => {
  const inspectionPhotos = Array.isArray(props.inspection?.photos_metadata) ? props.inspection.photos_metadata : [];
  const legacyPhotos = Array.isArray(legacyPhotoMetadata.value) ? legacyPhotoMetadata.value : [];
  const reportFindings = Array.isArray(reportPhotoFindings.value) ? reportPhotoFindings.value : [];
  const merged = [...inspectionPhotos, ...legacyPhotos, ...reportFindings];
  return merged
    .map((entry, index) => ({
      id: `${entry?.photo_url || entry?.source_photo_url || entry?.url || "photo"}-${index}`,
      photoUrl: firstDefined(entry?.photo_url, entry?.source_photo_url, entry?.url, entry?.source),
      zone: firstDefined(entry?.zone, entry?.area, "Зона не указана"),
      finding:
        firstDefined(
          entry?.issue, entry?.finding, entry?.findings, entry?.title,
          entry?.summary, entry?.condition_summary, entry?.analysis,
          entry?.evidence, entry?.rationale, entry?.action, entry?.note
        ) || "Вывод по фото не передан backend.",
      confidence: firstDefined(entry?.confidence, entry?.confidence_level)
    }))
    .filter((entry) => entry.photoUrl || entry.finding)
    .slice(0, 8);
});

function confidenceLabel(confidence) {
  if (typeof confidence === "number" && Number.isFinite(confidence)) {
    if (confidence >= 80) { return `Высокая уверенность (${confidence}%)`; }
    if (confidence >= 60) { return `Средняя уверенность (${confidence}%)`; }
    return `Низкая уверенность (${confidence}%)`;
  }
  const map = {
    high: "Высокая уверенность",
    medium: "Средняя уверенность",
    low: "Низкая уверенность"
  };
  return map[String(confidence || "").toLowerCase()] || "Уверенность не указана";
}

function sourceSlug(src) {
  const s = String(src || "").toLowerCase();
  if (s === "avito") return "avito";
  if (s === "drom") return "drom";
  if (s === "auto.ru" || s === "auto_ru") return "auto_ru";
  return "generic";
}

const maxRepairRub = computed(() => {
  if (!repairs.value.length) return 0;
  return Math.max(...repairs.value.map(r => r.max_rub || 0));
});
</script>

<template>
  <section class="overview-grid">

    <!-- Паспорт автомобиля — blue accent -->
    <article class="glass-block span-2 card--blue" data-reveal>
      <div class="section-head">
        <h2>
          <span class="section-icon section-icon--blue">\U0001faaa</span>
          Паспорт автомобиля
        </h2>
        <span :class="`src-badge src-badge--${sourceSlug(vehiclePassport.source)}`" style="font-size: 0.78rem; padding: 4px 12px;">
          {{ vehiclePassport.source }}
        </span>
      </div>

      <div class="passport-grid">
        <div class="passport-cell">
          <div class="passport-cell__key">Марка и модель</div>
          <div class="passport-cell__val">{{ vehiclePassport.brand || '—' }} {{ vehiclePassport.model || '' }}</div>
        </div>
        <div class="passport-cell">
          <div class="passport-cell__key">Год выпуска</div>
          <div class="passport-cell__val">{{ vehiclePassport.year || '—' }}</div>
        </div>
        <div class="passport-cell">
          <div class="passport-cell__key">VIN</div>
          <div class="passport-cell__val" style="font-size: 0.82rem; letter-spacing: 0.08em;">{{ vehiclePassport.vin || 'Не передан' }}</div>
        </div>
        <div class="passport-cell">
          <div class="passport-cell__key">Пробег</div>
          <div class="passport-cell__val">{{ vehiclePassport.mileageKm ? `${formatRub(vehiclePassport.mileageKm)} км` : '—' }}</div>
        </div>
        <div class="passport-cell">
          <div class="passport-cell__key">Цена объявления</div>
          <div class="passport-cell__val" style="color: var(--accent);">{{ vehiclePassport.priceRub ? `${formatRub(vehiclePassport.priceRub)} ₽` : '—' }}</div>
        </div>
        <div class="passport-cell">
          <div class="passport-cell__key">Достоверность источника</div>
          <div class="passport-cell__val" style="font-size: 0.85rem;">{{ vehiclePassport.reliability }}</div>
        </div>
      </div>

      <p class="section-copy" style="margin-top: 12px;">{{ vehiclePassport.reliabilityReason }}</p>
      <p v-if="vehiclePassport.listingUrl" class="section-copy" style="margin-top: 6px;">
        Источник:
        <a :href="vehiclePassport.listingUrl" target="_blank" rel="noopener noreferrer" style="margin-left: 4px;">{{ vehiclePassport.listingUrl }}</a>
      </p>
    </article>

    <!-- Риски сделки — red accent -->
    <article class="glass-block span-2 card--red" data-reveal>
      <div class="section-head">
        <h2>
          <svg class="section-icon section-icon--red" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3 2.5 20h19z"/><path d="M12 9v5M12 17.5h.01"/></svg>
          Риски сделки
        </h2>
        <span
          class="pill"
          :class="enrichedRisks.length ? 'badge--gradient-red' : ''"
        >
          {{ enrichedRisks.length }} {{ enrichedRisks.length === 1 ? 'риск' : enrichedRisks.length >= 2 && enrichedRisks.length <= 4 ? 'риска' : 'рисков' }}
        </span>
      </div>

      <p v-if="!enrichedRisks.length" class="section-copy">
        Риски пока не рассчитаны. Проверьте исходные данные или повторите анализ.
      </p>

      <div v-else class="risk-grid risk-grid--detailed">
        <div
          v-for="risk in enrichedRisks"
          :key="risk.id"
          class="risk-card"
          :class="`risk-card--${risk.severity}`"
        >
          <div class="risk-card-head">
            <h3>
              <span class="risk-card__severity-icon" :aria-label="risk.severity">
                <span v-if="risk.severity === 'high'">\U0001f534</span>
                <span v-else-if="risk.severity === 'medium'">\U0001f7e1</span>
                <span v-else-if="risk.severity === 'low'">\U0001f7e2</span>
                <span v-else>⚪</span>
              </span>
              {{ risk.title }}
            </h3>
            <div class="risk-badges">
              <span class="risk-badge" :class="`risk-badge--${risk.priority.toLowerCase()}`">{{ risk.priority }}</span>
              <span class="risk-badge risk-badge--confidence">{{ confidenceLabel(risk.confidence) }}</span>
            </div>
          </div>

          <p>{{ risk.description }}</p>

          <div class="risk-meta">
            <span class="risk-severity">{{ risk.severity }}</span>
            <strong v-if="risk.estimatedCostMax">
              {{ formatRub(risk.estimatedCostMin || 0) }} — {{ formatRub(risk.estimatedCostMax) }} ₽
            </strong>
            <strong v-else style="color: var(--text-muted);">стоимость уточняется</strong>
          </div>

          <div class="risk-evidence">
            <p class="risk-subtitle">Основание</p>
            <ul v-if="risk.evidence.length">
              <li v-for="point in risk.evidence" :key="point">{{ point }}</li>
            </ul>
            <p v-else class="section-copy" style="margin-top: 6px;">
              Backend не передал детальные evidence-пункты для этого риска.
            </p>
          </div>

          <div class="risk-parts">
            <p class="risk-subtitle">Запчасти для замены</p>
            <ul v-if="risk.partSuggestions.length" class="parts-links">
              <li v-for="offer in risk.partSuggestions" :key="offer.id">
                <span>
                  <a v-if="offer.url" :href="offer.url" target="_blank" rel="noopener noreferrer">
                    {{ offer.partName }} · {{ offer.title }}
                  </a>
                  <span v-else>{{ offer.partName }} · {{ offer.title }}</span>
                  <span :class="`src-badge src-badge--${sourceSlug(offer.source)}`" style="margin-left: 6px;">{{ offer.source }}</span>
                </span>
                <strong v-if="offer.priceRub" style="font-family: var(--font-mono); font-size: 0.88rem; white-space: nowrap;">{{ formatRub(offer.priceRub) }} ₽</strong>
              </li>
            </ul>
            <p v-else class="section-copy" style="margin-top: 6px;">
              Прямые ссылки на запчасти отсутствуют в ответе backend.
            </p>
          </div>
        </div>
      </div>
    </article>

    <!-- Чеклист осмотра — green accent -->
    <article class="glass-block card--green" data-reveal>
      <div class="section-head">
        <h2>
          <svg class="section-icon section-icon--green" viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg>
          Чеклист осмотра
        </h2>
        <span class="badge--gradient-green" style="font-size: 0.7rem; padding: 3px 10px;">
          {{ checklist.slice(0,5).length }} пунктов
        </span>
      </div>

      <div v-if="checklist.length" class="checklist">
        <div
          v-for="(item, idx) in checklist.slice(0, 5)"
          :key="item.title"
          class="checklist-item"
        >
          <span class="checklist-item__num">{{ String(idx + 1).padStart(2, '0') }}</span>
          <div class="checklist-item__body">
            <span v-if="item.zone" class="checklist-item__zone">{{ item.zone }}</span>
            <span class="checklist-item__title">{{ item.title }}</span>
            <span class="checklist-item__how">{{ item.how_to_check || 'Способ проверки уточняется.' }}</span>
          </div>
        </div>
      </div>
      <p v-else class="section-copy">Чеклист пока пуст. Повторите анализ для генерации шагов осмотра.</p>
    </article>

    <!-- Экономика ремонта — amber accent -->
    <article class="glass-block card--amber" data-reveal>
      <div class="section-head">
        <h2>
          <span class="section-icon section-icon--amber">\U0001f527</span>
          Экономика ремонта
        </h2>
        <span class="badge--gradient-amber" style="font-size: 0.7rem; padding: 3px 10px;">
          {{ repairs.slice(0,4).length }} позиций
        </span>
      </div>

      <div v-if="repairs.length" class="repair-economy">
        <div
          v-for="line in repairs.slice(0, 4)"
          :key="line.description"
          class="repair-row"
        >
          <div class="repair-row__head">
            <span class="repair-row__desc">{{ line.description }}</span>
            <span class="repair-row__price">{{ formatRub(line.min_rub) }} — {{ formatRub(line.max_rub) }} ₽</span>
          </div>
          <p v-if="line.parts_hint" class="section-copy" style="font-size: 0.78rem; margin-bottom: 4px;">{{ line.parts_hint }}</p>
          <div class="repair-row__bar-wrap">
            <div
              class="repair-row__bar"
              :class="{
                'repair-row__bar--gradient-danger':  (line.max_rub || 0) / (maxRepairRub || 1) > 0.6,
                'repair-row__bar--gradient-warning': (line.max_rub || 0) / (maxRepairRub || 1) <= 0.6
              }"
              :style="{ width: maxRepairRub > 0 ? `${Math.max(6, ((line.max_rub || 0) / maxRepairRub) * 100)}%` : '6%' }"
            ></div>
          </div>
        </div>
      </div>
      <p v-else class="section-copy">Ремонтные линии отсутствуют. Вероятно, отчёт ещё формируется.</p>
    </article>

    <!-- Запчасти и цены — purple accent -->
    <article class="glass-block card--purple" data-reveal>
      <div class="section-head">
        <h2>
          <span class="section-icon section-icon--purple">\U0001f6d2</span>
          Комплектующие и цены
        </h2>
      </div>
      <p class="section-copy">
        Цены оценочные и могут отличаться от фактических на момент покупки.
      </p>

      <ul v-if="partsMarketplace.length" class="parts-links parts-links--market" style="margin-top: 14px;">
        <li v-for="offer in partsMarketplace" :key="offer.id">
          <div class="parts-card">
            <span class="parts-card__name">{{ offer.partName }}</span>
            <span class="parts-card__meta">
              <span
                :class="
                  sourceSlug(offer.source) === 'avito'   ? 'src-badge src-badge--avito-solid'   :
                  sourceSlug(offer.source) === 'drom'    ? 'src-badge src-badge--drom-solid'    :
                  sourceSlug(offer.source) === 'auto_ru' ? 'src-badge src-badge--auto_ru-solid' :
                  `src-badge src-badge--${sourceSlug(offer.source)}`
                "
              >{{ offer.source }}</span>
              <span>{{ offer.category }}</span>
            </span>
            <a v-if="offer.url" :href="offer.url" target="_blank" rel="noopener noreferrer">{{ offer.title }}</a>
            <span v-else style="color: var(--text-muted); font-size: 0.88rem;">{{ offer.title }}</span>
          </div>
          <span class="parts-card__price">{{ offer.priceRub ? `${formatRub(offer.priceRub)} ₽` : '—' }}</span>
        </li>
      </ul>
      <p v-else class="section-copy" style="margin-top: 12px;">
        Backend не передал релевантные офферы комплектующих. Отчет остается валидным без этой секции.
      </p>
    </article>

    <!-- Анализ фото -->
    <article class="glass-block span-2" data-reveal>
      <div class="section-head">
        <h2>
          <span class="section-icon section-icon--blue">\U0001f4f8</span>
          Анализ фото по URL
        </h2>
        <span class="badge--gradient-blue" style="font-size: 0.7rem; padding: 3px 10px;">
          {{ photoFindings.length }} находок
        </span>
      </div>
      <p class="section-copy">
        Секция показывает данные из <code style="font-family: var(--font-mono); font-size: 0.82em; color: var(--accent);">image_findings</code> и других фото-полей, если backend передал URL и результат анализа.
      </p>

      <div v-if="photoFindings.length" class="photo-findings-grid">
        <article v-for="item in photoFindings" :key="item.id" class="photo-finding-card">
          <p class="risk-subtitle">{{ item.zone }}</p>
          <a v-if="item.photoUrl" :href="item.photoUrl" target="_blank" rel="noopener noreferrer">{{ item.photoUrl }}</a>
          <p>{{ item.finding }}</p>
          <p v-if="item.confidence !== null && item.confidence !== undefined" class="section-copy">
            {{ confidenceLabel(item.confidence) }}
          </p>
        </article>
      </div>
      <p v-else class="section-copy" style="margin-top: 12px;">
        Фото-findings отсутствуют: либо URL фото не переданы, либо анализ фото ещё не завершён.
      </p>
    </article>

  </section>
</template>
