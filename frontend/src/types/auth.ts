export interface User {
  id: number | string
  email: string
  username?: string
  full_name?: string
  first_name?: string
  last_name?: string
  role?: string
  exp?: number
  created_at?: string
  updated_at?: string
}

export interface AuthSuccessResponse {
  success: boolean
  data: {
    access_token: string
    user: User
  }
  metadata?: Record<string, unknown>
}

export interface ApiErrorResponse {
  success?: boolean
  message?: string
  data?: {
    message?: string
  }
  metadata?: {
    errors?: string[]
  }
  detail?: string | { msg?: string; message?: string }[]
}

