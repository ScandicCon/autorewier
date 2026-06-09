<script setup>
import { computed, ref } from "vue";

const props = defineProps({
  user: { type: Object, default: null },
  health: { type: Object, default: null },
  adminHealth: { type: Object, default: null },
  adminStats: { type: Object, default: null },
  statusMap: { type: Object, default: () => ({}) },
  loading: { type: Boolean, default: false },
  error: { type: String, default: "" }
});

const emit = defineEmits(["retry"]);

const expanded = ref(false);

const stateLabelMap = {
  loading: "loading",
  ok: "ok",
  unauthorized: "401",
  forbidden: "403",
  missing: "missing",
  degraded: "degraded",
  error: "error"
};

function labelFor(state) {
  return stateLabelMap[state] || state || "n/a";
}

function stateClass(state) {
  return state ? `ops-state--${state}` : "ops-state--unknown";
}

const requiredStatuses = ["account", "health", "adminHealth", "adminStats", "supportHealth", "supportStats"];
const missingStatuses = computed(() =>
  requiredStatuses.filter((key) => !(props.statusMap?.[key] && props.statusMap[key].state))
);
const hasEmailVerificationFlag = computed(() => typeof props.user?.email_verified === "boolean");
const isEmailVerified = computed(() => props.user?.email_verified === true);
const hasPhoneVerificationFlag = computed(() => typeof props.user?.phone_verified === "boolean");
const isPhoneVerified = computed(() => props.user?.phone_verified === true);
const hasAnyVerification = computed(() => isEmailVerified.value || isPhoneVerified.value);

const overallState = computed(() => {
  const states = requiredStatuses.map(k => props.statusMap?.[k]?.state).filter(Boolean);
  if (states.some(s => ["error","unauthorized","forbidden","degraded"].includes(s))) return "error";
  if (states.some(s => s === "missing")) return "missing";
  if (states.every(s => s === "ok")) return "ok";
  return "loading";
});
</script>

