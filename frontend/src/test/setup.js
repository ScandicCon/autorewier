import { afterEach, vi } from "vitest";

class MockIntersectionObserver {
  observe() {}
  disconnect() {}
  unobserve() {}
}

if (!globalThis.IntersectionObserver) {
  globalThis.IntersectionObserver = MockIntersectionObserver;
}

afterEach(() => {
  vi.clearAllMocks();
});
