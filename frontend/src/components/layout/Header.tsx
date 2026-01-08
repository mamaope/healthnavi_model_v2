import { useEffect, useRef, useState } from 'react'
import { useAuth } from '../../providers/AuthProvider'
import { ThemeToggle } from '../common/ThemeToggle'

interface HeaderProps {
  onSignIn: () => void
  onRegister: () => void
  onHomeClick?: () => void
}

export function Header({ onSignIn, onRegister, onHomeClick, onMenuToggle, showMenuButton = false }: HeaderProps) {
  const { isAuthenticated } = useAuth()
  const [isMenuOpen, setIsMenuOpen] = useState(false)
  const menuRef = useRef<HTMLDivElement>(null)

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
    <header className="modern-header">
      <div className="header-content">
        {showMenuButton && (
          <button 
            className="mobile-menu-button"
            onClick={onMenuToggle}
            aria-label="Toggle sidebar"
          >
            <i className="fas fa-bars" />
          </button>
        )}
        
        <div className="header-brand">
          <div 
            className="header-logo" 
            onClick={onHomeClick}
            style={{ cursor: onHomeClick ? 'pointer' : 'default' }}
          >
            <img 
              src="/logo.png" 
              alt="Empirico" 
              className="logo-image"
              onError={(e) => {
                const target = e.target as HTMLImageElement
                target.style.display = 'none'
                const parent = target.parentElement
                if (parent && !parent.querySelector('.logo-fallback')) {
                  const fallback = document.createElement('div')
                  fallback.className = 'logo-fallback'
                  fallback.innerHTML = '<span class="logo-text">Empirico</span>'
                  parent.appendChild(fallback)
                }
              }}
            />
          </div>
        </div>

        <div className="header-actions-wrapper">
          {!isAuthenticated && (
            <div className="header-actions">
              <button className="btn btn-outline" onClick={onSignIn}>
                Log In
              </button>
              <button className="btn btn-primary" onClick={onRegister}>
                Sign Up
              </button>
              <div className="header-menu-container" ref={menuRef}>
                <button 
                  className="header-hamburger-btn"
                  onClick={() => setIsMenuOpen((open) => !open)}
                  aria-label="More options"
                  aria-expanded={isMenuOpen}
                >
                  <i className="fas fa-bars" />
                </button>
                {isMenuOpen && (
                  <div className="header-menu-dropdown">
                    <div className="header-menu-theme-row">
                      <i className="fas fa-moon" />
                      <span>Dark Mode</span>
                      <ThemeToggle ariaLabel="Toggle light/dark theme" />
                    </div>
                    <div className="header-menu-divider" />
                    <button
                      className="header-menu-item"
                      onClick={() => {
                        setIsMenuOpen(false)
                        window.alert('Mobile app coming soon!')
                      }}
                    >
                      <i className="fas fa-mobile-alt" />
                      <span>Download App</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}

          {isAuthenticated && (
            <div className="header-user-section">
              <div className="header-menu-container" ref={menuRef}>
                <button 
                  className="header-hamburger-btn"
                  onClick={() => setIsMenuOpen((open) => !open)}
                  aria-label="More options"
                  aria-expanded={isMenuOpen}
                >
                  <i className="fas fa-bars" />
                </button>
                {isMenuOpen && (
                  <div className="header-menu-dropdown">
                    <div className="header-menu-theme-row">
                      <i className="fas fa-moon" />
                      <span>Dark Mode</span>
                      <ThemeToggle ariaLabel="Toggle light/dark theme" variant="header" />
                    </div>
                    <div className="header-menu-divider" />
                    <button
                      className="header-menu-item"
                      onClick={() => {
                        setIsMenuOpen(false)
                        window.alert('Mobile app coming soon!')
                      }}
                    >
                      <i className="fas fa-mobile-alt" />
                      <span>Download App</span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </header>
  )
}
