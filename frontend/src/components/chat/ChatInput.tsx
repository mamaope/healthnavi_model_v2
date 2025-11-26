import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
} from 'react'

interface ChatInputProps {
  value: string
  onChange: (value: string) => void
  onSend: (message: string) => Promise<void>
  isSending: boolean
  placeholder?: string
  isDeepSearchEnabled: boolean
  onToggleDeepSearch: () => void
}

export const MAX_MESSAGE_LENGTH = 2000

export const ChatInput = forwardRef<HTMLTextAreaElement, ChatInputProps>(
  (
    {
      value,
      onChange,
      onSend,
      isSending,
      placeholder = 'How can I help you today?',
      isDeepSearchEnabled,
      onToggleDeepSearch,
    },
    ref,
  ) => {
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    useImperativeHandle(ref, () => textareaRef.current as HTMLTextAreaElement, [])

    useEffect(() => {
      const textarea = textareaRef.current
      if (!textarea) return
      textarea.style.height = 'auto'
      const maxHeight = 150
      const newHeight = Math.min(textarea.scrollHeight, maxHeight)
      textarea.style.height = `${newHeight}px`
      textarea.style.overflowY = textarea.scrollHeight > maxHeight ? 'auto' : 'hidden'
    }, [value, isSending])

    const handleSend = useCallback(async () => {
      const trimmed = value.trim()
      if (!trimmed || isSending) return
      await onSend(trimmed)
    }, [isSending, onSend, value])

    const onKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault()
        void handleSend()
      }
    }

    const onTextareaChange = (
      event: React.ChangeEvent<HTMLTextAreaElement>,
    ) => {
      const nextValue = event.target.value
      if (nextValue.length <= MAX_MESSAGE_LENGTH) {
        onChange(nextValue)
      }
    }

    const isNearLimit = value.length > MAX_MESSAGE_LENGTH * 0.9
    const isOverLimit = value.length > MAX_MESSAGE_LENGTH

    return (
      <div className="input-area">
        <div className="input-container">
          <textarea
            ref={textareaRef}
            value={value}
            placeholder={placeholder}
            rows={1}
            onChange={onTextareaChange}
            onKeyDown={onKeyDown}
            disabled={isSending}
            aria-label="Message input"
          />
          <div className="input-actions">
            <div className="input-actions-left">
              <button
                type="button"
                className={`deep-search-toggle ${isDeepSearchEnabled ? 'active' : ''}`}
                onClick={onToggleDeepSearch}
                aria-pressed={isDeepSearchEnabled}
                aria-label="Toggle deep search for broader clinical context"
                disabled={isSending}
              >
                <span className="deep-search-icon">
                  <i className="fas fa-brain" aria-hidden="true" />
                </span>
                <span className="deep-search-text">
                  <span className="deep-search-title">Deep Reasoning</span>
                </span>
              </button>
            </div>
            <div className="input-actions-right">
              {value.length > 0 && (
                <div
                  className={`char-counter ${isNearLimit ? 'warning' : ''} ${isOverLimit ? 'error' : ''}`}
                >
                  {value.length} / {MAX_MESSAGE_LENGTH}
                </div>
              )}
              <button
                className="send-button"
                onClick={() => void handleSend()}
                disabled={isSending || value.trim().length === 0}
                aria-label="Send message"
              >
                {isSending ? (
                  <i className="fas fa-spinner fa-spin" />
                ) : (
                  <i className="fas fa-arrow-up" />
                )}
              </button>
            </div>
          </div>
        </div>
      </div>
    )
  },
)

ChatInput.displayName = 'ChatInput'

