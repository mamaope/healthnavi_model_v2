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
import { useChatStore } from './store/useChatStore'
import { APP_METADATA, STORAGE_KEYS } from './config'

export default function App() {
  const { isAuthenticated, initializing, refreshProfile } = useAuth()
  const {
    messages,
    isSending,
    // isStreaming,  // Commented out - streaming disabled
    sessions,
    currentSession,
    sessionsLoading,
    sendMessage,
    startNewSession,
    loadSession,
  } = useChatEngine()
  
  const isFetchingFollowup = useChatStore((state) => state.isFetchingFollowup)

  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [forgotPasswordModalOpen, setForgotPasswordModalOpen] = useState(false)
  const [resetPasswordModalOpen, setResetPasswordModalOpen] = useState(false)
  const [resetToken, setResetToken] = useState<string | null>(null)
  const [inputValue, setInputValue] = useState('')
  const [isDeepSearchEnabled, setIsDeepSearchEnabled] = useState(false)
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false)
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)
  const followupQuestions = useChatStore((state) => state.followupQuestions)
  const setFollowupQuestions = useChatStore((state) => state.setFollowupQuestions)
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
        localStorage.setItem(STORAGE_KEYS.accessToken, oauthToken)
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
    setInputValue('') // Clear input immediately when sending
    try {
      const result = await sendMessage({
        message,
        deepSearch: isDeepSearchEnabled,
      })
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

  // Show sample prompts when there are no messages
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
    <div className={`app-wrapper ${isAuthenticated ? 'authenticated' : 'guest'} ${showSidebarForGuest ? 'guest-with-sidebar' : ''} ${sidebarCollapsed ? 'sidebar-collapsed' : ''}`}>
      {/* Sidebar - Only visible when authenticated or guest with messages */}
      {showSidebar && (
        <Sidebar
          isOpen={mobileMenuOpen}
          isCollapsed={sidebarCollapsed}
          onToggleCollapse={() => setSidebarCollapsed(!sidebarCollapsed)}
          sessions={sessions}
          currentSessionId={currentSession?.id}
          onStartNewChat={startNewSession}
          onSelectSession={(session) => {
            void loadSession(session)
            setMobileMenuOpen(false) // Close mobile menu after selecting
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
          onClose={handleCloseSidebar}
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
          onMenuToggle={handleToggleSidebar}
          showMenuButton={showSidebar}
        />

        {/* Chat Container */}
        <main className="chat-main">
          <div className={`chat-wrapper ${hasMessages ? 'has-messages' : 'empty'}`}>
            {/* Messages Area */}
            <div className="messages-container">
              <MessageList messages={messages} />
              {/* Show loading indicator when sending or fetching follow-up questions */}
              <LoadingIndicator isVisible={isSending || isFetchingFollowup} />
              
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

            <div className="input-section">
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
                placeholder="Ask a clinical question, describe symptoms, or request guidance..."
              />
            </div>

            {showSamplePrompts && (
              <div className="prompts-section">
                <SamplePrompts
                  hidden={false}
                  onSelectPrompt={handleSelectPrompt}
                />
              </div>
            )}

            {showSamplePrompts && (
              <div className="disclaimer-bar-bottom">
                <i className="fas fa-shield-alt" />
                <span>
                  {isAuthenticated
                    ? 'AI-assisted clinical decision support. Always verify with professional judgment and institutional protocols.'
                    : 'This platform provides clinical decision support for trained professionals and does not replace independent clinical judgment.'}
                </span>
              </div>
            )}

            {/* Disclaimer - Right under input area when there are messages */}
            {!showSamplePrompts && (
              <div className="disclaimer-bar">
                <i className="fas fa-shield-alt" />
                <span>
                  {isAuthenticated
                    ? 'AI-assisted clinical decision support. Always verify with professional judgment and institutional protocols.'
                    : 'This platform provides clinical decision support for trained professionals and does not replace independent clinical judgment.'}
                </span>
              </div>
            )}
          </div>
        </main>

        {/* Footer  */}
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
