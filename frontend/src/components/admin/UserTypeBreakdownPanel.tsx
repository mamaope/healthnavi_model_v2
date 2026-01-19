import { useState, useEffect } from 'react'
import { adminApi } from '../../services/apiClient'
import './AdminPanel.css'
import './UserManagementPanel.css'

interface UserTypeBreakdownPanelProps {
  days?: number
}

export default function UserTypeBreakdownPanel({ days = 30 }: UserTypeBreakdownPanelProps) {
  const [statistics, setStatistics] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadStatistics()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [days])

  const loadStatistics = async () => {
    try {
      setLoading(true)
      setError(null)
      // Ensure days is a number
      const daysNum = typeof days === 'number' ? days : parseInt(String(days), 10)
      console.log('Loading user statistics for days:', daysNum)
      const response = await adminApi.getUserStatistics(daysNum)
      console.log('User statistics response:', response)
      console.log('Response success:', response.success)
      console.log('Response data:', response.data)
      
      if (response && response.success && response.data) {
        console.log('Setting statistics:', response.data)
        setStatistics(response.data)
      } else {
        const errorMsg = (response as any)?.message || 'Failed to load user statistics'
        console.error('Failed to load user statistics - response not successful:', response)
        setError(errorMsg)
        setStatistics(null)
      }
    } catch (err: any) {
      console.error('Exception loading user statistics:', err)
      console.error('Error details:', {
        message: err?.message,
        stack: err?.stack,
        name: err?.name
      })
      setError(err?.message || 'Failed to load user statistics. Please check the browser console for details.')
      setStatistics(null)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="admin-panel">
        <div className="panel-header">
          <h2>User Type Breakdown</h2>
        </div>
        <div className="panel-content">
          <div className="loading-container">
            <div className="spinner"></div>
            <p>Loading statistics...</p>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="admin-panel">
        <div className="panel-header">
          <h2>User Type Breakdown</h2>
          <button onClick={loadStatistics} className="btn-refresh">
            Retry
          </button>
        </div>
        <div className="panel-content">
          <div className="error-container">
            <p>Error: {error}</p>
            <button onClick={loadStatistics} className="btn-primary">
              Try Again
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (!statistics) {
    return (
      <div className="admin-panel">
        <div className="panel-header">
          <h2>User Type Breakdown</h2>
          <button onClick={loadStatistics} className="btn-refresh">
            Refresh
          </button>
        </div>
        <div className="panel-content">
          <p>No statistics available</p>
        </div>
      </div>
    )
  }

  return (
    <div className="admin-panel">
      <div className="panel-header">
        <h2>User Type Breakdown</h2>
        <button onClick={loadStatistics} className="btn-refresh">
          Refresh
        </button>
      </div>
      <div className="panel-content">
        <div className="user-statistics">
          {statistics.users_by_role && Object.keys(statistics.users_by_role).length > 0 && (
            <div className="statistics-section">
              <h3>Users by Role</h3>
              <div className="statistics-list">
                {Object.entries(statistics.users_by_role)
                  .filter(([role, count]) => role != null && role !== 'null' && count != null)
                  .map(([role, count]: [string, any]) => (
                    <div key={role || 'unknown'} className="statistics-item">
                      <span className="statistics-label">{role ? (role.charAt(0).toUpperCase() + role.slice(1).replace('_', ' ')) : 'Unknown'}</span>
                      <span className="statistics-value">{count || 0}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}

          {statistics.users_by_type && Object.keys(statistics.users_by_type).length > 0 && (
            <div className="statistics-section">
              <h3>Users by Professional Type</h3>
              <div className="statistics-list">
                {Object.entries(statistics.users_by_type)
                  .filter(([type, count]) => type != null && type !== 'null' && count != null)
                  .map(([type, count]: [string, any]) => (
                    <div key={type || 'unknown'} className="statistics-item">
                      <span className="statistics-label">{type || 'Unknown'}</span>
                      <span className="statistics-value">{count || 0}</span>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function MetricCard({ label, value, subtitle, icon }: { label: string; value: string | number; subtitle?: string; icon?: string }) {
  return (
    <div className="metric-card">
      {icon && <div className="metric-icon">{icon}</div>}
      <div className="metric-content">
        <div className="metric-label">{label}</div>
        <div className="metric-value">{value}</div>
        {subtitle && <div className="metric-subtitle">{subtitle}</div>}
      </div>
    </div>
  )
}
