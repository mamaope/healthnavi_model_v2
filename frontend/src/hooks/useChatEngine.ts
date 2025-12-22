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
  const isStreaming = useChatStore((state: any) => state.isStreaming)
  const streamingMessageId = useChatStore((state: any) => state.streamingMessageId)
  const setSessions = useChatStore((state: any) => state.setSessions)
  const setCurrentSession = useChatStore((state: any) => state.setCurrentSession)
  const ensureGuestSessionId = useChatStore(
    (state: any) => state.ensureGuestSessionId,
  )
  const addMessage = useChatStore((state: any) => state.addMessage)
  const appendMessageContent = useChatStore((state: any) => state.appendMessageContent)
  const clearMessages = useChatStore((state: any) => state.clearMessages)
  const setIsSending = useChatStore((state: any) => state.setIsSending)
  const setIsStreaming = useChatStore((state: any) => state.setIsStreaming)
  const setStreamingMessageId = useChatStore((state: any) => state.setStreamingMessageId)
  const setIsFetchingFollowup = useChatStore((state: any) => state.setIsFetchingFollowup)
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
    // Clear followup questions when starting a new session
    useChatStore.getState().setFollowupQuestions([])
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

      if (isSending || isStreaming) {
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

      // Create a placeholder AI message for streaming
      const aiMessageId = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2)
      const aiMessage: ChatMessage = {
        id: aiMessageId,
        author: 'assistant',
        content: '', // Start empty, will be filled by streaming
        createdAt: nowIso(),
      }

      addMessage(aiMessage)
      setIsStreaming(true)
      setStreamingMessageId(aiMessageId)
      setIsSending(false) // Not "sending" anymore, now "streaming"

      let fullResponse = ''

      try {
        // Stream the response
        const stream = chatApi.diagnoseStream({
          message: message.trim(),
          chatHistory,
          sessionId,
          deepSearch,
        })

        for await (const chunk of stream) {
          fullResponse += chunk
          appendMessageContent(aiMessageId, chunk)
        }

        // Streaming complete - update final message state
        setIsStreaming(false)
        setStreamingMessageId(null)

        // Fetch follow-up questions using non-streaming endpoint
        let followupQuestions: string[] = []
        setIsFetchingFollowup(true)
        try {
          const followupResponse = await chatApi.diagnose({
            message: message.trim(),
            chatHistory,
            sessionId,
            deepSearch,
          })
          if (followupResponse.success && followupResponse.data?.followup_questions) {
            followupQuestions = followupResponse.data.followup_questions
          }
        } catch (followupError) {
          console.warn('Could not fetch follow-up questions:', followupError)
          // Non-critical error, continue without follow-up questions
        } finally {
          setIsFetchingFollowup(false)
        }

        return {
          message: { ...aiMessage, content: fullResponse },
          followupQuestions
        }
      } catch (streamError) {
        console.error('Streaming error:', streamError)
        setIsStreaming(false)
        setStreamingMessageId(null)
        setIsFetchingFollowup(false) // Reset follow-up fetching state on error
        
        // If streaming fails, append error to the message
        if (fullResponse.length === 0) {
          appendMessageContent(aiMessageId, '⚠️ Failed to stream response. Please try again.')
        }
        
        throw streamError
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
      setIsStreaming(false)
      setStreamingMessageId(null)
      setIsFetchingFollowup(false) // Reset follow-up fetching state on error
    },
  })

  const value = useMemo(
    () => ({
      messages,
      isSending,
      isStreaming,
      streamingMessageId,
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
      isStreaming,
      streamingMessageId,
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

