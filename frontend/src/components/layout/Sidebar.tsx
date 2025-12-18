import { useMemo } from 'react'
import { useAuth } from '../../providers/AuthProvider'
import type { ChatSession } from '../../types/chat'

interface SidebarProps {
  isOpen: boolean
  sessions: ChatSession[]
  currentSessionId?: string | null
  onStartNewChat: () => void
  onSelectSession: (session: ChatSession) => void
  isLoading?: boolean
  onHomeClick?: () => void
}

export function Sidebar({
  isOpen,
  sessions,
  currentSessionId,
  onStartNewChat,
  onSelectSession,
  isLoading,
  onHomeClick,
}: SidebarProps) {
  const { isAuthenticated } = useAuth()

  const hasSessions = sessions.length > 0

  const sidebarClass = useMemo(
    () => `modern-sidebar ${isOpen ? 'open' : ''}`,
    [isOpen],
  )

  if (!isAuthenticated) {
    return null
  }

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

  const getSessionPreview = (session: ChatSession) => {
    // Extract first message or use default
    if (session.messages && session.messages.length > 0) {
      const firstMessage = session.messages[0]?.content || ''
      return firstMessage.length > 50 
        ? firstMessage.substring(0, 50) + '...' 
        : firstMessage
    }
    return 'New conversation'
  }

  return (
    <aside className={sidebarClass}>
      <div className="sidebar-header">
        <div className="sidebar-brand">
          <div 
            className="sidebar-logo" 
            onClick={onHomeClick}
            style={{ cursor: onHomeClick ? 'pointer' : 'default' }}
          >
            <img 
              src="/logo.png" 
              alt="Empirico" 
              className="logo-image"
            />
          </div>
        </div>
        <button className="btn-new-chat" onClick={onStartNewChat}>
          <i className="fas fa-plus" />
          <span>New Chat</span>
        </button>
      </div>

      <div className="sidebar-content">
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
                    {getSessionPreview(session)}
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
      </div>
    </aside>
  )
}
