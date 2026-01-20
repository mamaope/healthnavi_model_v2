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

interface RequestOptions extends Omit<RequestInit, 'headers'> {
  token?: string | null
  skipAuthHeader?: boolean
  headers?: HeadersInit | null
}

const defaultHeaders: HeadersInit = {
  'Content-Type': 'application/json',
  Accept: 'application/json',
}

/** Detect device type for X-Device-Type header (phone, tablet, laptop). */
function getDeviceType(): string {
  if (typeof navigator === 'undefined') return 'laptop'
  const ua = navigator.userAgent
  if (/iPad|Android(?!.*Mobile)|Tablet|Kindle|Silk|PlayBook|webOS/i.test(ua)) return 'tablet'
  if (/Mobile|Android|iPhone|iPod|webOS|BlackBerry|IEMobile|Opera Mini|MiuiBrowser/i.test(ua)) return 'phone'
  return 'laptop'
}

function buildHeaders(token: string | null, skipAuthHeader = false) {
  const headers = new Headers(defaultHeaders)
  headers.set('X-Device-Type', getDeviceType())
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
    // If it's a 504 Gateway Timeout, return a structured error
    if (response.status === 504) {
      return {
        message: 'Request timed out. The server took too long to respond. Please try again.',
        detail: 'Gateway Timeout - The request exceeded the maximum allowed time.',
      } as T
    }
    throw new Error('Received invalid JSON from server')
  }
}

