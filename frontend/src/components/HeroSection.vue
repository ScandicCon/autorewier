<script setup>
defineProps({
  loading: Boolean
});
</script>

<template>
  <section class="hero" :class="{ 'hero--loading': loading }">
    <div class="hero__bg">
      <div class="hero__grid"></div>
      <div class="hero__gradient"></div>
    </div>

    <!-- Inline SVG illustration — car silhouette (right side, decorative) -->
    <svg
      viewBox="0 0 320 160"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
      style="position:absolute;right:clamp(16px,5vw,60px);bottom:clamp(20px,4vw,48px);width:clamp(180px,28vw,320px);height:auto;opacity:0.18;pointer-events:none;filter:drop-shadow(0 0 24px rgba(0,212,255,0.25));"
    >
      <rect x="20" y="80" width="280" height="55" rx="12" fill="none" stroke="#00d4ff" stroke-width="2"/>
      <path d="M75 80 L105 36 L215 36 L245 80Z" fill="none" stroke="#00d4ff" stroke-width="2"/>
      <path d="M110 78 L128 42 L192 42 L210 78Z" fill="rgba(0,212,255,0.08)" stroke="#00d4ff" stroke-width="1" opacity="0.9"/>
      <rect x="113" y="44" width="38" height="30" rx="3" fill="rgba(0,212,255,0.06)" stroke="rgba(0,212,255,0.4)" stroke-width="0.8"/>
      <rect x="157" y="44" width="38" height="30" rx="3" fill="rgba(0,212,255,0.06)" stroke="rgba(0,212,255,0.4)" stroke-width="0.8"/>
      <circle cx="82" cy="135" r="22" fill="none" stroke="#00d4ff" stroke-width="2.5"/>
      <circle cx="82" cy="135" r="10" fill="none" stroke="#00d4ff" stroke-width="1.5" opacity="0.6"/>
      <circle cx="82" cy="135" r="4" fill="#00d4ff" opacity="0.5"/>
      <circle cx="238" cy="135" r="22" fill="none" stroke="#00d4ff" stroke-width="2.5"/>
      <circle cx="238" cy="135" r="10" fill="none" stroke="#00d4ff" stroke-width="1.5" opacity="0.6"/>
      <circle cx="238" cy="135" r="4" fill="#00d4ff" opacity="0.5"/>
      <ellipse cx="296" cy="100" rx="10" ry="7" fill="rgba(0,229,160,0.3)" stroke="#00e5a0" stroke-width="1.5"/>
      <line x1="20" y1="100" x2="20" y2="115" stroke="#00d4ff" stroke-width="1.5" opacity="0.5"/>
      <line x1="20" y1="108" x2="30" y2="108" stroke="#00d4ff" stroke-width="1" opacity="0.4"/>
      <path d="M55 135 Q60 80 109 80" fill="none" stroke="#00d4ff" stroke-width="1" opacity="0.3"/>
      <path d="M211 80 Q260 80 265 135" fill="none" stroke="#00d4ff" stroke-width="1" opacity="0.3"/>
      <line x1="20" y1="107" x2="300" y2="107" stroke="rgba(0,212,255,0.12)" stroke-width="1" stroke-dasharray="4 6"/>
    </svg>

    <div class="hero__body">
      <div class="hero__badge">
        <span class="hero__dot"></span>
        <span>{{ loading ? 'Синхронизация...' : 'Готово к анализу' }}</span>
      </div>

      <h1 class="hero__title">
        Покупайте авто<br>
        <span class="hero__accent hero__accent--gradient">без рисков</span>
      </h1>

      <p class="hero__sub">
        Интеллектуальный анализ объявления: риски, бюджет ремонта и торговые аргументы — до встречи с продавцом
      </p>

      <div class="hero__stats" style="flex-wrap:wrap;gap:12px;">
        <div class="hero__stat-card hero__stat-card--blue" style="--d:0ms">
          <div class="hero__stat-card-icon hero__stat-card-icon--blue"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.35-4.35"/></svg></div>
          <div class="hero__stat-card-body">
            <strong>3 500+</strong>
            <span>проверок</span>
          </div>
        </div>
        <div class="hero__stat-card hero__stat-card--green" style="--d:80ms">
          <div class="hero__stat-card-icon hero__stat-card-icon--green"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M20 6 9 17l-5-5"/></svg></div>
          <div class="hero__stat-card-body">
            <strong>95%</strong>
            <span>точность рисков</span>
          </div>
        </div>
        <div class="hero__stat-card hero__stat-card--amber" style="--d:160ms">
          <div class="hero__stat-card-icon hero__stat-card-icon--amber"><svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M13 2 4.5 13.5H11l-1 8.5L19.5 10H13z"/></svg></div>
          <div class="hero__stat-card-body">
            <strong>≤ 3 мин</strong>
            <span>время анализа</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
