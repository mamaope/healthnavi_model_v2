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
        <div className="input-container">
          <textarea
            ref={textareaRef}
            value={value}
            placeholder={placeholder}
            rows={1}
            onChange={onTextareaChange}
            onKeyDown={onKeyDown}
            disabled={isSending || isRecording}
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
              <button
                type="button"
                className={`mic-button ${isRecording ? 'recording' : ''} ${isTranscribing ? 'transcribing' : ''}`}
                onClick={() => void handleMicClick()}
                disabled={micButtonDisabled}
                aria-label={isRecording ? 'Stop recording' : 'Start voice input'}
                title={isRecording ? `Recording: ${duration.toFixed(1)}s` : 'Click to speak'}
              >
                {isTranscribing ? (
                  <i className="fas fa-spinner fa-spin" aria-hidden="true" />
                ) : (
                  <i className={`fas fa-microphone ${isRecording ? 'pulse' : ''}`} aria-hidden="true" />
                )}
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

