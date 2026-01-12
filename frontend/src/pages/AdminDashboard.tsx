import { useEffect, useState } from 'react'
import { useAuth } from '../providers/AuthProvider'
import { adminApi } from '../services/apiClient'
import { useNavigate } from 'react-router-dom'
import UsagePanel from '../components/admin/UsagePanel'
import ClinicalValuePanel from '../components/admin/ClinicalValuePanel'
import SafetyPanel from '../components/admin/SafetyPanel'
import PmfPanel from '../components/admin/PmfPanel'
import AlertsPanel from '../components/admin/AlertsPanel'
import './AdminDashboard.css'

export default function AdminDashboard() {
  const { user, isAuthenticated, initializing } = useAuth()
  const navigate = useNavigate()
  const [metrics, setMetrics] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [days, setDays] = useState(30)
  const [alerts, setAlerts] = useState<any[]>([])
  const [unreadAlertsCount, setUnreadAlertsCount] = useState(0)

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
      loadAlerts()
      
      // Auto-refresh every 5 minutes
      const interval = setInterval(() => {
        loadMetrics()
        loadAlerts()
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

  const loadAlerts = async () => {
    try {
      const response = await adminApi.getAlerts(true) // Get unread only
      if (response.success) {
        setAlerts(response.data.alerts)
        setUnreadAlertsCount(response.data.count)
      }
    } catch (err) {
      console.error('Failed to load alerts:', err)
    }
  }

  const handleCheckAlerts = async () => {
    try {
      await adminApi.checkAlerts()
      loadAlerts()
      loadMetrics() // Refresh metrics after checking alerts
    } catch (err) {
      console.error('Failed to check alerts:', err)
    }
  }

  const handleMarkAlertRead = async (alertId: number) => {
    try {
      await adminApi.markAlertRead(alertId)
      loadAlerts()
    } catch (err) {
      console.error('Failed to mark alert as read:', err)
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
            <button onClick={handleCheckAlerts} className="btn-check-alerts">
              Check Alerts
            </button>
            <button onClick={() => navigate('/')} className="btn-back">
              Back to Chat
            </button>
          </div>
        </div>
        {unreadAlertsCount > 0 && (
          <div className="alerts-banner">
            <span className="alerts-count">{unreadAlertsCount}</span> unread alert{unreadAlertsCount !== 1 ? 's' : ''}
          </div>
        )}
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
          <AlertsPanel 
            alerts={alerts} 
            onMarkRead={handleMarkAlertRead}
            onRefresh={loadAlerts}
          />
          <UsagePanel metrics={metrics.usage} />
          <ClinicalValuePanel metrics={metrics.clinical_value} />
          <SafetyPanel metrics={metrics.safety} />
          <PmfPanel metrics={metrics.pmf} />
        </div>
      )}
    </div>
  )
}
