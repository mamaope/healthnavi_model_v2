import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
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
  const [followupQuestions, setFollowupQuestions] = useState<string[]>([])
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Check for reset token or OAuth callback in URL on mount
  useEffect(() => {
    const urlParams = new URLSearchParams(window.location.search)
    const path = window.location.pathname
    
    // Handle password reset token (can be in URL params or path)
    const resetToken = urlParams.get('token')
    if (resetToken) {
      setResetToken(resetToken)
      setResetPasswordModalOpen(true)
      // Clean URL but keep pathname
      const cleanPath = path.includes('reset-password') ? '/' : window.location.pathname
      window.history.replaceState({}, document.title, cleanPath)
      return
    }
    
    // Handle Google OAuth success
    if (path.includes('/auth/google/success')) {
      const oauthToken = urlParams.get('token')
      console.log('OAuth success callback - token received:', oauthToken ? 'yes' : 'no')
      if (oauthToken) {
        localStorage.setItem('healthnavi.accessToken', oauthToken)
        console.log('OAuth token stored in localStorage')
        
        window.history.replaceState({}, document.title, '/')
        
        setTimeout(() => {
          refreshProfile()
            .then(() => {
              console.log('Profile refreshed successfully after OAuth login')
            })
            .catch((error) => {
              console.error('Failed to refresh profile after OAuth login:', error)
              console.log('Reloading page as fallback...')
              window.location.reload()
            })
        }, 100)
      } else {
        console.warn('OAuth success callback but no token in URL')
        window.history.replaceState({}, document.title, '/')
      }
      return
    }
    
    // Handle Google OAuth error
    if (path.includes('/auth/google/error')) {
      setAuthMode('login')
      setAuthModalOpen(true)
      window.history.replaceState({}, document.title, '/')
      return
    }
  }, [refreshProfile])

  const handleSendMessage = async (message: string) => {
    setFollowupQuestions([])
    try {
      const result = await sendMessage({
        message,
        deepSearch: isDeepSearchEnabled,
      })
      setInputValue('')
      if (result && result.followupQuestions) {
        setFollowupQuestions(result.followupQuestions)
      }
    } catch (error) {
      console.error('Error sending message:', error)
    }
    textareaRef.current?.focus()
  }

  const handleSelectPrompt = (prompt: string) => {
    setInputValue(prompt)
    setTimeout(() => {
      textareaRef.current?.focus()
    }, 0)
  }

  const showSamplePrompts = useMemo(
    () => messages.length === 0,
    [messages.length],
  )

  const hasMessages = messages.length > 0
  // Show sidebar for authenticated users OR guests who have started a chat (even if messages cleared via New Chat)
  const [hasStartedChat, setHasStartedChat] = useState(false)
  
  // Track when user starts their first chat
  useEffect(() => {
    if (hasMessages && !hasStartedChat) {
      setHasStartedChat(true)
    }
  }, [hasMessages, hasStartedChat])
  
  const showSidebarForGuest = !isAuthenticated && (hasMessages || hasStartedChat)
  const showSidebar = isAuthenticated || showSidebarForGuest

  // Memoize sidebar handlers to prevent unnecessary re-renders
  const handleCloseSidebar = useCallback(() => {
    setMobileMenuOpen(false)
  }, [])

  const handleToggleSidebar = useCallback(() => {
    setMobileMenuOpen((prev) => !prev)
  }, [])

  return (
    <div className={`app-wrapper ${isAuthenticated ? 'authenticated' : 'guest'}`}>
      {/* Sidebar - Only visible when authenticated */}
      {isAuthenticated && (
        <Sidebar
          isOpen={isAuthenticated}
          sessions={sessions}
          currentSessionId={currentSession?.id}
          onStartNewChat={startNewSession}
          onSelectSession={(session) => {
            void loadSession(session)
          }}
          isLoading={sessionsLoading}
          onHomeClick={() => {
            // Return to home screen by clearing everything
            startNewSession()
            setFollowupQuestions([])
            setInputValue('')
            setMobileMenuOpen(false)
            if (!isAuthenticated) {
              setHasStartedChat(false) // Reset to show home page without sidebar for guests
            }
          }}
        />
      )}

      {/* Main Content Area */}
      <div className="main-layout">
        {/* Header */}
        <Header
          onSignIn={() => {
            setAuthMode('login')
            setAuthModalOpen(true)
          }}
          onRegister={() => {
            setAuthMode('register')
            setAuthModalOpen(true)
          }}
          onHomeClick={() => {
            // Return to home screen by clearing everything
            startNewSession()
            setFollowupQuestions([])
            setInputValue('')
            if (!isAuthenticated) {
              setHasStartedChat(false) // Reset to show home page without sidebar for guests
            }
          }}
        />

        {/* Chat Container */}
        <main className="chat-main">
          <div className={`chat-wrapper ${hasMessages ? 'has-messages' : 'empty'}`}>
            {/* Messages Area */}
            <div className="messages-container">
              <MessageList messages={messages} />
              {/* Show loading indicator when sending */}
              <LoadingIndicator isVisible={isSending} />
              
              {/* Follow-up Questions - Below model response */}
              {followupQuestions && followupQuestions.length > 0 && messages.length > 0 && (
                <div className="followup-section">
                  <div className="followup-header">
                    <i className="fas fa-lightbulb" />
                    <span>Suggested Questions</span>
                  </div>
                  <div className="followup-grid">
                    {followupQuestions.map((question, index) => (
                      <button
                        key={index}
                        type="button"
                        className="followup-card"
                        onClick={() => {
                          setInputValue(question)
                          setFollowupQuestions([])
                          textareaRef.current?.focus()
                        }}
                      >
                        <i className="fas fa-arrow-right" />
                        <span>{question}</span>
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>

            {/* Follow-up Questions */}
            {followupQuestions && followupQuestions.length > 0 && (
              <div className="followup-section">
                <div className="followup-header">
                  <i className="fas fa-lightbulb" />
                  <span>Suggested Questions</span>
                </div>
                <div className="followup-grid">
                  {followupQuestions.map((question, index) => (
                    <button
                      key={index}
                      type="button"
                      className="followup-card"
                      onClick={() => {
                        setInputValue(question)
                        setFollowupQuestions([])
                        textareaRef.current?.focus()
                      }}
                    >
                      <i className="fas fa-arrow-right" />
                      <span>{question}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}

            {/* Input Area - Fixed at bottom */}
            <div className="input-section">
              {/* Logo - Only on homepage (no messages) */}
              {showSamplePrompts && (
                <div className="homepage-logo">
                  <img src="/logo.png" alt="Empirico" />
                </div>
              )}
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
                    ? 'Ask a clinical question, describe symptoms, or request guidance...'
                    : 'Ask a clinical question, describe symptoms, or request guidance...'
                }
              />
              {/* Disclaimer - Right under input area */}
              <div className="disclaimer-bar">
                <i className="fas fa-shield-alt" />
                <span>
                  {isAuthenticated
                    ? 'AI-assisted clinical decision support. Always verify with professional judgment and institutional protocols.'
                    : 'This platform provides clinical decision support for trained professionals and does not replace independent clinical judgment.'}
                </span>
              </div>
            </div>

            {/* Sample Prompts - Below disclaimer, only show when no messages */}
            {showSamplePrompts && (
              <div className="prompts-section">
                <SamplePrompts
                  hidden={false}
                  onSelectPrompt={handleSelectPrompt}
                />
              </div>
            )}
          </div>
        </main>

        {/* Footer - Only for guest users */}
        {!isAuthenticated && (
          <footer className="app-footer">
            <div className="footer-content">
              <div className="footer-links">
                <button
                  className="footer-link"
                  onClick={() =>
                    window.alert(
                      'Terms of Service: HealthNavy AI is designed to support clinical decision-making and should not replace professional medical judgment.',
                    )
                  }
                >
                  Terms
                </button>
                <span className="footer-divider">•</span>
                <button
                  className="footer-link"
                  onClick={() =>
                    window.alert(
                      'Privacy Policy: HealthNavy AI encrypts and protects your data, complying with healthcare privacy regulations.',
                    )
                  }
                >
                  Privacy
                </button>
                <span className="footer-divider">•</span>
                <button
                  className="footer-link"
                  onClick={() =>
                    window.alert(
                      'Support: Contact support@healthnavyai.com for assistance or visit our help center.',
                    )
                  }
                >
                  Support
                </button>
                <span className="footer-divider">•</span>
                <span className="footer-copyright">
                  &copy; {new Date().getFullYear()} {APP_METADATA.fullName}. All rights reserved.
                </span>
              </div>
            </div>
          </footer>
        )}
      </div>

      {/* Auth Modals */}
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
            // Ensure login modal is shown after closing reset password
            if (!isAuthenticated) {
              setAuthMode('login')
              setAuthModalOpen(true)
            }
          }}
          onSuccess={() => {
            setResetPasswordModalOpen(false)
            setResetToken(null)
            // Clear URL parameters
            window.history.replaceState({}, document.title, window.location.pathname)
            // Show login modal after successful reset
            setAuthMode('login')
            setAuthModalOpen(true)
          }}
        />
      )}
    </div>
  )
}
