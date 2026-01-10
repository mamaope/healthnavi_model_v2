import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useRef,
  useState,
} from 'react'
import { useAudioRecorder } from '../../hooks/useAudioRecorder'
import { transcriptionApi } from '../../services/apiClient'

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
    const [isTranscribing, setIsTranscribing] = useState(false)
    const [transcriptionError, setTranscriptionError] = useState<string | null>(null)

    const {
      isRecording,
      audioBlob,
      startRecording,
      stopRecording,
      clearRecording,
      error: recordingError,
      duration,
    } = useAudioRecorder()

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

    // Handle transcription when recording stops
    useEffect(() => {
      if (audioBlob && !isRecording) {
        handleTranscription(audioBlob)
      }
    }, [audioBlob, isRecording])

    const handleTranscription = async (blob: Blob) => {
      setIsTranscribing(true)
      setTranscriptionError(null)

      try {
        const response = await transcriptionApi.transcribe(blob)
        console.log('Transcription response:', response)
        
        // Extract text from response - handle both success formats
        const transcribedText = response?.data?.text || (response?.data as any)?.data?.text
        
        if (transcribedText) {
          // Append transcribed text to current value
          const newText = value ? `${value} ${transcribedText}` : transcribedText
          onChange(newText)
          clearRecording()
          
          // Focus the textarea after transcription
          if (textareaRef.current) {
            textareaRef.current.focus()
          }
        } else {
          console.error('No text in transcription response:', response)
          setTranscriptionError('No text received from transcription')
        }
      } catch (error) {
        console.error('Transcription error:', error)
        setTranscriptionError('Failed to transcribe audio. Please try again.')
      } finally {
        setIsTranscribing(false)
      }
    }

    const handleMicClick = async () => {
      if (isRecording) {
        stopRecording()
      } else {
        await startRecording()
      }
    }

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

    const micButtonDisabled = isSending || isTranscribing

    return (
      <div className="input-area">
        {(recordingError || transcriptionError) && (
          <div className="recording-error">
            {recordingError || transcriptionError}
          </div>
        )}
        <div className="chat-input-box">
          {/* Deep reasoning button - desktop position (first), mobile second line */}
          <button
            type="button"
            className={`deep-reasoning-btn desktop-deep-search ${isDeepSearchEnabled ? 'active' : ''}`}
            onClick={() => {
              onToggleDeepSearch()
              // Return focus to textarea after toggling
              setTimeout(() => {
                if (textareaRef.current) {
                  textareaRef.current.focus()
                }
              }, 0)
            }}
            onKeyDown={(e) => {
              // Prevent Enter key from toggling the button
              if (e.key === 'Enter') {
                e.preventDefault()
                e.stopPropagation()
                // Focus textarea and send message
                if (textareaRef.current) {
                  textareaRef.current.focus()
                  void handleSend()
                }
              }
            }}
            aria-pressed={isDeepSearchEnabled}
            aria-label="Toggle deep reasoning"
            title="Deep Reasoning"
            disabled={isSending}
          >
            <i className="fas fa-brain" aria-hidden="true" />
            <span className="sr-only">Deep Reasoning</span>
          </button>
          
          {/* Textarea - first line on mobile */}
          <textarea
            ref={textareaRef}
            value={value}
            placeholder={placeholder}
            rows={1}
            onChange={onTextareaChange}
            onKeyDown={onKeyDown}
            disabled={isSending || isRecording}
            aria-label="Message input"
            className="chat-textarea-input"
          />
          
          {/* Actions container - second line on mobile, first line on desktop */}
          <div className="chat-input-actions">
            {/* Left side on mobile: Deep search + Mic button */}
            <div className="chat-input-actions-left-mobile">
              {/* Deep search button for mobile - inside actions */}
              <button
                type="button"
                className={`deep-reasoning-btn mobile-deep-search ${isDeepSearchEnabled ? 'active' : ''}`}
                onClick={() => {
                  onToggleDeepSearch()
                  setTimeout(() => {
                    if (textareaRef.current) {
                      textareaRef.current.focus()
                    }
                  }, 0)
                }}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    e.preventDefault()
                    e.stopPropagation()
                    if (textareaRef.current) {
                      textareaRef.current.focus()
                      void handleSend()
                    }
                  }
                }}
                aria-pressed={isDeepSearchEnabled}
                aria-label="Toggle deep reasoning"
                title="Deep Reasoning"
                disabled={isSending}
              >
                <i className="fas fa-brain" aria-hidden="true" />
                <span className="sr-only">Deep Reasoning</span>
              </button>
              <button
                type="button"
                className={`chat-icon-btn mobile-mic-btn ${isRecording ? 'recording' : ''} ${isTranscribing ? 'transcribing' : ''}`}
                onClick={() => void handleMicClick()}
                disabled={micButtonDisabled}
                aria-label={isRecording ? 'Stop recording' : 'Start voice input'}
                title={isRecording ? `Recording: ${duration.toFixed(1)}s` : 'Voice input'}
              >
                {isTranscribing ? (
                  <i className="fas fa-spinner fa-spin" aria-hidden="true" />
                ) : (
                  <i className={`fas fa-microphone ${isRecording ? 'pulse' : ''}`} aria-hidden="true" />
                )}
              </button>
            </div>
            {/* Right side: Character counter */}
            <span className={`chat-char-counter ${isNearLimit ? 'warning' : ''} ${isOverLimit ? 'error' : ''}`}>
              {value.length}/{MAX_MESSAGE_LENGTH}
            </span>
            {/* Send button for desktop - hidden on mobile */}
            <button
              className="chat-send-btn desktop-send-btn"
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
          
          {/* Send button for mobile - first line, hidden on desktop */}
          <button
            className="chat-send-btn mobile-send-btn"
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
    )
  },
)

ChatInput.displayName = 'ChatInput'

