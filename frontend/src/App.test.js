import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App.vue";

// App.vue — это роутер-шелл: фон + <RouterView/> + баннер cookie-согласия.
// Тестируем реальное поведение: показ/скрытие баннера и сохранение выбора.

const CONSENT_KEY = "analytics_consent";

function mountApp() {
  return mount(App, {
    global: {
      stubs: {
        RouterView: { template: "<div data-test='route'>route-content</div>" },
        RouterLink: { template: "<a><slot /></a>" }
      }
    }
  });
}

describe("App shell", () => {
  beforeEach(() => {
    localStorage.clear();
    delete window.__initAnalytics;
  });

  afterEach(() => {
    localStorage.clear();
  });

  it("renders router content and cookie banner when consent not decided", async () => {
    const wrapper = mountApp();
    await nextTick();

    expect(wrapper.find("[data-test='route']").exists()).toBe(true);
    expect(wrapper.text()).toContain("Мы используем аналитические cookie");
  });

  it("does not show cookie banner when consent already stored", async () => {
    localStorage.setItem(CONSENT_KEY, "granted");

    const wrapper = mountApp();
    await nextTick();

    expect(wrapper.text()).not.toContain("Мы используем аналитические cookie");
  });

  it("accept stores consent and initializes analytics", async () => {
    const initAnalytics = vi.fn();
    window.__initAnalytics = initAnalytics;

    const wrapper = mountApp();
    await nextTick();

    await wrapper.get(".cc-accept").trigger("click");

    expect(localStorage.getItem(CONSENT_KEY)).toBe("granted");
    expect(initAnalytics).toHaveBeenCalledTimes(1);
    expect(wrapper.text()).not.toContain("Мы используем аналитические cookie");
  });

  it("decline stores denial and hides banner without analytics", async () => {
    const initAnalytics = vi.fn();
    window.__initAnalytics = initAnalytics;

    const wrapper = mountApp();
    await nextTick();

    await wrapper.get(".cc-decline").trigger("click");

    expect(localStorage.getItem(CONSENT_KEY)).toBe("denied");
    expect(initAnalytics).not.toHaveBeenCalled();
    expect(wrapper.text()).not.toContain("Мы используем аналитические cookie");
  });
});
