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
}

export const MAX_MESSAGE_LENGTH = 2000

export const ChatInput = forwardRef<HTMLTextAreaElement, ChatInputProps>(
  ({ value, onChange, onSend, isSending, placeholder = 'How can I help you today?' }, ref) => {
    const textareaRef = useRef<HTMLTextAreaElement>(null)

    useImperativeHandle(ref, () => textareaRef.current as HTMLTextAreaElement, [])

    useEffect(() => {
      const textarea = textareaRef.current
      if (!textarea) return
      textarea.style.height = 'auto'
      const maxHeight = 120
      textarea.style.height = `${Math.min(textarea.scrollHeight, maxHeight)}px`
      textarea.style.overflowY =
        textarea.scrollHeight > maxHeight ? 'auto' : 'hidden'
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
          <div className="input-icons">
            <div className="icon-deep-reasoning" title="AI-powered clinical reasoning">
              <i className="fas fa-brain" />
            </div>
          </div>
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
                <i className="fas fa-paper-plane" />
              )}
            </button>
          </div>
        </div>
      </div>
    )
  },
)

ChatInput.displayName = 'ChatInput'

