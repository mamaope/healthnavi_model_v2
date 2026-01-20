import { useEffect } from 'react'
import { Outlet, useNavigate, useLocation, NavLink } from 'react-router-dom'
import { useAuth } from '../../providers/AuthProvider'
import './SettingsPage.css'

const NAV_ITEMS = [
  { path: '/settings/profile', label: 'Profile', icon: 'fa-user' },
  { path: '/settings/billing', label: 'Billing', icon: 'fa-credit-card' },
  { path: '/settings/privacy', label: 'Privacy & Data', icon: 'fa-shield-alt' },
  { path: '/settings/close-account', label: 'Close Account', icon: 'fa-user-times' },
] as const

export default function SettingsPage() {
  const { isAuthenticated, initializing } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  useEffect(() => {
    if (initializing) return
    if (!isAuthenticated) {
      navigate('/', { replace: true })
      return
    }
  }, [isAuthenticated, initializing, navigate])

  if (initializing) {
    return (
      <div className="settings-page">
        <div className="settings-layout" style={{ flexDirection: 'column', justifyContent: 'center', alignItems: 'center', minHeight: '300px', gap: '1rem' }}>
          <div className="spinner" />
          <p style={{ margin: 0, color: 'var(--text-secondary)' }}>Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return null
  }

  return (
    <div className="settings-page">
      <div className="settings-header-bar">
        <button type="button" className="btn-back" onClick={() => navigate('/')}>
          ← Back to Chat
        </button>
      </div>
      <div className="settings-layout">
        <nav className="settings-nav">
          <h2>Settings</h2>
          <ul className="settings-nav-list">
            {NAV_ITEMS.map(({ path, label, icon }) => (
              <li key={path} className="settings-nav-item">
                <NavLink
                  to={path}
                  className={({ isActive }) =>
                    `settings-nav-link ${isActive || (path === '/settings/profile' && location.pathname === '/settings') ? 'active' : ''}`
                  }
                  end={path === '/settings/profile'}
                >
                  <i className={`fas ${icon}`} />
                  <span>{label}</span>
                </NavLink>
              </li>
            ))}
          </ul>
        </nav>
        <main className="settings-content">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