export function extractApiErrorMessage(payload: ApiErrorResponse, statusCode?: number): string {
  // Handle specific HTTP status codes with user-friendly messages
  if (statusCode === 504) {
    return 'Request timed out. The diagnosis is taking longer than expected. This may happen during peak times. Please try again in a moment.'
  }
  
  if (statusCode === 503) {
    return 'Service temporarily unavailable. The AI service is currently busy. Please try again in a few moments.'
  }
  
  if (statusCode === 502) {
    return 'Bad gateway. The server is experiencing issues. Please try again later.'
  }
  
  if (statusCode === 500) {
    return 'Internal server error. Something went wrong on our end. Please try again or contact support if the issue persists.'
  }

  // Try to extract error message from payload
  // Check data.message first (ErrorResponse structure)
  const messageFromData = payload.data?.message
  if (messageFromData) {
    return messageFromData
  }

  // Then check metadata.errors
  const messageFromMetadata = payload.metadata?.errors?.join(', ')
  if (messageFromMetadata) {
    return messageFromMetadata
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

  // Provide more context for unknown errors
  if (statusCode) {
    return `An error occurred (HTTP ${statusCode}). Please try again. If the problem persists, contact support.`
  }

  return 'An unexpected error occurred. Please try again. If the problem persists, contact support.'
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

  // For FormData (when headers is explicitly null), only set auth header
  let headers: Headers
  if (options.headers === null) {
    // FormData case - don't set Content-Type, let browser handle it
    headers = new Headers()
    headers.set('X-Device-Type', getDeviceType())
    if (token && !options.skipAuthHeader) {
      headers.set('Authorization', `Bearer ${token}`)
    }
  } else {
    // Normal JSON case
    headers = buildHeaders(token, options.skipAuthHeader)
  }

  // Create AbortController with reasonable timeout for diagnosis endpoint
  const isDiagnosisEndpoint = path.includes('/diagnosis/diagnose')
  const timeoutDuration = isDiagnosisEndpoint ? 90000 : 60000 // 90s for diagnosis, 60s for others
  const timeoutController = new AbortController()
  const timeoutId = setTimeout(() => timeoutController.abort(), timeoutDuration)
  
  // Combine user signal with timeout signal if both exist
  let finalSignal: AbortSignal
  if (options.signal) {
    const combinedController = new AbortController()
    const abortHandler = () => combinedController.abort()
    options.signal.addEventListener('abort', abortHandler)
    timeoutController.signal.addEventListener('abort', abortHandler)
    finalSignal = combinedController.signal
  } else {
    finalSignal = timeoutController.signal
  }

  let response: Response
  try {
    response = await fetch(`${API_URL}${path}`, {
      method,
      headers,
      body: options.body,
      signal: finalSignal,
    })
    clearTimeout(timeoutId)
  } catch (error: any) {
    clearTimeout(timeoutId)
    if (error.name === 'AbortError' && timeoutController.signal.aborted) {
      throw new Error(
        isDiagnosisEndpoint
          ? 'Request timed out after 90 seconds. The diagnosis is taking longer than expected. Please try again with a simpler query or contact support if the issue persists.'
          : 'Request timed out. Please try again.'
      )
    }
    throw error
  }

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
      url: response.url,
    })

    // Handle 401/403 errors - try to refresh token first (except for auth endpoints)
    if ((response.status === 401 || response.status === 403) && 
        !path.includes('/auth/login') && 
        !path.includes('/auth/register') && 
        !path.includes('/auth/refresh') &&
        !path.includes('/auth/forgot-password') &&
        !path.includes('/auth/reset-password') &&
        token) {
      // Try to refresh the token
      try {
        // Call refresh endpoint directly to avoid circular import
        const refreshHeaders = buildHeaders(token, false)
        const refreshResponse = await fetch(`${API_URL}/auth/refresh`, {
          method: 'POST',
          headers: refreshHeaders,
          signal: finalSignal,
        })
        
        if (refreshResponse.ok) {
          const refreshData = await parseJson<AuthSuccessResponse>(refreshResponse)
          if (refreshData.success && refreshData.data) {
            // Update stored token
            if (typeof window !== 'undefined') {
              window.localStorage.setItem(STORAGE_KEYS.accessToken, refreshData.data.access_token)
              window.localStorage.setItem(STORAGE_KEYS.currentUser, JSON.stringify(refreshData.data.user))
            }
            
            // Retry the original request with new token
            const newHeaders = buildHeaders(refreshData.data.access_token, options.skipAuthHeader)
            const retryResponse = await fetch(`${API_URL}${path}`, {
              method,
              headers: newHeaders,
              body: options.body,
              signal: finalSignal,
            })
            
            if (retryResponse.ok) {
              return parseJson<TResponse>(retryResponse)
            }
            // If retry also fails, fall through to error handling
          }
        }
      } catch (refreshError) {
        console.warn('Token refresh failed:', refreshError)
        // Fall through to clear auth and throw error
      }
      
      // If refresh failed or retry failed, clear auth
      if (typeof window !== 'undefined') {
        window.localStorage.removeItem(STORAGE_KEYS.accessToken)
        window.localStorage.removeItem(STORAGE_KEYS.currentUser)
        // Clear chat state when session expires
        try {
          // Use dynamic import to avoid circular dependencies
          import('../store/useChatStore').then(({ useChatStore }) => {
            useChatStore.getState().reset()
            window.localStorage.removeItem('empirico.chat')
          }).catch(() => {
            window.localStorage.removeItem('empirico.chat')
          })
        } catch (error) {
          window.localStorage.removeItem('empirico.chat')
        }
        // Trigger auth state update by dispatching storage event
        window.dispatchEvent(new Event('storage'))
        // Refresh the page when session expires
        window.location.href = '/'
      }
    }

    throw new Error(extractApiErrorMessage(errorPayload, response.status))
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
  refreshToken(token: string) {
    return apiFetch<AuthSuccessResponse>('/auth/refresh', 'POST', {
      token,
      skipAuthHeader: false,
    })
  },
  register(firstName: string, lastName: string, email: string, password: string) {
    console.log('Registration attempt with:', { firstName, lastName, email, passwordLength: password.length })
    return apiFetch<AuthSuccessResponse>('/auth/register', 'POST', {
      body: JSON.stringify({
        first_name: firstName,
        last_name: lastName,
        email,
        password,
      }),
      skipAuthHeader: true,
    }).then(response => {
      console.log('Registration successful:', response.success)
      return response
    }).catch(error => {
      console.error('Registration failed:', error.message)
      throw error
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
  updateProfile(data: { medical_professional_type?: string; full_name?: string }) {
    return apiFetch<{ success: boolean; data: User }>(
      '/auth/profile',
      'PUT',
      {
        body: JSON.stringify(data),
      },
    )
  },
  changePassword(currentPassword: string, newPassword: string) {
    return apiFetch<{ success: boolean; data: any }>(
      '/auth/change-password',
      'POST',
      {
        body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
      },
    )
  },
  requestDataDeletion() {
    return apiFetch<{ success: boolean; data: { message: string } }>(
      '/auth/request-data-deletion',
      'POST',
    )
  },
  cancelDataDeletion() {
    return apiFetch<{ success: boolean; data: { message: string } }>(
      '/auth/cancel-data-deletion',
      'POST',
    )
  },
  getDeletionStatus() {
    return apiFetch<{
      success: boolean
      data: { pending: boolean; requested_at: string | null; scheduled_deletion_at: string | null }
    }>('/auth/deletion-status', 'GET')
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
  }): Promise<DiagnosisResponse> {
    const requestBody = {
      patient_data: payload.message,
      chat_history: payload.chatHistory,
      deep_search: payload.deepSearch ?? false, // Explicitly default to false
      ...(payload.sessionId !== null && { session_id: payload.sessionId }),
    }
    return apiFetch<DiagnosisResponse>('/diagnosis/diagnose', 'POST', {
      body: JSON.stringify(requestBody),
    })
  },

  /**
   * Stream diagnosis response in real-time.
   * Returns an AsyncGenerator that yields text chunks as they are generated.
   */
  async *diagnoseStream(payload: {
    message: string
    chatHistory: string
    sessionId: string | null
    deepSearch: boolean
  }): AsyncGenerator<string, { sessionId: string | null }, unknown> {
    const requestBody = {
      patient_data: payload.message,
      chat_history: payload.chatHistory,
      deep_search: payload.deepSearch ?? false,
      ...(payload.sessionId !== null && { session_id: payload.sessionId }),
    }

    const token =
      typeof window !== 'undefined'
        ? window.localStorage.getItem(STORAGE_KEYS.accessToken)
        : null

    const headers: HeadersInit = {
      'Content-Type': 'application/json',
      'Accept': 'text/plain',
      'X-Device-Type': getDeviceType(),
    }
    if (token) {
      headers['Authorization'] = `Bearer ${token}`
    }

    // Create timeout controller (2 minutes for streaming)
    const controller = new AbortController()
    const timeoutId = setTimeout(() => controller.abort(), 120000)

    let returnedSessionId: string | null = null

    try {
      const response = await fetch(`${API_URL}/diagnosis/diagnose/stream`, {
        method: 'POST',
        headers,
        body: JSON.stringify(requestBody),
        signal: controller.signal,
      })

      clearTimeout(timeoutId)

      if (!response.ok) {
        const statusMessage = extractApiErrorMessage({} as any, response.status)
        throw new Error(statusMessage)
      }

      // Get session ID from response header for chat history continuity
      returnedSessionId = response.headers.get('X-Session-Id') || payload.sessionId

      if (!response.body) {
        throw new Error('Streaming not supported in this browser')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()

      try {
        while (true) {
          const { done, value } = await reader.read()
          if (done) break

          const chunk = decoder.decode(value, { stream: true })
          if (chunk) {
            // Check for stream error marker
            if (chunk.includes('[STREAM_ERROR]:')) {
              const errorMessage = chunk.replace('[STREAM_ERROR]:', '').trim()
              throw new Error(`Streaming failed: ${errorMessage}`)
            }
            yield chunk
          }
        }
      } finally {
        reader.releaseLock()
      }
      
      // Return session ID for continuity
      return { sessionId: returnedSessionId }
    } catch (error: any) {
      clearTimeout(timeoutId)
      if (error.name === 'AbortError') {
        throw new Error('Streaming request timed out. Please try again.')
      }
      throw error
    }
  },
  submitFeedback(
    messageId: number,
    feedbackType: 'helpful' | 'not_helpful',
    feedbackText?: string,
    rating?: number
  ) {
    return apiFetch<{
      success: boolean
      data: {
        id: number
        message_id: number
        user_id: number
        feedback_type: string
        feedback_text: string | null
        rating: number | null
        created_at: string | null
        updated_at: string | null
      }
    }>('/diagnosis/feedback', 'POST', {
      body: JSON.stringify({
        message_id: messageId,
        feedback_type: feedbackType,
        feedback_text: feedbackText || null,
        rating: rating || null,
      }),
    })
  },
  removeFeedback(messageId: number) {
    return apiFetch<{
      success: boolean
      data: { message_id: number }
    }>(`/diagnosis/feedback/${messageId}`, 'DELETE')
  },
}

export const adminApi = {
  getMetrics(days: number = 30) {
    // Ensure days is a valid number, default to 30 if invalid
    let daysParam = 30
    if (typeof days === 'number' && !isNaN(days) && days > 0) {
      daysParam = Math.floor(days)
    } else if (typeof days === 'string') {
      const parsed = parseInt(days, 10)
      if (!isNaN(parsed) && parsed > 0) {
        daysParam = parsed
      }
    }
    // Clamp to valid range
    daysParam = Math.max(1, Math.min(365, daysParam))
    return apiFetch<{ success: boolean; data: any }>(
      `/admin/metrics?days=${daysParam}`,
      'GET',
    )
  },
  getUsageMetrics(days: number = 30) {
    return apiFetch<{ success: boolean; data: any }>(
      `/admin/metrics/usage?days=${days}`,
      'GET',
    )
  },
  getClinicalValueMetrics(days: number = 30) {
    return apiFetch<{ success: boolean; data: any }>(
      `/admin/metrics/clinical-value?days=${days}`,
      'GET',
    )
  },
  getSafetyMetrics(days: number = 30) {
    return apiFetch<{ success: boolean; data: any }>(
      `/admin/metrics/safety?days=${days}`,
      'GET',
    )
  },
  getPmfMetrics(days: number = 30) {
    return apiFetch<{ success: boolean; data: any }>(
      `/admin/metrics/pmf?days=${days}`,
      'GET',
    )
  },
  getDeviceStatistics(days: number = 30) {
    const d = Math.max(1, Math.min(365, typeof days === 'number' && !isNaN(days) ? Math.floor(days) : 30))
    return apiFetch<{ success: boolean; data: { by_type: Record<string, number>; total: number } }>(
      `/admin/metrics/devices?days=${d}`,
      'GET',
    )
  },
  getAlerts(unreadOnly: boolean = false) {
    return apiFetch<{ success: boolean; data: { alerts: any[]; count: number } }>(
      `/admin/alerts?unread_only=${unreadOnly}`,
      'GET',
    )
  },
  checkAlerts() {
    return apiFetch<{ success: boolean; data: { alerts_created: number } }>(
      '/admin/alerts/check',
      'POST',
    )
  },
  markAlertRead(alertId: number) {
    return apiFetch<{ success: boolean; data: any }>(
      `/admin/alerts/${alertId}/read`,
      'PUT',
    )
  },
  getUsers(limit: number = 50, offset: number = 0, isActive?: boolean, role?: string, medicalProfessionalType?: string, search?: string) {
    const params = new URLSearchParams()
    params.append('limit', limit.toString())
    params.append('offset', offset.toString())
    if (isActive !== undefined) params.append('is_active', isActive.toString())
    if (role) params.append('role', role)
    if (medicalProfessionalType) params.append('medical_professional_type', medicalProfessionalType)
    if (search) params.append('search', search)
    return apiFetch<{ success: boolean; data: { users: any[]; total: number; limit: number; offset: number } }>(
      `/admin/users?${params.toString()}`,
      'GET',
    )
  },
  getUser(userId: number) {
    return apiFetch<{ success: boolean; data: any }>(
      `/admin/users/${userId}`,
      'GET',
    )
  },
  updateUser(userId: number, data: { is_active?: boolean; role?: string; medical_professional_type?: string; full_name?: string }) {
    return apiFetch<{ success: boolean; data: any }>(
      `/admin/users/${userId}`,
      'PUT',
      { body: JSON.stringify(data) },
    )
  },
  changeUserPassword(userId: number, newPassword: string) {
    return apiFetch<{ success: boolean; data: any }>(
      `/admin/users/${userId}/change-password`,
      'POST',
      { body: JSON.stringify({ new_password: newPassword }) },
    )
  },
  getUserStatistics(days: number = 30) {
    // Ensure days is a valid number, default to 30 if invalid
    let daysParam = 30
    if (typeof days === 'number' && !isNaN(days) && days > 0) {
      daysParam = Math.floor(days)
    } else if (typeof days === 'string') {
      const parsed = parseInt(days, 10)
      if (!isNaN(parsed) && parsed > 0) {
        daysParam = parsed
      }
    }
    // Clamp to valid range
    daysParam = Math.max(1, Math.min(365, daysParam))
    // Ensure we always send a valid number as a string in the URL
    const url = `/admin/users/statistics?days=${encodeURIComponent(daysParam)}`
    return apiFetch<{ success: boolean; data: any }>(
      url,
      'GET',
    )
  },
  getSessionStatistics(days: number = 30) {
    // Ensure days is a valid number, default to 30 if invalid
    let daysParam = 30
    if (typeof days === 'number' && !isNaN(days) && days > 0) {
      daysParam = Math.floor(days)
    } else if (typeof days === 'string') {
      const parsed = parseInt(days, 10)
      if (!isNaN(parsed) && parsed > 0) {
        daysParam = parsed
      }
    }
    // Clamp to valid range
    daysParam = Math.max(1, Math.min(365, daysParam))
    return apiFetch<{ success: boolean; data: any }>(
      `/admin/sessions/statistics?days=${daysParam}`,
      'GET',
    )
  },
  getAiResponseStatistics(days: number = 30) {
    // Ensure days is a valid number, default to 30 if invalid
    let daysParam = 30
    if (typeof days === 'number' && !isNaN(days) && days > 0) {
      daysParam = Math.floor(days)
    } else if (typeof days === 'string') {
      const parsed = parseInt(days, 10)
      if (!isNaN(parsed) && parsed > 0) {
        daysParam = parsed
      }
    }
    // Clamp to valid range
    daysParam = Math.max(1, Math.min(365, daysParam))
    return apiFetch<{ success: boolean; data: any }>(
      `/admin/ai-responses/statistics?days=${daysParam}`,
      'GET',
    )
  },
  getAuditLogs(limit: number = 100, offset: number = 0, action?: string, userId?: number) {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    })
    if (action) params.append('action', action)
    if (userId) params.append('user_id', userId.toString())
    return apiFetch<{ success: boolean; data: { logs: any[]; total: number } }>(
      `/admin/audit-logs?${params.toString()}`,
      'GET',
    )
  },
  getSafetyEvents(status?: string, severity?: string, limit: number = 50, offset: number = 0) {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    })
    if (status) params.append('status', status)
    if (severity) params.append('severity', severity)
    return apiFetch<{ success: boolean; data: { events: any[]; total: number } }>(
      `/admin/safety-events?${params.toString()}`,
      'GET',
    )
  },
  getSurveyStatistics(days: number = 30) {
    let daysParam = 30
    if (typeof days === 'number' && !isNaN(days) && days > 0) {
      daysParam = Math.floor(days)
    }
    daysParam = Math.max(1, Math.min(365, daysParam))
    return apiFetch<{ success: boolean; data: any }>(
      `/admin/surveys/statistics?days=${daysParam}`,
      'GET',
    )
  },
  getSurveys(surveyType?: string, limit: number = 100, offset: number = 0) {
    const params = new URLSearchParams({
      limit: limit.toString(),
      offset: offset.toString(),
    })
    if (surveyType) params.append('survey_type', surveyType)
    return apiFetch<{ success: boolean; data: { surveys: any[]; total: number; limit: number; offset: number } }>(
      `/admin/surveys?${params.toString()}`,
      'GET',
    )
  },
  getSurveyConfigs() {
    return apiFetch<{ success: boolean; data: { configs: any[] } }>(
      '/surveys/admin/config',
      'GET',
    )
  },
  toggleSurveyVisibility(surveyType: string, isVisible: boolean) {
    return apiFetch<{ success: boolean; data: any }>(
      `/surveys/admin/config/${surveyType}/visibility?is_visible=${isVisible}`,
      'PUT',
    )
  },
}

