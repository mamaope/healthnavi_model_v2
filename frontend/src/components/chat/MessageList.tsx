import { Fragment, useEffect, useRef, useState } from 'react'
import type { ChatMessage } from '../../types/chat'
import { renderModelResponse } from '../../utils/markdown'
import { chatApi } from '../../services/apiClient'
import { useAuth } from '../../providers/AuthProvider'

interface MessageListProps {
  messages: ChatMessage[]
}

export function MessageList({ messages }: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const { isAuthenticated } = useAuth()
  const [feedback, setFeedback] = useState<Record<string, 'helpful' | 'not_helpful' | null>>({})
  const [shareStatus, setShareStatus] = useState<Record<string, 'shared' | 'copied' | null>>({})
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState<Record<string, boolean>>({})
  const shareTimeoutRef = useRef<NodeJS.Timeout | null>(null)

  useEffect(() => {
    if (!containerRef.current) return
    const el = containerRef.current
    el.scrollTo({
      top: el.scrollHeight,
      behavior: 'smooth',
    })
  }, [messages])

  useEffect(() => {
    return () => {
      if (shareTimeoutRef.current) {
        clearTimeout(shareTimeoutRef.current)
      }
    }
  }, [])

  const handleFeedback = async (message: ChatMessage, value: 'helpful' | 'not_helpful') => {
    // Only submit feedback if user is authenticated and message has a backend ID
    if (!isAuthenticated || !message.messageId) {
      // For unauthenticated users or messages without backend ID, just update local state
      setFeedback((prev) => ({
        ...prev,
        [message.id]: prev[message.id] === value ? null : value,
      }))
      return
    }

    const messageId = message.id
    const backendMessageId = message.messageId

    // Toggle feedback: if already set to this value, remove it
    const currentFeedback = feedback[messageId]
    const isRemoving = currentFeedback === value

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
        // Submit feedback
        await chatApi.submitFeedback(backendMessageId, value)
      }
    } catch (error) {
      console.error('Failed to submit feedback:', error)
      // Revert optimistic update on error
      setFeedback((prev) => ({
        ...prev,
        [messageId]: currentFeedback,
      }))
    } finally {
      setIsSubmittingFeedback((prev) => ({ ...prev, [messageId]: false }))
    }
  }

  const handleShare = async (messageId: string, content: string) => {
    try {
      if (typeof navigator !== 'undefined' && navigator.share) {
        await navigator.share({
          title: 'HealthNavy AI Response',
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
      {messages.length === 0 && (
        <div className="welcome-message">
          <div className="welcome-content">
            <h2 className="welcome-logo">
              <span className="logo-health">Health</span>
              <span className="logo-navy">Navy</span>
            </h2>
            <h3>Welcome to HealthNavy</h3>
            <p>
              How can I assist you today? Ask clinical questions, review treatment options, or explore guidelines.
            </p>
          </div>
        </div>
      )}

      {messages.map((message) => {
        if (message.author === 'assistant') {
          return (
            <div key={message.id} className="message ai-message">
              <div className="message-content">
                <div
                  dangerouslySetInnerHTML={{
                    __html: renderModelResponse(message.content),
                  }}
                />
                <div className="message-actions" role="group" aria-label="AI response feedback">
                  <button
                    type="button"
                    className={`message-action positive ${feedback[message.id] === 'helpful' ? 'active' : ''}`}
                    onClick={() => handleFeedback(message, 'helpful')}
                    aria-pressed={feedback[message.id] === 'helpful'}
                    disabled={isSubmittingFeedback[message.id]}
                  >
                    <i className="fas fa-thumbs-up" aria-hidden="true" />
                    Helpful
                  </button>
                  <button
                    type="button"
                    className={`message-action negative ${feedback[message.id] === 'not_helpful' ? 'active' : ''}`}
                    onClick={() => handleFeedback(message, 'not_helpful')}
                    aria-pressed={feedback[message.id] === 'not_helpful'}
                    disabled={isSubmittingFeedback[message.id]}
                  >
                    <i className="fas fa-thumbs-down" aria-hidden="true" />
                    Not helpful
                  </button>
                  <button
                    type="button"
                    className="message-action neutral"
                    onClick={() => handleShare(message.id, message.content)}
                  >
                    <i className="fas fa-share-alt" aria-hidden="true" />
                    Share
                  </button>
                  {shareStatus[message.id] && (
                    <span className="message-action-status">
                      {shareStatus[message.id] === 'shared' ? 'Shared!' : 'Copied to clipboard'}
                    </span>
                  )}
                </div>
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
    </div>
  )
}

