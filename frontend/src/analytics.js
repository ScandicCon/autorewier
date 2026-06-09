function toSafePayload(payload = {}) {
  return {
    app: "autorewier-frontend",
    ts: new Date().toISOString(),
    ...payload
  };
}

export function trackEvent(name, payload = {}) {
  if (!name) {
    return;
  }
  const eventPayload = toSafePayload(payload);

  if (typeof window !== "undefined") {
    window.dispatchEvent(
      new CustomEvent("autorewier:analytics", {
        detail: { name, payload: eventPayload }
      })
    );

    if (Array.isArray(window.dataLayer)) {
      window.dataLayer.push({
        event: name,
        ...eventPayload
      });
    }

    if (window.autorewierAnalytics && typeof window.autorewierAnalytics.track === "function") {
      window.autorewierAnalytics.track(name, eventPayload);
    }
  }

  if (import.meta.env.DEV) {
    console.debug("[analytics:event]", name, eventPayload);
  }
}
