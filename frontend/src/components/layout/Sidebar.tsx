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
  const { isAuthenticated, logout } = useAuth()

  const hasSessions = sessions.length > 0

  const sidebarClass = useMemo(
    () => `sidebar ${isOpen ? 'open' : ''}`,
    [isOpen],
  )

  if (!isAuthenticated) {
    return null
  }

  return (
    <aside className={sidebarClass}>
      <div className="sidebar-header">
        <div className="sidebar-logo">
          <h2 
            className="welcome-logo" 
            onClick={onHomeClick}
            style={{ cursor: onHomeClick ? 'pointer' : 'default' }}
          >
            <span className="logo-health">Health</span>
            <span className="logo-navy">Navy</span>
          </h2>
        </div>
        <button className="btn-new-chat" onClick={onStartNewChat}>
          <i className="fas fa-plus" />
          <span>New Chat</span>
        </button>
      </div>

      <div className="sidebar-content">
        <div className="sessions-header">
          <h3>Sessions</h3>
        </div>
        <div className="sessions-list">
          {isLoading && (
            <div className="sessions-loading">
              <i className="fas fa-spinner fa-spin" />
              <span>Loading sessions…</span>
            </div>
          )}
          {!isLoading && !hasSessions && (
            <div className="empty-state">
              <i className="fas fa-comments" />
              <p>No conversations yet</p>
              <small>Start a new chat to begin</small>
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
                <div className="session-name">
                  Session {session.id}
                </div>
                <div className="session-date">
                  {new Date(session.created_at).toLocaleDateString()}
                </div>
              </button>
            ))}
        </div>
      </div>

      <div className="sidebar-footer">
        <button className="btn-logout btn-logout-full" onClick={logout}>
          <i className="fas fa-sign-out-alt" />
          <span>Sign Out</span>
        </button>
      </div>
    </aside>
  )
}

