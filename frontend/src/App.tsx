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
  const { isAuthenticated, initializing, refreshProfile } = useAuth()
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
  const [isDeepSearchEnabled, setIsDeepSearchEnabled] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Check for reset token or OAuth callback in URL on mount
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const path = window.location.pathname
    
    // Handle password reset token
    const resetToken = urlParams.get('token')
    if (resetToken && path.includes('reset-password')) {
      setResetToken(resetToken)
      setResetPasswordModalOpen(true)
      window.history.replaceState({}, document.title, window.location.pathname)
      return
    }
    
    // Handle Google OAuth success
    if (path.includes('/auth/google/success')) {
      const oauthToken = urlParams.get('token')
      console.log('OAuth success callback - token received:', oauthToken ? 'yes' : 'no')
      if (oauthToken) {
        // Store token first
        localStorage.setItem('healthnavi.accessToken', oauthToken)
        console.log('OAuth token stored in localStorage')
        
        // Clean up URL immediately
        window.history.replaceState({}, document.title, '/')
        
        // Small delay to ensure localStorage is written, then refresh profile
        setTimeout(() => {
          refreshProfile()
            .then(() => {
              console.log('Profile refreshed successfully after OAuth login - user should be authenticated now')
              // Profile refreshed, user should now be authenticated
              // The component will re-render with isAuthenticated=true
            })
            .catch((error) => {
              console.error('Failed to refresh profile after OAuth login:', error)
              // If refresh fails, reload as fallback to trigger AuthProvider initialization
              console.log('Reloading page as fallback...')
              window.location.reload()
            })
        }, 100)
      } else {
        console.warn('OAuth success callback but no token in URL')
        // No token, just clean up URL
        window.history.replaceState({}, document.title, '/')
      }
      return
    }
    
    // Handle Google OAuth error
    if (path.includes('/auth/google/error')) {
      // const error = urlParams.get('error') || 'Authentication failed'
      setAuthMode('login')
      setAuthModalOpen(true)
      // Show error message (you might want to add error state to AuthModal)
      window.history.replaceState({}, document.title, '/')
      return
    }
  }, [refreshProfile])

  const handleSendMessage = async (message: string) => {
    await sendMessage({
      message,
      deepSearch: isDeepSearchEnabled,
    })
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

  const chatArea = (
    <div
      className={`chat-container ${isAuthenticated ? 'with-sidebar' : ''}`}
    >
      <MessageList messages={messages} />

      <LoadingIndicator isVisible={isSending} />

      <ChatInput
        ref={textareaRef}
        value={inputValue}
        onChange={setInputValue}
        onSend={handleSendMessage}
        isSending={isSending || initializing}
        isDeepSearchEnabled={isDeepSearchEnabled}
        onToggleDeepSearch={() =>
          setIsDeepSearchEnabled((previous) => !previous)
        }
        placeholder={
          isAuthenticated
            ? 'Welcome to HealthNavy! How can I assist you today?'
            : 'Welcome to HealthNavy! How can I assist you today?'
        }
      />

      {isAuthenticated && (
        <div className="authenticated-disclaimer">
          <i className="fas fa-info-circle" aria-hidden="true" />
          <span>
            HealthNavy offers AI-assisted clinical decision support. Always verify
            outputs with your professional judgment and institutional protocols.
          </span>
        </div>
      )}

      {!isAuthenticated && messages.length === 0 && (
        <div className="disclaimer-section">
          <div className="disclaimer">
            <i className="fas fa-info-circle" />
            <span>
              This platform provides clinical decision support for trained
              professionals and does not replace independent clinical judgment.
            </span>
          </div>
        </div>
      )}

      <SamplePrompts
        hidden={!showSamplePrompts}
        onSelectPrompt={handleSelectPrompt}
      />
    </div>
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

      <div className="main-area">
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

        {isAuthenticated ? (
          <main className="main-content">{chatArea}</main>
        ) : (
          <div className="landing-page">
            <main className="main-content">{chatArea}</main>

            <footer className="footer">
              <div className="footer-content">
                <div className="footer-brand">
                  <div className="footer-logo">
                    <span className="logo-health">Health</span>
                    <span className="logo-navy">Navy</span>
                  </div>
                </div>
                <div className="footer-copyright">
                  <span>
                    &copy; {new Date().getFullYear()} {APP_METADATA.fullName}. All
                    rights reserved.
                  </span>
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
        )}
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

