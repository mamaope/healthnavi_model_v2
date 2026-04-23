import { Fragment, memo, useEffect, useRef, useState } from 'react'
import type { ChatMessage } from '../../types/chat'
import { getRenderModelResponse, loadMarkdownRenderer } from '../../utils/markdownLoader'
import { chatApi, sessionsApi } from '../../services/apiClient'
import { useAuth } from '../../providers/AuthProvider'
import { useChatStore } from '../../store/useChatStore'
import { FeedbackDialog } from './FeedbackDialog'

interface MessageListProps {
  messages: ChatMessage[]
  showWelcomeMessage?: boolean
  onDeepSearch?: (userQuestion: string) => void
}

// Fallback renderer (plain text with line breaks) until markdown chunk loads
const fallbackRender = getRenderModelResponse()

// Memoized AI message row to avoid re-rendering all messages during streaming
const AIMessageRow = memo(function AIMessageRow({
  message,
  renderContent,
  feedback,
  copyStatus,
  shareStatus,
  isSubmittingFeedback,
  onDeepSearch,
  onCopy,
  onShare,
  onFeedbackClick,
}: {
  message: ChatMessage
  renderContent: (content: string) => string
  feedback: 'helpful' | 'not_helpful' | null
  copyStatus: 'copied' | null
  shareStatus: 'shared' | 'copied' | null
  isSubmittingFeedback: boolean
  onDeepSearch: () => void
  onCopy: () => void
  onShare: () => void
  onFeedbackClick: (value: 'helpful' | 'not_helpful') => void
}) {
  return (
    <div className="message ai-message">
      <div className="message-content">
        <div dangerouslySetInnerHTML={{ __html: renderContent(message.content) }} />
        {message.content.length > 0 && (
          <div className="message-actions" role="group" aria-label="AI response feedback">
            <button type="button" className="message-action deep-search" onClick={onDeepSearch} aria-label="Deep search" title="Get a more detailed response">
              <i className="fas fa-brain" aria-hidden="true" />
              <span className="sr-only">Deep search</span>
            </button>
            <button type="button" className="message-action neutral" onClick={onCopy} aria-label="Copy AI response">
              <i className="fas fa-copy" aria-hidden="true" />
              <span className="sr-only">Copy</span>
            </button>
            <button type="button" className="message-action neutral" onClick={onShare} aria-label="Share">
              <i className="fas fa-share-alt" aria-hidden="true" />
              <span className="sr-only">Share</span>
            </button>
            <button
              type="button"
              className={`message-action positive ${feedback === 'helpful' ? 'active' : ''}`}
              onClick={() => onFeedbackClick('helpful')}
              aria-pressed={feedback === 'helpful'}
              aria-label="Helpful"
              disabled={isSubmittingFeedback}
              title={!message.messageId ? 'Message ID missing - cannot submit feedback' : 'Mark as helpful'}
            >
              <i className="fas fa-thumbs-up" aria-hidden="true" />
              <span className="sr-only">Helpful</span>
            </button>
            <button
              type="button"
              className={`message-action negative ${feedback === 'not_helpful' ? 'active' : ''}`}
              onClick={() => onFeedbackClick('not_helpful')}
              aria-pressed={feedback === 'not_helpful'}
              aria-label="Not helpful"
              disabled={isSubmittingFeedback}
              title={!message.messageId ? 'Message ID missing - cannot submit feedback' : 'Mark as not helpful'}
            >
              <i className="fas fa-thumbs-down" aria-hidden="true" />
              <span className="sr-only">Not helpful</span>
            </button>
            {shareStatus && <span className="message-action-status">{shareStatus === 'shared' ? 'Shared!' : 'Copied to clipboard'}</span>}
            {copyStatus && <span className="message-action-status">Copied!</span>}
          </div>
        )}
      </div>
    </div>
  )
})

