<script setup>
import { RouterLink } from 'vue-router'
import PartFinderPanel from '../components/PartFinderPanel.vue'
</script>

<template>
  <div class="pf-page">
    <div class="pf-page__inner">
      <RouterLink to="/app" class="pf-back">← В кабинет</RouterLink>
      <h1 class="pf-title">Поиск детали по фото</h1>
      <p class="pf-sub">Загрузите фотографию детали — найдём похожие б/у объявления на Авито.</p>
      <PartFinderPanel />
    </div>
  </div>
</template>

<style scoped>
.pf-page { padding: 24px 16px 48px; }
.pf-page__inner { max-width: 640px; margin: 0 auto; }
.pf-back { display: inline-block; color: var(--muted); font-size: 13px; text-decoration: none; margin-bottom: 14px; }
.pf-back:hover { text-decoration: underline; }
.pf-title { font-size: 24px; font-weight: 700; margin: 0 0 6px; }
.pf-sub { color: var(--muted); font-size: 14px; margin: 0 0 18px; }
</style>
