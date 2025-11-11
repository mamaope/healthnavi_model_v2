export const API_URL =
  import.meta.env.VITE_API_URL?.replace(/\/$/, '') ?? '/api/v2'

export const STORAGE_KEYS = {
  accessToken: 'healthnavi.accessToken',
  currentUser: 'healthnavi.currentUser',
  theme: 'healthnavi.theme',
  guestSession: 'healthnavi.guestSessionId',
} as const

export const APP_METADATA = {
  name: 'HealthNavy',
  fullName: 'HealthNavy Clinical Assistant',
  defaultRole: 'Healthcare Professional',
  defaultSessionName: 'New Chat',
} as const

