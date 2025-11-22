export type MessageAuthor = 'user' | 'assistant' | 'system' | 'error'

export interface ChatMessage {
  id: string
  author: MessageAuthor
  content: string
  diagnosisComplete?: boolean
  createdAt: string
}

export interface ChatSession {
  id: string
  session_name: string
  created_at: string
  updated_at?: string
  patient_summary?: string | null
}

export interface DiagnosisRequestBody {
  patient_data: string
  chat_history: string
  session_id: string | null
}

export interface DiagnosisResponse {
  success: boolean
  data: {
    model_response: string
    diagnosis_complete?: boolean
    session_id?: string
    metadata?: Record<string, unknown>
  }
  metadata?: Record<string, unknown>
}

export interface SessionMessagesResponse {
  success: boolean
  data: {
    messages: Array<{
      id: string | number
      message_type: 'user' | 'assistant' | 'system'
      content: string
      diagnosis_complete?: boolean
      created_at: string
    }>
  }
}