export const surveysApi = {
  getAvailableSurveys() {
    return apiFetch<{ success: boolean; data: { surveys: any[] } }>(
      '/surveys/available',
      'GET',
    )
  },
  getSurveyQuestions(surveyType: string) {
    return apiFetch<{ success: boolean; data: any }>(
      `/surveys/questions/${surveyType}`,
      'GET',
    )
  },
  submitSurvey(surveyType: string, responses: Record<string, any>) {
    return apiFetch<{ success: boolean; data: any }>(
      '/surveys/submit',
      'POST',
      { body: JSON.stringify({ survey_type: surveyType, responses }) },
    )
  },
  getMySurveys() {
    return apiFetch<{ success: boolean; data: { surveys: any[] } }>(
      '/surveys/my-surveys',
      'GET',
    )
  },
  getSurveyNotification() {
    return apiFetch<{ success: boolean; data: { has_notification: boolean; pending_count: number; pending_surveys?: any[] } }>(
      '/surveys/notification',
      'GET',
    )
  },
  dismissSurveyNotification() {
    return apiFetch<{ success: boolean; data: any }>(
      '/surveys/notification/dismiss',
      'POST',
    )
  },
}

export const transcriptionApi = {
  transcribe(audioBlob: Blob) {
    const formData = new FormData()
    formData.append('audio', audioBlob, 'audio.wav')
    
    return apiFetch<{
      success: boolean
      data: {
        text: string
        language: string
        duration?: number
      }
    }>('/transcription/transcribe', 'POST', {
      body: formData,
      headers: null, // Let browser set Content-Type for FormData
    })
  },
}

