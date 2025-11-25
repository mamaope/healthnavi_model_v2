import { API_URL, STORAGE_KEYS } from '../config'
import type {
  AuthSuccessResponse,
  ApiErrorResponse,
  User,
} from '../types/auth'
import type {
  ChatSession,
  DiagnosisResponse,
  SessionMessagesResponse,
} from '../types/chat'

type HttpMethod = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'

interface RequestOptions extends RequestInit {
  token?: string | null
  skipAuthHeader?: boolean
}

const defaultHeaders: HeadersInit = {
  'Content-Type': 'application/json',
  Accept: 'application/json',
}

function buildHeaders(token: string | null, skipAuthHeader = false) {
  const headers = new Headers(defaultHeaders)
  if (token && !skipAuthHeader) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return headers
}

async function parseJson<T>(response: Response): Promise<T> {
  const text = await response.text()
  try {
    return text ? (JSON.parse(text) as T) : ({} as T)
  } catch (error) {
    console.error('Failed to parse JSON response', error, text)
    throw new Error('Received invalid JSON from server')
  }
}

export function extractApiErrorMessage(payload: ApiErrorResponse): string {
  const messageFromMetadata = payload.metadata?.errors?.join(', ')
  if (messageFromMetadata) {
    return messageFromMetadata
  }

  const messageFromData = payload.data?.message
  if (messageFromData) {
    return messageFromData
  }

  if (typeof payload.detail === 'string') {
    return payload.detail
  }

  if (Array.isArray(payload.detail)) {
    const detailMessage = payload.detail
      .map((item) => item.msg || item.message)
      .filter(Boolean)
      .join(', ')
    if (detailMessage) {
      return detailMessage
    }
  }

  if (payload.message) {
    return payload.message
  }

  return 'An unexpected error occurred. Please try again.'
}

async function apiFetch<TResponse>(
  path: string,
  method: HttpMethod,
  options: RequestOptions = {},
): Promise<TResponse> {
  const token =
    options.token ??
    (typeof window !== 'undefined'
      ? window.localStorage.getItem(STORAGE_KEYS.accessToken)
      : null)

  const response = await fetch(`${API_URL}${path}`, {
    method,
    headers: buildHeaders(token, options.skipAuthHeader),
    body: options.body,
    signal: options.signal,
  })

  if (!response.ok) {
    const errorPayload = await parseJson<ApiErrorResponse>(response).catch(
      () => ({} as ApiErrorResponse),
    )

    // Log full error details for debugging
    console.error('API Error:', {
      status: response.status,
      statusText: response.statusText,
      path,
      payload: errorPayload,
    })

    if (response.status === 401 || response.status === 403) {
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(STORAGE_KEYS.accessToken)
        window.localStorage.removeItem(STORAGE_KEYS.currentUser)
      }
    }

    throw new Error(extractApiErrorMessage(errorPayload))
  }

  return parseJson<TResponse>(response)
}

export const authApi = {
  login(email: string, password: string) {
    return apiFetch<AuthSuccessResponse>('/auth/login', 'POST', {
      body: JSON.stringify({ email, password }),
      skipAuthHeader: true,
    })
  },
  register(firstName: string, lastName: string, email: string, password: string) {
    return apiFetch<AuthSuccessResponse>('/auth/register', 'POST', {
      body: JSON.stringify({
        first_name: firstName,
        last_name: lastName,
        email,
        password,
      }),
      skipAuthHeader: true,
    })
  },
  forgotPassword(email: string) {
    return apiFetch<{ success: boolean; data: { message: string } }>(
      '/auth/forgot-password',
      'POST',
      {
        body: JSON.stringify({ email }),
        skipAuthHeader: true,
      },
    )
  },
  resetPassword(token: string, newPassword: string) {
    return apiFetch<{ success: boolean; data: { message: string } }>(
      '/auth/reset-password',
      'POST',
      {
        body: JSON.stringify({ token, new_password: newPassword }),
        skipAuthHeader: true,
      },
    )
  },
  me(token?: string) {
    return apiFetch<{ success: boolean; data: User }>(
      '/auth/me',
      'GET',
      token ? { token } : undefined,
    )
  },
}

export const sessionsApi = {
  list() {
    return apiFetch<{ success: boolean; data: { sessions: ChatSession[] } }>(
      '/chat/sessions',
      'GET',
    )
  },
  create(sessionName: string) {
    return apiFetch<{ success: boolean; data: ChatSession }>(
      '/chat/sessions',
      'POST',
      {
        body: JSON.stringify({
          session_name: sessionName,
          patient_summary: '',
        }),
      },
    )
  },
  messages(sessionId: string) {
    return apiFetch<SessionMessagesResponse>(
      `/chat/sessions/${sessionId}/messages`,
      'GET',
    )
  },
}

export const chatApi = {
  diagnose(payload: {
    message: string
    chatHistory: string
    sessionId: string | null
    deepSearch: boolean
  }) {
    const requestBody = {
      patient_data: payload.message,
      chat_history: payload.chatHistory,
      deep_search: payload.deepSearch,
      ...(payload.sessionId !== null && { session_id: payload.sessionId }),
    }
    console.log('Sending diagnosis request:', {
      patient_data_length: payload.message.length,
      chat_history_length: payload.chatHistory.length,
      session_id: payload.sessionId,
      body: requestBody,
    })
    return apiFetch<DiagnosisResponse>('/diagnosis/diagnose', 'POST', {
      body: JSON.stringify(requestBody),
    })
  },
}