<template>
  <section class="glass-block" data-reveal>

    <!-- Compact header with toggle -->
    <div class="ops-header" @click="expanded = !expanded">
      <div class="section-head" style="margin-bottom: 0; flex: 1;">
        <h2>
          <span class="section-icon section-icon--purple" style="margin-right: 6px;">⚙️</span>
          Операционная панель
        </h2>
        <span
          class="ops-state"
          :class="stateClass(overallState)"
          style="font-size: 0.7rem;"
        >{{ loading ? 'обновление...' : labelFor(overallState) }}</span>
      </div>
      <button
        class="ops-toggle"
        type="button"
        :aria-expanded="expanded"
        aria-label="Развернуть операционную панель"
      >{{ expanded ? '−' : '+' }}</button>
    </div>

    <!-- Collapsible body -->
    <div v-if="expanded" class="ops-body">
      <p class="section-copy" style="margin: 12px 0 0;">
        Срез состояния API, сессии и служебных инструментов.
      </p>

      <p v-if="error" class="inline-alert" role="alert" style="margin-top: 12px;">{{ error }}</p>
      <p v-if="missingStatuses.length" class="inline-alert" role="status" style="margin-top: 8px;">
        Не все контракты вернули статус: {{ missingStatuses.join(", ") }}. Интерфейс работает в fallback-режиме.
      </p>

      <div class="ops-grid ops-grid--dense">

        <!-- Аккаунт -->
        <article class="ops-card">
          <h3>Аккаунт</h3>
          <p v-if="user">
            {{ user.email }} · план {{ user.plan || "free" }}
            <span v-if="user.is_pro"> · Pro</span>
          </p>
          <p v-else>Сессия не определена. Проверьте вход в кабинет.</p>
          <p v-if="user && (hasEmailVerificationFlag || hasPhoneVerificationFlag) && !hasAnyVerification" class="inline-alert">
            Аккаунт не подтверждён. Подтвердите email или телефон.
          </p>
          <p v-else-if="user && hasAnyVerification" class="ops-meta">
            {{
              isEmailVerified
                ? "Email подтверждён."
                : isPhoneVerified
                  ? "Телефон подтверждён."
                  : "Аккаунт подтверждён."
            }}
          </p>
          <p v-else-if="user" class="ops-meta">Статус подтверждения email не передан backend (legacy payload).</p>
          <span class="ops-state" :class="stateClass(statusMap.account?.state)">{{ labelFor(statusMap.account?.state) }}</span>
          <p class="ops-meta">{{ statusMap.account?.message || "Состояние аккаунта неизвестно." }}</p>
          <div class="ops-actions">
            <a href="/cabinet" class="cta ghost">Кабинет</a>
            <a v-if="user && (hasEmailVerificationFlag || hasPhoneVerificationFlag) && !hasAnyVerification" href="/cabinet" class="cta ghost">
              Подтвердить
            </a>
          </div>
        </article>

        <!-- Public API health -->
        <article class="ops-card">
          <h3>Public API health</h3>
          <p v-if="health?.status === 'ok'">Сервис {{ health.service || "backend" }} отвечает корректно.</p>
          <p v-else>Health-check не подтверждён в этой сессии.</p>
          <span class="ops-state" :class="stateClass(statusMap.health?.state)">{{ labelFor(statusMap.health?.state) }}</span>
          <p class="ops-meta">{{ statusMap.health?.message || "Статус health неизвестен." }}</p>
          <a href="/docs" class="cta ghost">API docs</a>
        </article>

        <!-- Admin health -->
        <article class="ops-card">
          <h3>Admin health</h3>
          <p v-if="adminHealth?.ok">
            app {{ adminHealth.app_version || "n/a" }} · env {{ adminHealth.environment || "n/a" }}
          </p>
          <p v-else>Контракт <code style="font-family: var(--font-mono); font-size: 0.82em;">admin/health</code> недоступен.</p>
          <span class="ops-state" :class="stateClass(statusMap.adminHealth?.state)">{{ labelFor(statusMap.adminHealth?.state) }}</span>
          <p class="ops-meta">{{ statusMap.adminHealth?.message || "Статус admin/health неизвестен." }}</p>
        </article>

        <!-- Admin stats -->
        <article class="ops-card">
          <h3>Admin stats</h3>
          <p v-if="adminStats">
            users {{ adminStats.users_total ?? 0 }} · inspections {{ adminStats.inspections_total ?? 0 }}
          </p>
          <p v-else>Контракт <code style="font-family: var(--font-mono); font-size: 0.82em;">admin/stats</code> недоступен.</p>
          <span class="ops-state" :class="stateClass(statusMap.adminStats?.state)">{{ labelFor(statusMap.adminStats?.state) }}</span>
          <p class="ops-meta">{{ statusMap.adminStats?.message || "Статус admin/stats неизвестен." }}</p>
        </article>

        <!-- Support health -->
        <article class="ops-card">
          <h3>Support health</h3>
          <p>Проверка <code style="font-family: var(--font-mono); font-size: 0.82em;">support/health</code> без моков.</p>
          <span class="ops-state" :class="stateClass(statusMap.supportHealth?.state)">{{ labelFor(statusMap.supportHealth?.state) }}</span>
          <p class="ops-meta">{{ statusMap.supportHealth?.message || "Контракт support/health не проверен." }}</p>
        </article>

        <!-- Support stats -->
        <article class="ops-card">
          <h3>Support stats</h3>
          <p>Проверка <code style="font-family: var(--font-mono); font-size: 0.82em;">support/stats</code> c fallback.</p>
          <span class="ops-state" :class="stateClass(statusMap.supportStats?.state)">{{ labelFor(statusMap.supportStats?.state) }}</span>
          <p class="ops-meta">{{ statusMap.supportStats?.message || "Контракт support/stats не проверен." }}</p>
          <div class="ops-actions">
            <a href="/cabinet/subscription" class="cta ghost">Подписка</a>
            <button class="cta ghost ops-retry" type="button" :disabled="loading" @click="emit('retry')">
              {{ loading ? "Проверяем..." : "Обновить" }}
            </button>
          </div>
        </article>

      </div>
    </div>

  </section>
</template>
