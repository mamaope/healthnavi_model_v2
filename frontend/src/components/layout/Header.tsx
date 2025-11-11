import { useEffect, useRef, useState } from 'react'
import { getDisplayName, getRoleLabel, useAuth } from '../../providers/AuthProvider'
import { ThemeToggle } from '../common/ThemeToggle'

interface HeaderProps {
  onSignIn: () => void
  onRegister: () => void
}

export function Header({ onSignIn, onRegister }: HeaderProps) {
  const { isAuthenticated, user, logout } = useAuth()
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

  const userName = getDisplayName(user)
  const userRole = getRoleLabel(user)

  useEffect(() => {
    if (!isMenuOpen) return

    const handleClickOutside = (event: MouseEvent) => {
      if (
        menuRef.current &&
        !menuRef.current.contains(event.target as Node)
      ) {
        setIsMenuOpen(false)
      }
    }

    document.addEventListener('click', handleClickOutside)
    return () => document.removeEventListener('click', handleClickOutside)
  }, [isMenuOpen])

  return (
    <header className="header">
      <div className="logo">
        <h1 className="welcome-logo">
          <span className="logo-health">Health</span>
          <span className="logo-navy">Navy</span>
        </h1>
      </div>

      {!isAuthenticated && (
        <div className="header-actions">
          <ThemeToggle ariaLabel="Toggle light/dark theme" />
          <button className="btn btn-outline" onClick={onSignIn}>
            Sign In
          </button>
          <button className="btn btn-primary" onClick={onRegister}>
            Get Started
          </button>
        </div>
      )}

      {isAuthenticated && (
        <div className="header-user-profile">
          <ThemeToggle ariaLabel="Toggle light/dark theme" variant="header" />
          <div className="header-user-menu" ref={menuRef}>
            <button
              className="header-user-button"
              onClick={() => setIsMenuOpen((open) => !open)}
              aria-haspopup="menu"
              aria-expanded={isMenuOpen}
            >
              <div className="header-user-avatar">
                <i className="fas fa-user-md" />
              </div>
              <div className="header-user-info">
                <span className="header-user-name">{userName}</span>
                <span className="header-user-role">{userRole}</span>
              </div>
              <i className="fas fa-chevron-down header-dropdown-icon" />
            </button>

            {isMenuOpen && (
              <div className="user-dropdown-menu" role="menu">
                <div className="user-dropdown-header">
                  <div className="user-dropdown-avatar">
                    <i className="fas fa-user-md" />
                  </div>
                  <div className="user-dropdown-info">
                    <div className="user-dropdown-name">{userName}</div>
                    <div className="user-dropdown-email">{user?.email}</div>
                  </div>
                </div>
                <div className="user-dropdown-divider" />
                <button
                  className="user-dropdown-item"
                  onClick={() => {
                    setIsMenuOpen(false)
                    window.alert('Profile page coming soon!')
                  }}
                >
                  <i className="fas fa-user" />
                  <span>My Profile</span>
                </button>
                <button
                  className="user-dropdown-item"
                  onClick={() => {
                    setIsMenuOpen(false)
                    window.alert('Settings page coming soon!')
                  }}
                >
                  <i className="fas fa-cog" />
                  <span>Settings</span>
                </button>
                <button
                  className="user-dropdown-item"
                  onClick={() => {
                    setIsMenuOpen(false)
                    window.alert('Help & Support coming soon!')
                  }}
                >
                  <i className="fas fa-question-circle" />
                  <span>Help & Support</span>
                </button>
                <div className="user-dropdown-divider" />
                <button
                  className="user-dropdown-item user-dropdown-item-danger"
                  onClick={() => {
                    setIsMenuOpen(false)
                    logout()
                  }}
                >
                  <i className="fas fa-sign-out-alt" />
                  <span>Sign Out</span>
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </header>
  )
}

