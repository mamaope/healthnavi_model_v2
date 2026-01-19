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
  // The backend returns id as a number (database ID), use it for both id and messageId
  const numericId = typeof message.id === 'number' ? message.id : parseInt(String(message.id), 10)
  const isValidId = !isNaN(numericId) && numericId > 0
  
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
    messageId: isValidId ? numericId : undefined, // Use the numeric database ID for feedback
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

      // Try streaming first, fall back to non-streaming if it fails
      let useStreaming = true
      let streamingFailed = false
      let streamedContent = ''
      let aiMessageId = ''

      if (useStreaming) {
        try {
          setIsStreaming(true)
          aiMessageId = crypto.randomUUID?.() ?? Math.random().toString(36).slice(2)
          
          // Add empty AI message placeholder for streaming
          const aiMessagePlaceholder: ChatMessage = {
            id: aiMessageId,
            author: 'assistant',
            content: '',
            createdAt: nowIso(),
          }
          addMessage(aiMessagePlaceholder)
          setStreamingMessageId(aiMessageId)

          // Stream the response
          const streamGenerator = chatApi.diagnoseStream({
            message: message.trim(),
            chatHistory,
            sessionId,
            deepSearch,
          })
          
          let streamResult: IteratorResult<string, { sessionId: string | null } | undefined>
          let followupQuestions: string[] = []
          let pendingFollowupJson = ''
          let foundFollowupMarker = false
          let messageIdFromStream: number | null = null
          let allChunks: string[] = [] // Store all chunks to search for markers at the end
          const setFollowupQuestionsHook = useChatStore.getState().setFollowupQuestions
          
          setIsFetchingFollowup(true)
          
          while (!(streamResult = await streamGenerator.next()).done) {
            const chunk = streamResult.value
            allChunks.push(chunk) // Store all chunks
            
            // Check for message_id marker first (before processing content)
            if (chunk.includes('[MESSAGE_ID]:')) {
              const messageIdMatch = chunk.match(/\[MESSAGE_ID\]:(\d+)/)
              if (messageIdMatch) {
                messageIdFromStream = parseInt(messageIdMatch[1], 10)
                console.log('✅ Extracted message_id from stream:', messageIdFromStream)
                // Remove the marker from content before adding to stream
                const contentWithoutMarker = chunk.replace(/\[MESSAGE_ID\]:\d+\s*/g, '').trim()
                if (contentWithoutMarker) {
                  streamedContent += contentWithoutMarker
                  appendMessageContent(aiMessageId, contentWithoutMarker)
                }
                continue
              }
            }
            
            // Check for followup questions marker
            if (chunk.includes('[FOLLOWUP_QUESTIONS]:')) {
              foundFollowupMarker = true
              const jsonStart = chunk.indexOf('[FOLLOWUP_QUESTIONS]:') + '[FOLLOWUP_QUESTIONS]:'.length
              pendingFollowupJson = chunk.substring(jsonStart)
              
              const contentWithoutMarker = chunk.substring(0, chunk.indexOf('[FOLLOWUP_QUESTIONS]:')).trim()
              if (contentWithoutMarker) {
                streamedContent += contentWithoutMarker
                appendMessageContent(aiMessageId, contentWithoutMarker)
              }
              continue
            } else if (foundFollowupMarker) {
              pendingFollowupJson += chunk
              
              if (pendingFollowupJson.trim().startsWith('[') && pendingFollowupJson.trim().endsWith(']')) {
                try {
                  const parsed = JSON.parse(pendingFollowupJson.trim())
                  if (Array.isArray(parsed)) {
                    followupQuestions = parsed
                    setFollowupQuestionsHook(parsed)
                    setIsFetchingFollowup(false)  // Set to false immediately when questions arrive
                    foundFollowupMarker = false
                    pendingFollowupJson = ''
                  }
                } catch (parseError) {
                  // Continue collecting - don't set to false yet
                }
              }
              continue
            } else {
              // Regular content - add to streamed content
              streamedContent += chunk
              appendMessageContent(aiMessageId, chunk)
            }
          }
          
          // After stream ends, search all chunks for message_id if we didn't find it yet
          if (!messageIdFromStream) {
            const allContent = allChunks.join('')
            const messageIdMatch = allContent.match(/\[MESSAGE_ID\]:(\d+)/)
            if (messageIdMatch) {
              messageIdFromStream = parseInt(messageIdMatch[1], 10)
              console.log('✅ Extracted message_id from stream (end of stream search):', messageIdFromStream)
            }
          }
          
          // Update message with messageId if we got it from the stream
          if (messageIdFromStream) {
            useChatStore.getState().replaceMessage(aiMessageId, {
              messageId: messageIdFromStream
            })
            console.log('✅ Updated message with messageId:', messageIdFromStream, 'for message:', aiMessageId)
          } else {
            console.warn('⚠️ No messageId received from stream for message:', aiMessageId, 'Content length:', streamedContent.length)
            // Try to fetch messageId from session if we have a session
            const returnValue = streamResult.value
            const finalSessionId = returnValue?.sessionId || sessionId
            if (finalSessionId && isAuthenticated && currentSession) {
              console.log('Attempting to fetch messageId from session...')
              try {
                const sessionMessages = await sessionsApi.messages(finalSessionId)
                if (sessionMessages.success && sessionMessages.data.messages) {
                  // Find the most recent assistant message that matches our content
                  const matchingMessage = sessionMessages.data.messages
                    .filter(m => m.message_type === 'assistant')
                    .reverse()
                    .find(m => m.content.trim() === streamedContent.trim() || 
                               m.content.trim().includes(streamedContent.trim().substring(0, 100)))
                  if (matchingMessage && matchingMessage.id) {
                    const fetchedMessageId = typeof matchingMessage.id === 'number' ? matchingMessage.id : parseInt(String(matchingMessage.id), 10)
                    useChatStore.getState().replaceMessage(aiMessageId, {
                      messageId: fetchedMessageId
                    })
                    console.log('✅ Fetched and updated messageId from session:', fetchedMessageId)
                    messageIdFromStream = fetchedMessageId
                  }
                }
              } catch (fetchError) {
                console.error('Failed to fetch messageId from session:', fetchError)
              }
            }
          }
          
          // Process any remaining follow-up questions data
          if (foundFollowupMarker && pendingFollowupJson) {
            try {
              const parsed = JSON.parse(pendingFollowupJson.trim())
              if (Array.isArray(parsed)) {
                followupQuestions = parsed
                setFollowupQuestionsHook(parsed)
              }
            } catch (parseError) {
              // If parsing fails, we'll just not have follow-up questions
              console.warn('Failed to parse follow-up questions JSON:', parseError)
            }
          }
          
          // Always set isFetchingFollowup to false after stream completes
          // (follow-up questions either arrived or won't arrive)
          setIsFetchingFollowup(false)
          
          // Get session ID from return value for chat history continuity
          const returnValue = streamResult.value
          if (returnValue?.sessionId && !currentSession) {
            setCurrentSession({
              id: returnValue.sessionId,
              session_name: `Session ${returnValue.sessionId}`,
              created_at: nowIso(),
            })
            queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] })
          }

          setIsStreaming(false)
          setStreamingMessageId(null)
          setIsSending(false)

          // Return success with session ID and follow-up questions
          return {
            message: { id: aiMessageId, author: 'assistant', content: streamedContent, createdAt: nowIso() },
            followupQuestions: followupQuestions,
            sessionId: returnValue?.sessionId || sessionId
          }

        } catch (streamError: any) {
          streamingFailed = true
          setIsStreaming(false)
          setStreamingMessageId(null)
          setIsFetchingFollowup(false)  // Clear follow-up loading on streaming error
          
          // Remove the failed streaming message if it exists
          if (aiMessageId) {
            useChatStore.getState().replaceMessage(aiMessageId, { content: '' })
          }
        }
      }

      // Fallback to non-streaming (or if streaming failed)
      if (!useStreaming || streamingFailed) {
        try {
          const response = await chatApi.diagnose({
            message: message.trim(),
            chatHistory,
            sessionId,
            deepSearch,
          })

          if (!response.success || !response.data) {
            throw new Error('Failed to receive response from the assistant.')
          }

          // If we had a failed streaming message, update it; otherwise add new
          if (streamingFailed && aiMessageId) {
            useChatStore.getState().replaceMessage(aiMessageId, {
              content: response.data.model_response,
              diagnosisComplete: response.data.diagnosis_complete,
              messageId: response.data.message_id,
            })
          } else {
            const aiMessage: ChatMessage = {
              id: crypto.randomUUID?.() ?? Math.random().toString(36).slice(2),
              author: 'assistant',
              content: response.data.model_response,
              diagnosisComplete: response.data.diagnosis_complete,
              createdAt: nowIso(),
              messageId: response.data.message_id,
            }
            addMessage(aiMessage)
          }

          setIsSending(false)

          if (response.data.session_id && !currentSession) {
            setCurrentSession({
              id: response.data.session_id,
              session_name: `Session ${response.data.session_id}`,
              created_at: nowIso(),
            })
            queryClient.invalidateQueries({ queryKey: ['chat', 'sessions'] })
          }

          return {
            message: { id: aiMessageId || 'fallback', author: 'assistant', content: response.data.model_response, createdAt: nowIso() },
            followupQuestions: response.data.followup_questions || []
          }
        } catch (fallbackError: any) {
          setIsSending(false)
          setIsFetchingFollowup(false)  // Clear follow-up loading on error
          throw fallbackError
        }
      }

      // This shouldn't be reached, but TypeScript needs it
      throw new Error('Unexpected state in message sending')
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
      setIsFetchingFollowup(false)  // Ensure follow-up loading is cleared on error
    },
  })

  const value = useMemo(
    () => ({
      messages,
      isSending,
      isStreaming,
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

