<script setup>
// Реквизиты и контакты исполнителя (самозанятый).
</script>

<template>
  <main class="legal">
    <router-link to="/" class="legal-back">← На главную</router-link>
    <h1>Реквизиты и контакты</h1>

    <h2>Исполнитель</h2>
    <p>Самозанятый (плательщик налога на профессиональный доход)<br>
    ФИО: Долгушев Даниил Максимович<br>
    ИНН: 320207587587</p>

    <h2>Связь</h2>
    <p>Email для обращений и поддержки: dolgushevdaniel@yandex.ru<br>
    Время ответа: в течение рабочего дня.</p>

    <h2>Сервис</h2>
    <p>«ПОДКАПОТ» (AutoRewier) — информационно-консультационный сервис: анализ объявления и помощь в подготовке к осмотру автомобиля перед покупкой.<br>
    Сайт: https://www.podcapot.ru</p>

    <h2>Документы</h2>
    <p><router-link to="/oferta">Публичная оферта</router-link> · <router-link to="/privacy">Политика конфиденциальности</router-link></p>
  </main>
</template>

<style scoped>
.legal { max-width: 820px; margin: 0 auto; padding: 40px 20px 80px; line-height: 1.6; color: var(--fg, #e8eef5); }
.legal-back { display:inline-block; margin-bottom: 24px; color: var(--muted, #94a3b8); text-decoration:none; }
.legal h1 { font-size: 28px; margin-bottom: 6px; }
.legal h2 { font-size: 18px; margin: 28px 0 8px; }
.legal p { margin: 8px 0; color: var(--fg, #cbd5e1); }
</style>
