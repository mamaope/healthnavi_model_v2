export const API_URL =
  import.meta.env.VITE_API_URL?.replace(/\/$/, '') ?? '/api/v2'

function envInt(key: string, fallback: number): number {
  const value = Number.parseInt(import.meta.env[key], 10)
  return Number.isFinite(value) && value > 0 ? value : fallback
}

export const REQUEST_TIMEOUTS = {
  defaultMs: envInt('VITE_API_TIMEOUT_MS', 60000),
  diagnosisMs: envInt('VITE_DIAGNOSIS_TIMEOUT_MS', 180000),
  diagnosisStreamMs: envInt('VITE_DIAGNOSIS_STREAM_TIMEOUT_MS', 180000),
} as const

export const STORAGE_KEYS = {
  accessToken: 'empirico.accessToken',
  currentUser: 'empirico.currentUser',
  theme: 'empirico.theme',
  guestSession: 'empirico.guestSessionId',
} as const

export const APP_METADATA = {
  name: 'Empirico',
  fullName: 'Empirico Clinical Assistant',
  defaultRole: 'Healthcare Professional',
  defaultSessionName: 'New Chat',
} as const
