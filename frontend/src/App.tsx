import { useEffect, useMemo, useRef, useState } from 'react'
import { AuthModal, type AuthMode } from './components/auth/AuthModal'
import { ForgotPasswordModal } from './components/auth/ForgotPasswordModal'
import { ResetPasswordModal } from './components/auth/ResetPasswordModal'
import { ChatInput } from './components/chat/ChatInput'
import { LoadingIndicator } from './components/chat/LoadingIndicator'
import { MessageList } from './components/chat/MessageList'
import { SamplePrompts } from './components/chat/SamplePrompts'
import { Header } from './components/layout/Header'
import { Sidebar } from './components/layout/Sidebar'
import { useChatEngine } from './hooks/useChatEngine'
import { useAuth } from './providers/AuthProvider'
import { APP_METADATA } from './config'

export default function App() {
  const { isAuthenticated, initializing } = useAuth()
  const {
    messages,
    isSending,
    sessions,
    currentSession,
    sessionsLoading,
    sendMessage,
    startNewSession,
    loadSession,
  } = useChatEngine()

  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [forgotPasswordModalOpen, setForgotPasswordModalOpen] = useState(false)
  const [resetPasswordModalOpen, setResetPasswordModalOpen] = useState(false)
  const [resetToken, setResetToken] = useState<string | null>(null)
  const [inputValue, setInputValue] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Check for reset token in URL on mount
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const token = urlParams.get('token')
    if (token) {
      setResetToken(token)
      setResetPasswordModalOpen(true)
      // Clean up URL
      window.history.replaceState({}, document.title, window.location.pathname)
    }
  }, [])

  const handleSendMessage = async (message: string) => {
    await sendMessage(message)
    setInputValue('')
    textareaRef.current?.focus()
  }

  const handleSelectPrompt = (prompt: string) => {
    setInputValue(prompt)
    setTimeout(() => {
      textareaRef.current?.focus()
    }, 0)
  }

  const showSamplePrompts = useMemo(
    () => !isAuthenticated && messages.length === 0,
    [isAuthenticated, messages.length],
  )

  return (
    <div className={`app-container ${isAuthenticated ? 'authenticated' : ''}`}>
      <Sidebar
        isOpen={isAuthenticated}
        sessions={sessions}
        currentSessionId={currentSession?.id}
        onStartNewChat={startNewSession}
        onSelectSession={(session) => {
          void loadSession(session)
        }}
        isLoading={sessionsLoading}
      />

      <div className="landing-page">
        <Header
          onSignIn={() => {
            setAuthMode('login')
            setAuthModalOpen(true)
          }}
          onRegister={() => {
            setAuthMode('register')
            setAuthModalOpen(true)
          }}
        />

        <main className="main-content">
          <div
            className={`chat-container ${
              isAuthenticated ? 'with-sidebar' : ''
            }`}
          >
            <MessageList messages={messages} />

            <LoadingIndicator isVisible={isSending} />

            <ChatInput
              ref={textareaRef}
              value={inputValue}
              onChange={setInputValue}
              onSend={handleSendMessage}
              isSending={isSending || initializing}
              placeholder={
                isAuthenticated
                  ? 'Document the case details to continue the session…'
                  : 'Welcome to HealthNavy! How can I assist you today?'
              }
            />

            {!isAuthenticated && messages.length === 0 && (
              <div className="disclaimer-section">
                <div className="disclaimer">
                  <i className="fas fa-info-circle" />
                  <span>
                    This platform provides clinical decision support for trained professionals and does not replace independent clinical judgment.
                  </span>
                </div>
              </div>
            )}

            <SamplePrompts
              hidden={!showSamplePrompts}
              onSelectPrompt={handleSelectPrompt}
            />
          </div>
        </main>

        <footer className="footer">
          <div className="footer-content">
            <div className="footer-brand">
              <div className="footer-logo">
                <span className="logo-health">Health</span>
                <span className="logo-navy">Navy</span>
              </div>
            </div>
            <div className="footer-copyright">
              <span>&copy; {new Date().getFullYear()} {APP_METADATA.fullName}. All rights reserved.</span>
            </div>
            <div className="footer-links">
              <button
                className="link-button"
                onClick={() =>
                  window.alert(
                    'Terms of Service: HealthNavy AI is designed to support clinical decision-making and should not replace professional medical judgment.',
                  )
                }
              >
                Terms of Service
              </button>
              <button
                className="link-button"
                onClick={() =>
                  window.alert(
                    'Privacy Policy: HealthNavy AI encrypts and protects your data, complying with healthcare privacy regulations.',
                  )
                }
              >
                Privacy Policy
              </button>
              <button
                className="link-button"
                onClick={() =>
                  window.alert(
                    'Support: Contact support@healthnavyai.com for assistance or visit our help center.',
                  )
                }
              >
                Support
              </button>
            </div>
          </div>
        </footer>
      </div>

      <AuthModal
        isOpen={authModalOpen}
        mode={authMode}
        onClose={() => setAuthModalOpen(false)}
        onSwitchMode={(mode) => setAuthMode(mode)}
        onForgotPassword={() => {
          setAuthModalOpen(false)
          setForgotPasswordModalOpen(true)
        }}
      />

      <ForgotPasswordModal
        isOpen={forgotPasswordModalOpen}
        onClose={() => setForgotPasswordModalOpen(false)}
        onBackToLogin={() => {
          setForgotPasswordModalOpen(false)
          setAuthMode('login')
          setAuthModalOpen(true)
        }}
      />

      {resetToken && (
        <ResetPasswordModal
          isOpen={resetPasswordModalOpen}
          token={resetToken}
          onClose={() => {
            setResetPasswordModalOpen(false)
            setResetToken(null)
          }}
          onSuccess={() => {
            setResetPasswordModalOpen(false)
            setResetToken(null)
            setAuthMode('login')
            setAuthModalOpen(true)
          }}
        />
      )}
    </div>
  )
}

