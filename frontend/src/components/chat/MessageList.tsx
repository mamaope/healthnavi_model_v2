import { Fragment, useEffect, useRef, useState } from 'react'
import type { ChatMessage } from '../../types/chat'
import { renderModelResponse } from '../../utils/markdown'
import { chatApi } from '../../services/apiClient'
import { useAuth } from '../../providers/AuthProvider'
import { FeedbackDialog } from './FeedbackDialog'

interface MessageListProps {
  messages: ChatMessage[]
  showWelcomeMessage?: boolean
  onDeepSearch?: (userQuestion: string) => void
}

export function MessageList({ messages, showWelcomeMessage = false, onDeepSearch }: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const { isAuthenticated } = useAuth()
  const [feedback, setFeedback] = useState<Record<string, 'helpful' | 'not_helpful' | null>>({})
  const [shareStatus, setShareStatus] = useState<Record<string, 'shared' | 'copied' | null>>({})
  const [copyStatus, setCopyStatus] = useState<Record<string, 'copied' | null>>({})
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState<Record<string, boolean>>({})
  const [feedbackDialogOpen, setFeedbackDialogOpen] = useState(false)
  const [selectedMessage, setSelectedMessage] = useState<ChatMessage | null>(null)
  const [selectedFeedbackType, setSelectedFeedbackType] = useState<'helpful' | 'not_helpful' | null>(null)
  const shareTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  
  // Streaming state commented out - reverted to non-streaming
  // const isStreaming = useChatStore((state) => state.isStreaming)
  // const streamingMessageId = useChatStore((state) => state.streamingMessageId)

  useEffect(() => {
    return () => {
      if (shareTimeoutRef.current) {
        clearTimeout(shareTimeoutRef.current)
      }
      setCopyStatus({})
    }
  }, [])

  const handleFeedbackClick = (message: ChatMessage, value: 'helpful' | 'not_helpful') => {
    // Check if feedback is already set to this value (toggle off)
    const currentFeedback = feedback[message.id]
    if (currentFeedback === value) {
      // Remove feedback
      handleFeedback(message, value, '', 0, true)
      return
    }

    // Open dialog for new feedback
    setSelectedMessage(message)
    setSelectedFeedbackType(value)
    setFeedbackDialogOpen(true)
  }

  const handleDeepSearch = (aiMessage: ChatMessage) => {
    if (!onDeepSearch) return
    
    // Find the user's question that prompted this AI response
    // Look for the previous user message before this AI message
    const currentIndex = messages.findIndex(m => m.id === aiMessage.id)
    if (currentIndex > 0) {
      // Look backwards for the most recent user message
      for (let i = currentIndex - 1; i >= 0; i--) {
        if (messages[i].author === 'user') {
          onDeepSearch(messages[i].content)
          return
        }
      }
    }
  }

  const handleCopy = async (messageId: string, content: string) => {
    try {
      await navigator.clipboard.writeText(content)
      setCopyStatus((prev) => ({ ...prev, [messageId]: 'copied' }))
      if (shareTimeoutRef.current) {
        clearTimeout(shareTimeoutRef.current)
      }
      shareTimeoutRef.current = setTimeout(() => {
        setCopyStatus((prev) => {
          const updated = { ...prev }
          delete updated[messageId]
          return updated
        })
      }, 2000)
    } catch (err) {
      console.error('Failed to copy AI response:', err)
    }
  }

  const handleFeedback = async (
    message: ChatMessage,
    value: 'helpful' | 'not_helpful',
    feedbackText: string = '',
    rating: number = 0,
    isRemoving: boolean = false
  ) => {
    const messageId = message.id

    // Only submit feedback if user is authenticated and message has a backend ID
    if (!isAuthenticated || !message.messageId) {
      // For unauthenticated users or messages without backend ID, just update local state
      setFeedback((prev) => ({
        ...prev,
        [messageId]: isRemoving ? null : value,
      }))
      // Close dialog even for unauthenticated users
      setFeedbackDialogOpen(false)
      setSelectedMessage(null)
      setSelectedFeedbackType(null)
      return
    }

    const backendMessageId = message.messageId

    // Optimistically update UI
    setFeedback((prev) => ({
      ...prev,
      [messageId]: isRemoving ? null : value,
    }))
    setIsSubmittingFeedback((prev) => ({ ...prev, [messageId]: true }))

    try {
      if (isRemoving) {
        // Remove feedback
        await chatApi.removeFeedback(backendMessageId)
      } else {
        // Submit feedback with text and rating
        await chatApi.submitFeedback(backendMessageId, value, feedbackText, rating)
      }
      // Close dialog immediately on successful submission
      setFeedbackDialogOpen(false)
      setSelectedMessage(null)
      setSelectedFeedbackType(null)
    } catch (error) {
      console.error('Failed to submit feedback:', error)
      // Revert optimistic update on error
      const currentFeedback = feedback[messageId]
      setFeedback((prev) => ({
        ...prev,
        [messageId]: currentFeedback,
      }))
      // Keep dialog open on error so user can retry
    } finally {
      setIsSubmittingFeedback((prev) => ({ ...prev, [messageId]: false }))
    }
  }

  const handleFeedbackSubmit = (feedbackText: string, rating: number) => {
    if (selectedMessage && selectedFeedbackType) {
      handleFeedback(selectedMessage, selectedFeedbackType, feedbackText, rating, false)
    }
  }

  const handleShare = async (messageId: string, content: string) => {
    try {
      if (typeof navigator !== 'undefined' && navigator.share) {
        await navigator.share({
          title: 'Empirico AI Response',
          text: content,
        })
        setShareStatus((prev) => ({ ...prev, [messageId]: 'shared' }))
      } else if (typeof navigator !== 'undefined' && navigator.clipboard) {
        await navigator.clipboard.writeText(content)
        setShareStatus((prev) => ({ ...prev, [messageId]: 'copied' }))
      } else {
        // Fallback: create a temporary textarea
        const textarea = document.createElement('textarea')
        textarea.value = content
        document.body.appendChild(textarea)
        textarea.select()
        document.execCommand('copy')
        document.body.removeChild(textarea)
        setShareStatus((prev) => ({ ...prev, [messageId]: 'copied' }))
      }
    } catch (error) {
      console.error('Unable to share response', error)
      setShareStatus((prev) => ({ ...prev, [messageId]: null }))
      return
    }

    if (shareTimeoutRef.current) {
      clearTimeout(shareTimeoutRef.current)
    }
    shareTimeoutRef.current = setTimeout(() => {
      setShareStatus((prev) => ({ ...prev, [messageId]: null }))
    }, 2000)
  }

  return (
    <div className="chat-messages" ref={containerRef}>
      {messages.length === 0 && showWelcomeMessage && (
        <div className="welcome-message">
          <div className="welcome-content">
            <h3>Welcome</h3>
            <p>
              How can I assist you today? Ask clinical questions, review treatment options, or explore guidelines.
            </p>
          </div>
        </div>
      )}

      {messages.map((message) => {
        // Streaming check commented out - reverted to non-streaming
        // const isCurrentlyStreaming = isStreaming && streamingMessageId === message.id
        
        if (message.author === 'assistant') {
          // Hide empty message containers (they show as white ovals)
          if (!message.content || message.content.trim().length === 0) {
            return null
          }
          
          return (
            <div key={message.id} className="message ai-message">
              <div className="message-content">
                <div
                  dangerouslySetInnerHTML={{
                    __html: renderModelResponse(message.content),
                  }}
                />
                {/* Show actions when message has content */}
                {message.content.length > 0 && (
                  <div className="message-actions" role="group" aria-label="AI response feedback">
                    <button
                      type="button"
                      className={`message-action positive ${feedback[message.id] === 'helpful' ? 'active' : ''}`}
                      onClick={() => handleFeedbackClick(message, 'helpful')}
                      aria-pressed={feedback[message.id] === 'helpful'}
                      aria-label="Helpful"
                      disabled={isSubmittingFeedback[message.id]}
                    >
                      <i className="fas fa-thumbs-up" aria-hidden="true" />
                      <span className="sr-only">Helpful</span>
                    </button>
                    <button
                      type="button"
                      className={`message-action negative ${feedback[message.id] === 'not_helpful' ? 'active' : ''}`}
                      onClick={() => handleFeedbackClick(message, 'not_helpful')}
                      aria-pressed={feedback[message.id] === 'not_helpful'}
                      aria-label="Not helpful"
                      disabled={isSubmittingFeedback[message.id]}
                    >
                      <i className="fas fa-thumbs-down" aria-hidden="true" />
                      <span className="sr-only">Not helpful</span>
                    </button>
                    <button
                      type="button"
                      className="message-action deep-search"
                      onClick={() => handleDeepSearch(message)}
                      aria-label="Deep search"
                      title="Get a more detailed response"
                    >
                      <i className="fas fa-brain" aria-hidden="true" />
                      <span className="sr-only">Deep search</span>
                    </button>
                    <button
                      type="button"
                      className="message-action neutral"
                      onClick={() => handleCopy(message.id, message.content)}
                      aria-label="Copy AI response"
                    >
                      <i className="fas fa-copy" aria-hidden="true" />
                      <span className="sr-only">Copy</span>
                    </button>
                    <button
                      type="button"
                      className="message-action neutral"
                      onClick={() => handleShare(message.id, message.content)}
                      aria-label="Share"
                    >
                      <i className="fas fa-share-alt" aria-hidden="true" />
                      <span className="sr-only">Share</span>
                    </button>
                    {shareStatus[message.id] && (
                      <span className="message-action-status">
                        {shareStatus[message.id] === 'shared' ? 'Shared!' : 'Copied to clipboard'}
                      </span>
                    )}
                    {copyStatus[message.id] && (
                      <span className="message-action-status">
                        Copied!
                      </span>
                    )}
                  </div>
                )}
              </div>
            </div>
          )
        }

        if (message.author === 'error') {
          return (
            <div key={message.id} className="message error-message">
              <div className="message-content">
                <strong>⚠️ Error:</strong>
                <p>{message.content}</p>
              </div>
            </div>
          )
        }

        if (message.author === 'system') {
          return (
            <div key={message.id} className="message system-message">
              <div className="message-content">{message.content}</div>
            </div>
          )
        }

        return (
          <Fragment key={message.id}>
            <div className="message user-message">
              <div className="message-content">
                {message.content.split('\n').map((line, index) => (
                  <span key={`${message.id}-${index}`}>
                    {line}
                    <br />
                  </span>
                ))}
              </div>
            </div>
          </Fragment>
        )
      })}

      <FeedbackDialog
        isOpen={feedbackDialogOpen}
        feedbackType={selectedFeedbackType}
        onClose={() => {
          setFeedbackDialogOpen(false)
          setSelectedMessage(null)
          setSelectedFeedbackType(null)
        }}
        onSubmit={handleFeedbackSubmit}
        isSubmitting={selectedMessage ? isSubmittingFeedback[selectedMessage.id] : false}
      />
    </div>
  )
}

