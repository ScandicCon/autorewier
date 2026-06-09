<script setup>
defineProps({
  items: {
    type: Array,
    default: () => []
  }
});

const emit = defineEmits(["select"]);
</script>

<template>
  <section class="glass-block" data-reveal>
    <div class="section-head">
      <h2>
        <span class="section-icon section-icon--blue">🕐</span>
        История инспекций
      </h2>
      <span
        class="pill"
        :class="items.length ? 'badge--gradient-blue' : ''"
      >
        {{ items.length }} {{ items.length === 1 ? 'запись' : items.length >= 2 && items.length <= 4 ? 'записи' : 'записей' }}
      </span>
    </div>

    <!-- Empty state with SVG car -->
    <div v-if="!items.length" class="empty-state">
      <svg viewBox="0 0 200 100" class="empty-car" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
        <rect x="20" y="45" width="160" height="40" rx="8" fill="var(--surface-2)" stroke="var(--border-strong)" stroke-width="1.5"/>
        <path d="M50 45 L70 20 L130 20 L150 45Z" fill="var(--surface-3)" stroke="var(--border-strong)" stroke-width="1.5"/>
        <circle cx="55" cy="85" r="12" fill="var(--surface-1)" stroke="var(--accent)" stroke-width="2"/>
        <circle cx="145" cy="85" r="12" fill="var(--surface-1)" stroke="var(--accent)" stroke-width="2"/>
        <circle cx="55" cy="85" r="4" fill="var(--accent)" opacity="0.7"/>
        <circle cx="145" cy="85" r="4" fill="var(--accent)" opacity="0.7"/>
        <path d="M72 42 L82 24 L118 24 L128 42Z" fill="var(--accent-glow)" stroke="var(--accent)" stroke-width="0.5" opacity="0.8"/>
        <text x="100" y="72" text-anchor="middle" fill="var(--text-muted)" font-size="14" font-family="system-ui" opacity="0.6">?</text>
      </svg>
      <h2>Проверок пока нет</h2>
      <p>Создайте первую инспекцию в форме выше — анализ займёт менее 3 минут.</p>
    </div>

    <!-- Timeline -->
    <div v-else class="timeline">
      <button
        v-for="item in items"
        :key="item.id"
        type="button"
        class="timeline-card"
        :class="{
          'timeline-card--buy':     item.final_recommendation === 'BUY_WITH_CONFIDENCE',
          'timeline-card--caution': item.final_recommendation === 'CAUTIOUS',
          'timeline-card--reject':  item.final_recommendation === 'REJECT'
        }"
        @click="emit('select', item.id)"
      >
        <div
          class="timeline-marker"
          :class="{
            'verdict-dot--buy':     item.final_recommendation === 'BUY_WITH_CONFIDENCE',
            'verdict-dot--caution': item.final_recommendation === 'CAUTIOUS',
            'verdict-dot--reject':  item.final_recommendation === 'REJECT'
          }"
        />
        <h3>
          {{ item.brand || 'Не указано' }} {{ item.model || '' }}
          <span style="color: var(--text-muted); font-size: 0.78rem; font-weight: 400;">#{{ item.id }}</span>
          <span
            v-if="item.final_recommendation === 'BUY_WITH_CONFIDENCE'"
            class="badge--gradient-green"
            style="font-size: 0.65rem; padding: 2px 9px;"
          >✓ Брать</span>
          <span
            v-else-if="item.final_recommendation === 'CAUTIOUS'"
            class="badge--gradient-amber"
            style="font-size: 0.65rem; padding: 2px 9px;"
          ><svg viewBox="0 0 24 24" width="12" height="12" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:4px" aria-hidden="true"><path d="M12 3 2.5 20h19z"/><path d="M12 9v5M12 17.5h.01"/></svg>Осторожно</span>
          <span
            v-else-if="item.final_recommendation === 'REJECT'"
            class="badge--gradient-red"
            style="font-size: 0.65rem; padding: 2px 9px;"
          >✕ Отказ</span>
        </h3>
        <p>{{ new Date(item.created_at).toLocaleDateString('ru-RU') }} · этап: {{ item.stage }}</p>
        <small>{{ item.final_recommendation || 'рекомендация не рассчитана' }}</small>
        <span class="timeline-card__arrow">→</span>
      </button>
    </div>
  </section>
</template>
