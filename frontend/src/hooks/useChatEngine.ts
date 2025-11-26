import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useCallback, useEffect, useMemo } from 'react'
import { chatApi, sessionsApi } from '../services/apiClient'
import { useAuth } from '../providers/AuthProvider'
import {
  formatChatHistory,
  useChatMessages,
  useChatStore,
} from '../store/useChatStore'
import type { ChatMessage, ChatSession } from '../types/chat'

function nowIso() {
  return new Date().toISOString()
}

function toChatMessage(message: {
  id: string | number
  message_type: 'user' | 'assistant' | 'system'
  content: string
  diagnosis_complete?: boolean
  created_at: string
}): ChatMessage {
  return {
    id: String(message.id),
    author:
      message.message_type === 'assistant'
        ? 'assistant'
        : message.message_type === 'user'
          ? 'user'
          : 'system',
    content: message.content,
    diagnosisComplete: message.diagnosis_complete,
    createdAt: message.created_at ?? nowIso(),
    messageId: typeof message.id === 'number' ? message.id : undefined, // Store numeric ID if available
  }
}

export function useChatEngine() {
  const queryClient = useQueryClient()
  const { isAuthenticated } = useAuth()

  const messages = useChatMessages()
  const sessions = useChatStore((state: any) => state.sessions)
  const currentSession = useChatStore((state: any) => state.currentSession)
  const isSending = useChatStore((state: any) => state.isSending)
  const setSessions = useChatStore((state: any) => state.setSessions)
  const setCurrentSession = useChatStore((state: any) => state.setCurrentSession)
  const ensureGuestSessionId = useChatStore(
    (state: any) => state.ensureGuestSessionId,
  )
  const addMessage = useChatStore((state: any) => state.addMessage)
  const clearMessages = useChatStore((state: any) => state.clearMessages)
  const setIsSending = useChatStore((state: any) => state.setIsSending)
  const setGuestSessionId = useChatStore((state: any) => state.setGuestSessionId)

  const {
    data: fetchedSessions,
    isLoading: sessionsLoading,
    error: sessionsError,
  } = useQuery({
    queryKey: ['chat', 'sessions'],
    queryFn: async () => {
      const response = await sessionsApi.list()
      if (!response.success) {
        throw new Error('Failed to load chat sessions.')
      }
      return response.data.sessions ?? []
    },
    enabled: isAuthenticated,
    staleTime: 1000 * 60,
  })

  useEffect(() => {
    if (!isAuthenticated) {
      setSessions([])
      return
    }
    if (!fetchedSessions) {
      return
    }
    setSessions(fetchedSessions)
  }, [fetchedSessions, isAuthenticated, setSessions])

  const loadSession = useCallback(
    async (session: ChatSession) => {
      setCurrentSession(session)
      const response = await sessionsApi.messages(session.id)
      if (response.success) {
        clearMessages()
        response.data.messages.forEach((message) => {
          addMessage(toChatMessage(message))
        })
      }
    },
    [addMessage, clearMessages, setCurrentSession],
  )

  const startNewSession = useCallback(() => {
    setCurrentSession(null)
    clearMessages()
    if (!isAuthenticated) {
      setGuestSessionId(null)
    }
  }, [clearMessages, isAuthenticated, setCurrentSession, setGuestSessionId])

  const createSessionIfNeeded = useCallback(async () => {
    if (!isAuthenticated) {
      return ensureGuestSessionId()
    }
    if (currentSession) {
      return currentSession.id
    }
    const response = await sessionsApi.create('Session')
    if (response.success) {
      setCurrentSession(response.data)
      queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] })
      return response.data.id
    }
    return null
  }, [
    currentSession,
    ensureGuestSessionId,
    isAuthenticated,
    queryClient,
    setCurrentSession,
  ])

  const sendMessageMutation = useMutation({
    mutationKey: ['chat', 'send'],
    mutationFn: async ({
      message,
      deepSearch,
    }: {
      message: string
      deepSearch: boolean
    }) => {
      if (!message.trim()) {
        throw new Error('Message cannot be empty.')
      }

      if (isSending) {
        throw new Error('Already processing a message')
      }

      const chatHistory = formatChatHistory(messages)
      const sessionId = await createSessionIfNeeded()

      const userMessage: ChatMessage = {
        id: crypto.randomUUID?.() ?? Math.random().toString(36).slice(2),
        author: 'user',
        content: message.trim(),
        createdAt: nowIso(),
      }

      addMessage(userMessage)
      setIsSending(true)

      const response = await chatApi.diagnose({
        message: message.trim(),
        chatHistory,
        sessionId,
        deepSearch,
      })

      if (!response.success || !response.data) {
        throw new Error('Failed to receive response from the assistant.')
      }


      const aiMessage: ChatMessage = {
        id: crypto.randomUUID?.() ?? Math.random().toString(36).slice(2),
        author: 'assistant',
        content: response.data.model_response,
        diagnosisComplete: response.data.diagnosis_complete,
        createdAt: nowIso(),
        messageId: response.data.message_id, // Store backend message ID for feedback
      }

      addMessage(aiMessage)
      setIsSending(false)

      if (response.data.session_id && !currentSession) {
        setCurrentSession({
          id: response.data.session_id,
          session_name: `Session ${response.data.session_id}`,
          created_at: nowIso(),
        })
        queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] })
      }

      // Return follow-up questions to be displayed above input
      return {
        message: aiMessage,
        followupQuestions: response.data.followup_questions || []
      }
    },
    onError: (error: any) => {
      console.error('Failed to send message', error)
      addMessage({
        id: crypto.randomUUID?.() ?? Math.random().toString(36).slice(2),
        author: 'error',
        content:
          error instanceof Error
            ? error.message
            : 'An unexpected error occurred while processing your request.',
        createdAt: nowIso(),
      })
      setIsSending(false)
    },
  })

  const value = useMemo(
    () => ({
      messages,
      isSending,
      sessions,
      currentSession,
      sessionsLoading,
      sessionsError,
      sendMessage: sendMessageMutation.mutateAsync,
      startNewSession,
      loadSession,
    }),
    [
      currentSession,
      isSending,
      loadSession,
      messages,
      sendMessageMutation.mutateAsync,
      sessions,
      sessionsError,
      sessionsLoading,
      startNewSession,
    ],
  )

  return value
}