const MessageListComponent = function MessageList({ messages, showWelcomeMessage = false, onDeepSearch }: MessageListProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const { isAuthenticated } = useAuth()
  const [feedback, setFeedback] = useState<Record<string, 'helpful' | 'not_helpful' | null>>({})
  const [shareStatus, setShareStatus] = useState<Record<string, 'shared' | 'copied' | null>>({})
  const [copyStatus, setCopyStatus] = useState<Record<string, 'copied' | null>>({})
  const [isSubmittingFeedback, setIsSubmittingFeedback] = useState<Record<string, boolean>>({})
  const [feedbackDialogOpen, setFeedbackDialogOpen] = useState(false)
  const [selectedMessage, setSelectedMessage] = useState<ChatMessage | null>(null)
  const [selectedFeedbackType, setSelectedFeedbackType] = useState<'helpful' | 'not_helpful' | null>(null)
  const [renderContent, setRenderContent] = useState<((content: string) => string)>(() => fallbackRender)
  const shareTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Lazy-load markdown (marked + DOMPurify) only when we have assistant messages
  const hasAssistantMessage = messages.some((m) => m.author === 'assistant')
  useEffect(() => {
    if (!hasAssistantMessage) return
    loadMarkdownRenderer().then((fn) => setRenderContent(() => fn))
  }, [hasAssistantMessage])

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

    if (!isAuthenticated) {
      // For unauthenticated users, just update local state
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

    if (!message.messageId) {
      const { currentSession } = useChatStore.getState()
      if (currentSession && message.author === 'assistant') {
        try {
          const sessionMessages = await sessionsApi.messages(currentSession.id)
          if (sessionMessages.success && sessionMessages.data.messages) {
            const matchingMessage = sessionMessages.data.messages.find(m =>
              m.message_type === 'assistant' &&
              (m.content.trim() === message.content.trim() ||
                m.content.trim().includes(message.content.trim().substring(0, 100)))
            )
            if (matchingMessage && matchingMessage.id) {
              const fetchedMessageId = typeof matchingMessage.id === 'number' ? matchingMessage.id : parseInt(String(matchingMessage.id), 10)
              useChatStore.getState().replaceMessage(message.id, { messageId: fetchedMessageId })
              message.messageId = fetchedMessageId
            } else {
              throw new Error('Message not found in session')
            }
          } else {
            throw new Error('Failed to load session messages')
          }
        } catch (reloadError) {
          console.error('Failed to reload session for messageId:', reloadError)
          alert('Unable to submit feedback: Message ID is missing. This may happen with older messages. Please try refreshing the page or submitting feedback on a newly received message.')
          setFeedbackDialogOpen(false)
          setSelectedMessage(null)
          setSelectedFeedbackType(null)
          return
        }
      } else {
        alert('Unable to submit feedback: Message ID is missing. This may happen with older messages. Please try refreshing the page or submitting feedback on a newly received message.')
        setFeedbackDialogOpen(false)
        setSelectedMessage(null)
        setSelectedFeedbackType(null)
        return
      }
    }

    // Optimistically update UI
    setFeedback((prev) => ({
      ...prev,
      [messageId]: isRemoving ? null : value,
    }))
    setIsSubmittingFeedback((prev) => ({ ...prev, [messageId]: true }))

    try {
      if (isRemoving) {
        await chatApi.removeFeedback(message.messageId)
      } else {
        await chatApi.submitFeedback(message.messageId, value, feedbackText, rating)
      }
      // Close dialog immediately on successful submission
      setFeedbackDialogOpen(false)
      setSelectedMessage(null)
      setSelectedFeedbackType(null)
    } catch (error: any) {
      console.error('Failed to submit feedback:', error)
      const errorMessage = error?.message || error?.toString() || 'Unknown error occurred'
      alert(`Failed to submit feedback: ${errorMessage}`)
      // Revert optimistic update on error
      const previousFeedback = feedback[messageId]
      setFeedback((prev) => ({
        ...prev,
        [messageId]: previousFeedback,
      }))
      // Keep dialog open on error so user can retry
      // Don't close dialog here - let user see the error and retry
    } finally {
      setIsSubmittingFeedback((prev) => ({ ...prev, [messageId]: false }))
    }
  }

  const handleFeedbackSubmit = async (feedbackText: string, rating: number) => {
    if (!selectedMessage || !selectedFeedbackType) {
      setFeedbackDialogOpen(false)
      setSelectedMessage(null)
      setSelectedFeedbackType(null)
      return
    }
    
    try {
      await handleFeedback(selectedMessage, selectedFeedbackType, feedbackText, rating, false)
    } catch (error) {
      console.error('Error in handleFeedbackSubmit:', error)
      // Error is already handled in handleFeedback, but we log it here too
      // Don't close dialog here - let handleFeedback decide
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
          if (!message.content || message.content.trim().length === 0) return null
          return (
            <AIMessageRow
              key={message.id}
              message={message}
              renderContent={renderContent}
              feedback={feedback[message.id] ?? null}
              copyStatus={copyStatus[message.id] ?? null}
              shareStatus={shareStatus[message.id] ?? null}
              isSubmittingFeedback={isSubmittingFeedback[message.id] ?? false}
              onDeepSearch={() => handleDeepSearch(message)}
              onCopy={() => handleCopy(message.id, message.content)}
              onShare={() => handleShare(message.id, message.content)}
              onFeedbackClick={(value) => handleFeedbackClick(message, value)}
            />
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

export const MessageList = memo(MessageListComponent)
