import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { AuthModal, type AuthMode } from '../components/auth/AuthModal'
import { ForgotPasswordModal } from '../components/auth/ForgotPasswordModal'
import { ResetPasswordModal } from '../components/auth/ResetPasswordModal'
import { ProfessionalTypeModal } from '../components/ProfessionalTypeModal'
import { ChatInput } from '../components/chat/ChatInput'
import { LoadingIndicator } from '../components/chat/LoadingIndicator'
import { MessageList } from '../components/chat/MessageList'
import { SamplePrompts } from '../components/chat/SamplePrompts'
import { Header } from '../components/layout/Header'
import { Sidebar } from '../components/layout/Sidebar'
import { useChatEngine } from '../hooks/useChatEngine'
import { useAuth } from '../providers/AuthProvider'
import { useChatStore } from '../store/useChatStore'
import { APP_METADATA, STORAGE_KEYS } from '../config'
import { Link } from 'react-router-dom'

export default function HomePage() {
  const { isAuthenticated, initializing, refreshProfile, user } = useAuth()
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
  
  const isFetchingFollowup = useChatStore((state) => state.isFetchingFollowup)

  const [authModalOpen, setAuthModalOpen] = useState(false)
  const [authMode, setAuthMode] = useState<AuthMode>('login')
  const [forgotPasswordModalOpen, setForgotPasswordModalOpen] = useState(false)
  const [resetPasswordModalOpen, setResetPasswordModalOpen] = useState(false)
  const [resetToken, setResetToken] = useState<string | null>(null)
  const [professionalTypeModalOpen, setProfessionalTypeModalOpen] = useState(false)
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
      console.log('[OAuth] Success callback detected')
      console.log('[OAuth] Path:', path)
      console.log('[OAuth] Token in URL:', oauthToken ? 'yes' : 'no')
      console.log('[OAuth] Full URL params:', Object.fromEntries(urlParams.entries()))
      
      if (oauthToken) {
        console.log('[OAuth] Token length:', oauthToken.length)
        // Store token immediately
        localStorage.setItem(STORAGE_KEYS.accessToken, oauthToken)
        console.log('OAuth token stored in localStorage')
        
        // Clear URL parameters
        window.history.replaceState({}, document.title, '/')
        
        // Refresh profile with retry logic
        const refreshWithRetry = async (retries = 3, delay = 500) => {
          for (let i = 0; i < retries; i++) {
            try {
              console.log(`Attempting to refresh profile (attempt ${i + 1}/${retries})...`)
              await refreshProfile()
              console.log('Profile refreshed successfully after OAuth login')
              // The professional type modal will show automatically if needed
              // via the useEffect hook that checks for medical_professional_type
              return // Success, exit retry loop
            } catch (error: any) {
              console.error(`Profile refresh attempt ${i + 1} failed:`, error)
              if (i < retries - 1) {
                // Wait before retrying
                await new Promise(resolve => setTimeout(resolve, delay))
                delay *= 2 // Exponential backoff
              } else {
                // All retries failed
                console.error('All profile refresh attempts failed after OAuth login')
                // Check if token is still in localStorage
                const storedToken = localStorage.getItem(STORAGE_KEYS.accessToken)
                if (storedToken === oauthToken) {
                  // Token is still there, might be a temporary server issue
                  // Force a page reload to let AuthProvider re-initialize
                  console.log('Reloading page to re-initialize auth state...')
                  window.location.reload()
                } else {
                  // Token was cleared, show login
                  setAuthMode('login')
                  setAuthModalOpen(true)
                }
              }
            }
          }
        }
        
        // Start refresh with retry
        setTimeout(() => {
          refreshWithRetry()
        }, 200) // Small delay to ensure localStorage is updated
        
        // Dispatch custom event to notify AuthProvider of the token change
        // This ensures the AuthProvider picks up the new token in the same window
        if (typeof window !== 'undefined') {
          window.dispatchEvent(new CustomEvent('auth-token-updated'))
        }
      } else {
        console.warn('OAuth success callback but no token in URL')
        window.history.replaceState({}, document.title, '/')
        setAuthMode('login')
        setAuthModalOpen(true)
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

  // Show professional type modal on first login if not set
  useEffect(() => {
    // Only open modal if user doesn't have medical_professional_type and modal is not already open
    if (
      !initializing &&
      isAuthenticated &&
      user &&
      !user.medical_professional_type &&
      !professionalTypeModalOpen
    ) {
      setProfessionalTypeModalOpen(true)
    }
    // If user now has medical_professional_type, ensure modal is closed
    // This prevents the modal from reopening after a successful update
    if (user?.medical_professional_type && professionalTypeModalOpen) {
      setProfessionalTypeModalOpen(false)
    }
  }, [initializing, isAuthenticated, user?.medical_professional_type, professionalTypeModalOpen])

  const handleSendMessage = async (message: string) => {
    setFollowupQuestions([])
    setInputValue('')
    try {
      const result = await sendMessage({
        message,
        sessionId: currentSession?.id,
        deepSearch: isDeepSearchEnabled,
      })
      if (result && 'followupQuestions' in result && result.followupQuestions) {
        setFollowupQuestions(result.followupQuestions)
      }
    } catch (error) {
      console.error('Error sending message:', error)
    }
  }

  const handleSelectPrompt = useCallback(
    (prompt: string) => {
      setInputValue(prompt)
      textareaRef.current?.focus()
    },
    [],
  )

  const handleToggleSidebar = useCallback(() => {
    setMobileMenuOpen((prev) => !prev)
  }, [])

  const handleCloseSidebar = useCallback(() => {
    setMobileMenuOpen(false)
  }, [])

  const hasMessages = messages.length > 0
  const showSamplePrompts = !hasMessages && !isSending
  const [hasStartedChat, setHasStartedChat] = useState(false)

  useEffect(() => {
    if (hasMessages && !hasStartedChat) {
      setHasStartedChat(true)
    }
  }, [hasMessages, hasStartedChat])

  const showSidebar = isAuthenticated || (hasStartedChat && hasMessages)
  const showSidebarForGuest = !isAuthenticated && hasStartedChat && hasMessages

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
            setMobileMenuOpen(false)
          }}
          isLoading={sessionsLoading}
          onHomeClick={() => {
            startNewSession()
            setFollowupQuestions([])
            setInputValue('')
            setMobileMenuOpen(false)
            if (!isAuthenticated) {
              setHasStartedChat(false)
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
            startNewSession()
            setFollowupQuestions([])
            setInputValue('')
            if (!isAuthenticated) {
              setHasStartedChat(false)
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
                placeholder="Ask me a medical question ..."
              />
            </div>

            {/* Patient Privacy Notice - Right below input */}
            <div className="privacy-notice">
              <i className="fas fa-lock" />
              <span>Please do not include patient identifying information.</span>
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
                    ? 'For healthcare professionals only: guidance is informational and not a substitute for clinical judgment.'
                    : 'For healthcare professionals only: guidance is informational and not a substitute for clinical judgment.'}
                </span>
              </div>
            )}

            {/* Disclaimer - Right under input area when there are messages */}
            {!showSamplePrompts && (
              <div className="disclaimer-bar">
                <i className="fas fa-shield-alt" />
                <span>
                  {isAuthenticated
                    ? 'For healthcare professionals only: guidance is informational and not a substitute for clinical judgment.'
                    : 'For healthcare professionals only: guidance is informational and not a substitute for clinical judgment.'}
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
                <Link to="/terms" className="footer-link">
                  Terms
                </Link>
                <span className="footer-divider">•</span>
                <Link to="/privacy" className="footer-link">
                  Privacy
                </Link>
                <span className="footer-divider">•</span>
                <button
                  className="footer-link"
                  onClick={() =>
                    window.alert(
                      'Support: Contact empiricoai26@gmail.com for assistance or visit our help center.',
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

      {professionalTypeModalOpen && (
        <ProfessionalTypeModal
          isOpen={professionalTypeModalOpen}
          onClose={() => setProfessionalTypeModalOpen(false)}
        />
      )}
    </div>
  )
}

