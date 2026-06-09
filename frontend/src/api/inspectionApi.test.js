import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchAdminHealth, fetchAdminStats } from "./inspectionApi";

function mockOk(payload) {
  return Promise.resolve({
    ok: true,
    status: 200,
    json: async () => payload
  });
}

describe("inspectionApi admin calls", () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("requests admin health via session credentials only", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockImplementation(() => mockOk({ ok: true }));

    await fetchAdminHealth();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, options] = fetchSpy.mock.calls[0];
    expect(options.credentials).toBe("include");
    expect(options.headers["X-Admin-Token"]).toBeUndefined();
  });

  it("requests admin stats via session credentials only", async () => {
    const fetchSpy = vi
      .spyOn(globalThis, "fetch")
      .mockImplementation(() => mockOk({ users_total: 1, inspections_total: 2 }));

    await fetchAdminStats();

    expect(fetchSpy).toHaveBeenCalledTimes(1);
    const [, options] = fetchSpy.mock.calls[0];
    expect(options.credentials).toBe("include");
    expect(options.headers["X-Admin-Token"]).toBeUndefined();
  });
});
