// API-клиент фичи «поиск б/у детали по фото».
// Отдельный файл, чтобы не конфликтовать с inspectionApi.js при командной работе.
// Переиспользует getToken/ApiClientError из основного клиента (только импорт, без правок).
import { getToken, ApiClientError } from './inspectionApi'

const API_BASE = (import.meta.env.VITE_API_URL ?? '').replace(/\/$/, '')
const API_ROOT = `${API_BASE}/api/v1`

// Загрузка одного фото детали (+ необязательная текстовая подсказка) → похожие
// объявления на Авито. multipart/form-data; Content-Type ставит браузер сам.
export async function findPartByPhoto(file, hint = '') {
  const token = getToken()
  const authHeader = token ? { Authorization: `Bearer ${token}` } : {}

  const form = new FormData()
  form.append('file', file)
  if (hint && hint.trim()) form.append('hint', hint.trim())

  const response = await fetch(`${API_ROOT}/parts/find-by-photo`, {
    method: 'POST',
    credentials: 'include',
    headers: { ...authHeader },
    body: form,
  })

  if (!response.ok) {
    let details = null
    try { details = await response.json() } catch { /* пустой/не-JSON ответ */ }
    const detail = details && typeof details === 'object' ? details.detail : null
    const message = typeof detail === 'string' && detail ? detail : `API error ${response.status}`
    throw new ApiClientError(message, response.status, details)
  }

  return response.json()
}
