import { useState, useEffect } from 'react'
import { adminApi } from '../../services/apiClient'
import './AdminPanel.css'

interface SessionManagementPanelProps {
  days: number
}

export default function SessionManagementPanel({ days }: SessionManagementPanelProps) {
  const [statistics, setStatistics] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStatistics()
  }, [days])

  const loadStatistics = async () => {
    try {
      setLoading(true)
      const response = await adminApi.getSessionStatistics(days)
      if (response.success) {
        setStatistics(response.data)
      }
    } catch (err) {
      console.error('Failed to load session statistics:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="admin-panel">
        <div className="panel-header">
          <h2>Session Management</h2>
        </div>
        <div className="panel-content">
          <div className="loading-container">
            <div className="spinner"></div>
            <p>Loading session statistics...</p>
          </div>
        </div>
      </div>
    )
  }

  if (!statistics) return null

  return (
    <div className="admin-panel">
      <div className="panel-header">
        <h2>Session Management</h2>
        <button onClick={loadStatistics} className="btn-refresh">
          Refresh
        </button>
      </div>
      <div className="panel-content">
        <div className="metrics-grid">
          <MetricCard
            label="Total Sessions"
            value={statistics.total_sessions || 0}
            subtitle={`Last ${days} days`}
            icon="📋"
          />
          <MetricCard
            label="Active Sessions"
            value={statistics.active_sessions || 0}
            subtitle="Last 24 hours"
            icon="🟢"
          />
          <MetricCard
            label="Avg Session Length"
            value={typeof statistics.avg_session_length === 'number' ? statistics.avg_session_length.toFixed(1) : '0.0'}
            subtitle="Messages per session"
            icon="💬"
          />
          <MetricCard
            label="Avg Session Duration"
            value={typeof statistics.avg_duration_minutes === 'number' ? `${statistics.avg_duration_minutes.toFixed(1)} min` : '0.0 min'}
            subtitle="Time between first and last message"
            icon="⏱️"
          />
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
