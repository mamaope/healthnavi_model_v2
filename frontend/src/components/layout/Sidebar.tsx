import { useMemo, useEffect, useRef } from 'react'
import type { ChatSession } from '../../types/chat'

interface SidebarProps {
  isOpen: boolean
  isCollapsed: boolean
  onToggleCollapse: () => void
  sessions: ChatSession[]
  currentSessionId?: string | null
  onStartNewChat: () => void
  onSelectSession: (session: ChatSession) => void
  isLoading?: boolean
  onHomeClick?: () => void
  onClose?: () => void
}

export function Sidebar({
  isOpen,
  isCollapsed,
  onToggleCollapse,
  sessions,
  currentSessionId,
  onStartNewChat,
  onSelectSession,
  isLoading,
  onHomeClick,
  onClose,
}: SidebarProps) {
  const sidebarRef = useRef<HTMLElement>(null)

  const hasSessions = sessions.length > 0

  const sidebarClass = useMemo(
    () => {
      // On mobile, only add 'open' class if isOpen is true
      // On desktop, sidebar is always visible
      const isMobile = typeof window !== 'undefined' && window.innerWidth <= 768
      if (isMobile) {
        return `modern-sidebar ${isOpen ? 'open' : ''} ${isCollapsed ? 'collapsed' : ''}`
      }
      // Desktop: always show sidebar
      return `modern-sidebar open ${isCollapsed ? 'collapsed' : ''}`
    },
    [isOpen, isCollapsed],
  )
  
  // Close sidebar when clicking outside on mobile
  useEffect(() => {
    // Only on mobile screens (768px and below)
    if (typeof window === 'undefined' || window.innerWidth > 768) return
    if (!isOpen || !onClose) return

    const handleClickOutside = (event: MouseEvent | TouchEvent) => {
      const target = event.target as Node
      
      // Don't close if clicking inside the sidebar
      if (sidebarRef.current && sidebarRef.current.contains(target)) {
        return
      }
      
      // Don't close if clicking on the hamburger menu button
      const menuButton = document.querySelector('.mobile-menu-button')
      if (menuButton && menuButton.contains(target)) {
        return
      }
      
      // Close sidebar when clicking outside
      onClose()
    }

    // Add a small delay to avoid immediate closure when opening
    // This prevents the same click that opens the menu from also closing it
    const timeoutId = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside, true)
      document.addEventListener('touchstart', handleClickOutside as any, true)
    }, 150)

    return () => {
      clearTimeout(timeoutId)
      document.removeEventListener('mousedown', handleClickOutside, true)
      document.removeEventListener('touchstart', handleClickOutside as any, true)
    }
  }, [isOpen, onClose])

  const formatSessionDate = (date: Date | string) => {
    const d = typeof date === 'string' ? new Date(date) : date
    const now = new Date()
    const diffTime = Math.abs(now.getTime() - d.getTime())
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24))

    if (diffDays === 0) {
      return 'Today'
    } else if (diffDays === 1) {
      return 'Yesterday'
    } else if (diffDays < 7) {
      return `${diffDays} days ago`
    } else {
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
    }
  }

  const getSessionTitle = (session: ChatSession) => {
    // Backend updates it with first user message automatically
    if (session.session_name && !session.session_name.startsWith('Diagnosis Session')) {
      return session.session_name
    }
    
    return 'New conversation'
  }

  return (
    <aside ref={sidebarRef} className={sidebarClass}>
      <div className="sidebar-header">
        <div className="sidebar-header-top">
          <div className="sidebar-brand">
            <div 
              className="sidebar-logo" 
              onClick={onHomeClick}
              style={{ cursor: onHomeClick ? 'pointer' : 'default' }}
            >
              {!isCollapsed && (
                <img 
                  src="/logo.png" 
                  alt="Empirico" 
                  className="logo-image"
                />
              )}
            </div>
          </div>
          <button 
            className="btn-collapse-sidebar" 
            onClick={onToggleCollapse}
            title={isCollapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            <i className={`fas fa-${isCollapsed ? 'chevron-right' : 'chevron-left'}`} />
          </button>
        </div>
        {!isCollapsed && (
          <button className="btn-new-chat" onClick={onStartNewChat}>
            <i className="fas fa-plus" />
            <span>New Chat</span>
          </button>
        )}
        {isCollapsed && (
          <button className="btn-new-chat-collapsed" onClick={onStartNewChat} title="New Chat">
            <i className="fas fa-plus" />
          </button>
        )}
      </div>

      <div className="sidebar-content">
        {!isCollapsed && (
          <>
            <div className="sessions-header">
              <h3>Recent Conversations</h3>
            </div>
            <div className="sessions-list">
              {isLoading && (
                <div className="sessions-loading">
                  <i className="fas fa-spinner fa-spin" />
                  <span>Loading conversations…</span>
                </div>
              )}
              {!isLoading && !hasSessions && (
                <div className="empty-state">
                  <div className="empty-state-icon">
                    <i className="fas fa-comments" />
                  </div>
                  <p className="empty-state-title">No conversations yet</p>
                  <p className="empty-state-description">Start a new chat to begin your clinical consultation</p>
                </div>
              )}
              {!isLoading &&
                hasSessions &&
                sessions.map((session) => (
                  <button
                    key={session.id}
                    className={`session-item ${
                      currentSessionId === session.id ? 'active' : ''
                    }`}
                    onClick={() => onSelectSession(session)}
                  >
                    <div className="session-icon">
                      <i className="fas fa-comment-medical" />
                    </div>
                    <div className="session-content">
                      <div className="session-name">
                        {getSessionTitle(session)}
                      </div>
                      <div className="session-meta">
                        <span className="session-date">
                          {formatSessionDate(session.created_at)}
                        </span>
                      </div>
                    </div>
                  </button>
                ))}
            </div>
          </>
        )}
        {isCollapsed && (
          <div className="sessions-list-collapsed">
            {sessions.slice(0, 5).map((session) => (
              <button
                key={session.id}
                className={`session-item-collapsed ${
                  currentSessionId === session.id ? 'active' : ''
                }`}
                onClick={() => onSelectSession(session)}
                title={getSessionTitle(session)}
              >
                <i className="fas fa-comment-medical" />
              </button>
            ))}
          </div>
        )}
      </div>
    </aside>
  )
}
