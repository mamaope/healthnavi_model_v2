import { useState, useCallback, useRef, useEffect } from 'react'

export interface UseAudioRecorderReturn {
  isRecording: boolean
  audioBlob: Blob | null
  startRecording: () => Promise<void>
  stopRecording: () => void
  clearRecording: () => void
  error: string | null
  duration: number
}

export const useAudioRecorder = (): UseAudioRecorderReturn => {
  const [isRecording, setIsRecording] = useState(false)
  const [audioBlob, setAudioBlob] = useState<Blob | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [duration, setDuration] = useState(0)

  const mediaRecorderRef = useRef<MediaRecorder | null>(null)
  const audioChunksRef = useRef<Blob[]>([])
  const startTimeRef = useRef<number>(0)
  const durationIntervalRef = useRef<number | null>(null)

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (mediaRecorderRef.current && isRecording) {
        mediaRecorderRef.current.stop()
      }
      if (durationIntervalRef.current) {
        clearInterval(durationIntervalRef.current)
      }
    }
  }, [isRecording])

  const startRecording = useCallback(async () => {
    try {
      setError(null)
      setAudioBlob(null)
      audioChunksRef.current = []
      setDuration(0)

      // Request microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })

      // Create MediaRecorder with appropriate mime type
      const mimeType = MediaRecorder.isTypeSupported('audio/webm')
        ? 'audio/webm'
        : 'audio/mp4'

      const mediaRecorder = new MediaRecorder(stream, {
        mimeType,
      })

      mediaRecorderRef.current = mediaRecorder

      mediaRecorder.ondataavailable = (event) => {
        if (event.data.size > 0) {
          audioChunksRef.current.push(event.data)
        }
      }

      mediaRecorder.onstop = () => {
        // Create blob from chunks
        const blob = new Blob(audioChunksRef.current, { type: mimeType })
        setAudioBlob(blob)

        // Stop all tracks
        stream.getTracks().forEach((track) => track.stop())

        // Clear duration interval
        if (durationIntervalRef.current) {
          clearInterval(durationIntervalRef.current)
          durationIntervalRef.current = null
        }
      }

      mediaRecorder.onerror = (event) => {
        console.error('MediaRecorder error:', event)
        setError('Recording error occurred')
        setIsRecording(false)
      }

      // Start recording
      mediaRecorder.start()
      setIsRecording(true)
      startTimeRef.current = Date.now()

      // Update duration every 100ms
      durationIntervalRef.current = setInterval(() => {
        const elapsed = (Date.now() - startTimeRef.current) / 1000
        setDuration(elapsed)
      }, 100)
    } catch (err) {
      console.error('Error starting recording:', err)
      if (err instanceof Error) {
        if (err.name === 'NotAllowedError') {
          setError('Microphone access denied. Please allow microphone access.')
        } else if (err.name === 'NotFoundError') {
          setError('No microphone found. Please connect a microphone.')
        } else {
          setError('Failed to start recording: ' + err.message)
        }
      } else {
        setError('Failed to start recording')
      }
      setIsRecording(false)
    }
  }, [])

  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop()
      setIsRecording(false)
    }
  }, [isRecording])

  const clearRecording = useCallback(() => {
    setAudioBlob(null)
    setError(null)
    setDuration(0)
    audioChunksRef.current = []
  }, [])

  return {
    isRecording,
    audioBlob,
    startRecording,
    stopRecording,
    clearRecording,
    error,
    duration,
  }
}
