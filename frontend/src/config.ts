export const API_URL =
  import.meta.env.VITE_API_URL?.replace(/\/$/, '') ?? '/api/v2'

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

