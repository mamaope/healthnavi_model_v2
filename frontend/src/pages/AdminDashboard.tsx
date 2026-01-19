import { useEffect, useState } from 'react'
import { useAuth } from '../providers/AuthProvider'
import { adminApi } from '../services/apiClient'
import { useNavigate } from 'react-router-dom'
import UsagePanel from '../components/admin/UsagePanel'
import UserTypeBreakdownPanel from '../components/admin/UserTypeBreakdownPanel'
import UserManagementPanel from '../components/admin/UserManagementPanel'
import SessionManagementPanel from '../components/admin/SessionManagementPanel'
import AIResponseStatisticsPanel from '../components/admin/AIResponseStatisticsPanel'
import './AdminDashboard.css'

export default function AdminDashboard() {
  const { user, isAuthenticated, initializing } = useAuth()
  const navigate = useNavigate()
  const [metrics, setMetrics] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [days, setDays] = useState(30)

  useEffect(() => {
    // Wait for auth to initialize before checking
    if (initializing) {
      return
    }

    // Check if user is admin
    if (!isAuthenticated) {
      navigate('/')
      return
    }

    if (user && !['admin', 'super_admin'].includes(user.role)) {
      navigate('/')
      return
    }

    // Only load data if user is authenticated and has admin role
    if (isAuthenticated && user && ['admin', 'super_admin'].includes(user.role)) {
      loadMetrics()
      
      // Auto-refresh every 5 minutes
      const interval = setInterval(() => {
        loadMetrics()
      }, 5 * 60 * 1000)

      return () => clearInterval(interval)
    }
  }, [isAuthenticated, user, initializing, days, navigate])

  const loadMetrics = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await adminApi.getMetrics(days)
      if (response.success) {
        setMetrics(response.data)
      } else {
        setError('Failed to load metrics')
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load metrics')
    } finally {
      setLoading(false)
    }
  }


  // Show loading while auth initializes
  if (initializing) {
    return (
      <div className="admin-dashboard">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading...</p>
        </div>
      </div>
    )
  }

  // Redirect if not authenticated or not admin
  if (!isAuthenticated || !user || !['admin', 'super_admin'].includes(user.role)) {
    return null
  }

  return (
    <div className="admin-dashboard">
      <header className="admin-header">
        <div className="admin-header-content">
          <h1>Admin Dashboard</h1>
          <div className="admin-header-actions">
            <select 
              value={days} 
              onChange={(e) => setDays(Number(e.target.value))}
              className="period-selector"
            >
              <option value={7}>Last 7 days</option>
              <option value={30}>Last 30 days</option>
              <option value={90}>Last 90 days</option>
              <option value={365}>Last year</option>
            </select>
            <button onClick={() => navigate('/')} className="btn-back">
              Back to Chat
            </button>
          </div>
        </div>
      </header>

      {loading && !metrics && (
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading metrics...</p>
        </div>
      )}

      {error && (
        <div className="error-container">
          <p>Error: {error}</p>
          <button onClick={loadMetrics}>Retry</button>
        </div>
      )}

      {metrics && (
        <div className="admin-panels">
          <UserTypeBreakdownPanel days={days} />
          <UsagePanel metrics={metrics.usage} days={days} />
          <SessionManagementPanel days={days} />
          <AIResponseStatisticsPanel days={days} />
          <UserManagementPanel days={days} />
        </div>
      )}
    </div>
  )
}
