<script setup>
const props = defineProps({
  inspection: Object
});

const labels = {
  BUY_WITH_CONFIDENCE: "Покупать уверенно",
  CAUTIOUS: "Торг + углубленная диагностика",
  REJECT: "Отказ от сделки"
};
</script>

<template>
  <section
    class="recommendation"
    :class="{
      'recommendation--buy':     inspection?.final_recommendation === 'BUY_WITH_CONFIDENCE',
      'recommendation--caution': inspection?.final_recommendation === 'CAUTIOUS',
      'recommendation--reject':  inspection?.final_recommendation === 'REJECT'
    }"
    data-reveal
  >
    <div class="recommendation__layout">

      <!-- Icon in gradient circle -->
      <div
        class="recommendation__icon-circle"
        :class="{
          'recommendation__icon-circle--buy':     inspection?.final_recommendation === 'BUY_WITH_CONFIDENCE',
          'recommendation__icon-circle--caution': inspection?.final_recommendation === 'CAUTIOUS',
          'recommendation__icon-circle--reject':  inspection?.final_recommendation === 'REJECT'
        }"
        aria-hidden="true"
      >
        <span v-if="inspection?.final_recommendation === 'BUY_WITH_CONFIDENCE'">✓</span>
        <svg v-else-if="inspection?.final_recommendation === 'CAUTIOUS'" viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3 2.5 20h19z"/><path d="M12 9v5M12 17.5h.01"/></svg>
        <span v-else-if="inspection?.final_recommendation === 'REJECT'">✕</span>
        <span v-else>?</span>
      </div>

      <!-- Body -->
      <div class="recommendation__body">
        <span class="eyebrow">Финальная рекомендация</span>

        <h2 class="recommendation__verdict">
          {{ labels[inspection?.final_recommendation] || 'Требуются данные' }}
        </h2>

        <!-- Price row with coin icon -->
        <div class="recommendation__price-row recommendation__price-highlight">
          <svg class="recommendation__price-icon" viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"/><path d="M12 6v12M9 9h4.5a1.5 1.5 0 010 3H9m0 0h5.5a1.5 1.5 0 010 3H9"/></svg>
          <span class="recommendation__price-label">Диапазон ремонта:</span>
          <span class="recommendation__price">
            <span v-if="inspection?.repair_min_rub || inspection?.repair_max_rub">
              {{ new Intl.NumberFormat('ru-RU').format(inspection?.repair_min_rub || 0) }}
              —
              {{ new Intl.NumberFormat('ru-RU').format(inspection?.repair_max_rub || 0) }} ₽
            </span>
            <span v-else>не рассчитан</span>
          </span>
        </div>

        <div class="recommendation__actions">
          <span
            v-if="inspection?.final_recommendation === 'BUY_WITH_CONFIDENCE'"
            class="badge--gradient-green"
            style="font-size: 0.8rem; padding: 6px 16px;"
          >✓ Рекомендуем</span>
          <span
            v-else-if="inspection?.final_recommendation === 'CAUTIOUS'"
            class="badge--gradient-amber"
            style="font-size: 0.8rem; padding: 6px 16px;"
          ><svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:5px" aria-hidden="true"><path d="M12 3 2.5 20h19z"/><path d="M12 9v5M12 17.5h.01"/></svg>Уточните риски</span>
          <span
            v-else-if="inspection?.final_recommendation === 'REJECT'"
            class="badge--gradient-red"
            style="font-size: 0.8rem; padding: 6px 16px;"
          >✕ Не рекомендуем</span>

          <a href="/cabinet/new" class="cta ghost">
            Открыть классическую форму
          </a>
        </div>
      </div>

    </div>
  </section>
</template>
