// In production (Vercel + Railway), set VITE_API_URL=https://your-railway-app.railway.app
// For local dev and Docker, leave unset — relative /api/v1 works via the proxy / same host.
const API_BASE = (import.meta.env.VITE_API_URL ?? "").replace(/\/$/, "");
const API_ROOT = `${API_BASE}/api/v1`;

export class ApiClientError extends Error {
  constructor(message, status, details) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.details = details;
  }
}

async function parseErrorDetails(response) {
  const raw = await response.text();
  if (!raw) return null;
  try { return JSON.parse(raw); } catch { return raw; }
}

function toErrorMessage(response, details) {
  if (typeof details === "string" && details.trim()) return details;
  if (details && typeof details === "object") {
    if (typeof details.detail === "string" && details.detail) return details.detail;
    if (Array.isArray(details.detail)) return details.detail.map((item) => item?.msg || item).join("; ");
  }
  return `API error ${response.status}`;
}

async function request(path, options = {}) {
  const response = await fetch(`${API_ROOT}${path}`, {
    credentials: "include",
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options
  });
  if (!response.ok) {
    const details = await parseErrorDetails(response);
    throw new ApiClientError(toErrorMessage(response, details), response.status, details);
  }
  return response.json();
}

export async function createInspection(payload) {
  return request("/inspections", { method: "POST", body: JSON.stringify(payload) });
}

export async function fetchInspectionsHistory() {
  return request("/inspections");
}

export async function fetchInspectionDetails(inspectionId) {
  return request(`/inspections/${inspectionId}`);
}

export async function fetchCurrentUser() {
  return request("/me");
}

export async function fetchHealth() {
  return request("/health", { headers: { "Content-Type": "application/json" } });
}

export async function fetchAdminHealth() {
  return request("/admin/health");
}

export async function fetchAdminStats() {
  return request("/admin/stats");
}

async function probeContract(path) {
  try {
    const response = await fetch(`${API_ROOT}${path}`, { credentials: "include" });
    if (response.ok) return { state: "ok", status: response.status, message: "Контракт доступен." };
    if (response.status === 401) return { state: "unauthorized", status: response.status, message: "Нужна авторизация." };
    if (response.status === 403) return { state: "forbidden", status: response.status, message: "Нет прав для просмотра." };
    if (response.status === 404 || response.status === 405) return { state: "missing", status: response.status, message: "Контракт не опубликован в backend." };
    return { state: "error", status: response.status, message: `Контракт вернул ${response.status}.` };
  } catch {
    return { state: "error", status: null, message: "Не удалось проверить контракт." };
  }
}

export async function probeSupportContracts() {
  const [health, stats] = await Promise.all([probeContract("/support/health"), probeContract("/support/stats")]);
  return { health, stats };
}

export async function requestVerificationCode(payload) {
  return request("/auth/verification/request", { method: "POST", body: JSON.stringify(payload) });
}

export async function confirmVerificationCode(payload) {
  return request("/auth/verification/confirm", { method: "POST", body: JSON.stringify(payload) });
}

export async function loginUser(email, password) {
  return request("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) });
}

export async function registerUser(email, password) {
  return request("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) });
}

export async function logoutUser() {
  return request("/auth/logout", { method: "POST" });
}

export async function checkAuth() {
  return request("/auth/check");
}

export async function registerWithConfirm(email, password, passwordConfirm) {
  return request("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, password_confirm: passwordConfirm })
  });
}

export async function parseListing(url) {
  return request("/parse-listing", { method: "POST", body: JSON.stringify({ url }) });
}

export async function requestPasswordReset(email) {
  return request("/auth/forgot-password", { method: "POST", body: JSON.stringify({ email }) });
}

export async function resetPassword(token, newPassword) {
  return request("/auth/reset-password", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword })
  });
}
