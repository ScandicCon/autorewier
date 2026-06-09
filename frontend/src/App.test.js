import { mount } from "@vue/test-utils";
import { nextTick } from "vue";
import { beforeEach, describe, expect, it, vi } from "vitest";
import App from "./App.vue";
import * as api from "./api/inspectionApi";

vi.mock("./analytics", () => ({
  trackEvent: vi.fn()
}));

vi.mock("./api/inspectionApi", () => {
  class ApiClientError extends Error {
    constructor(message, status, details) {
      super(message);
      this.name = "ApiClientError";
      this.status = status;
      this.details = details;
    }
  }
  return {
    ApiClientError,
    createInspection: vi.fn(),
    fetchInspectionsHistory: vi.fn(),
    fetchInspectionDetails: vi.fn(),
    fetchHealth: vi.fn(),
    fetchCurrentUser: vi.fn(),
    fetchAdminHealth: vi.fn(),
    fetchAdminStats: vi.fn(),
    probeSupportContracts: vi.fn(),
    requestVerificationCode: vi.fn(),
    confirmVerificationCode: vi.fn()
  };
});

async function flushUi() {
  await Promise.resolve();
  await nextTick();
  await Promise.resolve();
}

function mountApp() {
  return mount(App, {
    global: {
      stubs: {
        HeroSection: true,
        HistoryPanel: true,
        InspectionComposer: true,
        InspectionOverview: true,
        RecommendationBanner: true
      }
    }
  });
}

function setHappyPathApi() {
  api.fetchInspectionsHistory.mockResolvedValue([]);
  api.fetchHealth.mockResolvedValue({ status: "ok", service: "autorewier" });
  api.fetchCurrentUser.mockResolvedValue({
    email: "ops@autorewier.test",
    plan: "pro",
    is_pro: true
  });
  api.fetchAdminHealth.mockResolvedValue({
    ok: true,
    app_version: "0.2.0",
    environment: "test"
  });
  api.fetchAdminStats.mockResolvedValue({
    users_total: 10,
    inspections_total: 25,
    payments_total: 7,
    succeeded_payments: 6
  });
  api.probeSupportContracts.mockResolvedValue({
    health: { state: "missing", status: 404, message: "Контракт не опубликован в backend." },
    stats: { state: "missing", status: 404, message: "Контракт не опубликован в backend." }
  });
}

describe("App operations states", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    setHappyPathApi();
  });

  it("shows 401 authorization banner for protected history request", async () => {
    api.fetchInspectionsHistory.mockRejectedValueOnce(
      new api.ApiClientError("Unauthorized", 401, { detail: "Not authenticated" })
    );
    api.fetchCurrentUser.mockRejectedValueOnce(new api.ApiClientError("Unauthorized", 401, null));

    const wrapper = mountApp();
    await flushUi();

    const text = wrapper.text();
    expect(text).toContain("Требуется авторизация. Войдите в кабинет и повторите действие.");
    expect(text).toContain("401");
  });

  it("renders degraded fallback states for missing/forbidden contracts", async () => {
    api.fetchAdminHealth.mockRejectedValueOnce(new api.ApiClientError("Forbidden", 403, null));
    api.fetchAdminStats.mockRejectedValueOnce(new api.ApiClientError("Forbidden", 403, null));
    api.probeSupportContracts.mockResolvedValueOnce({
      health: { state: "missing", status: 404, message: "Контракт не опубликован в backend." },
      stats: { state: "missing", status: 404, message: "Контракт не опубликован в backend." }
    });

    const wrapper = mountApp();
    await flushUi();

    const text = wrapper.text();
    expect(text).toContain("Режим degraded");
    expect(text).toContain("Контракт не опубликован в backend.");
    expect(text).toContain("fallback через кабинет");
  });

  it("retries operations status and clears degraded banner after recovery", async () => {
    api.fetchAdminHealth
      .mockRejectedValueOnce(new api.ApiClientError("Forbidden", 403, null))
      .mockResolvedValueOnce({ ok: true, app_version: "0.2.0", environment: "test" });
    api.fetchAdminStats
      .mockRejectedValueOnce(new api.ApiClientError("Forbidden", 403, null))
      .mockResolvedValueOnce({
        users_total: 10,
        inspections_total: 25,
        payments_total: 7,
        succeeded_payments: 6
      });
    api.probeSupportContracts
      .mockResolvedValueOnce({
        health: { state: "missing", status: 404, message: "Контракт не опубликован в backend." },
        stats: { state: "missing", status: 404, message: "Контракт не опубликован в backend." }
      })
      .mockResolvedValueOnce({
        health: { state: "ok", status: 200, message: "Контракт доступен." },
        stats: { state: "ok", status: 200, message: "Контракт доступен." }
      });

    const wrapper = mountApp();
    await flushUi();
    expect(wrapper.text()).toContain("Режим degraded");

    await wrapper.get(".ops-retry").trigger("click");
    await flushUi();

    expect(api.fetchAdminHealth).toHaveBeenCalledTimes(2);
    expect(api.fetchAdminStats).toHaveBeenCalledTimes(2);
    expect(wrapper.text()).not.toContain("Режим degraded");
    expect(wrapper.text()).toContain("Контракт доступен.");
  });
});
