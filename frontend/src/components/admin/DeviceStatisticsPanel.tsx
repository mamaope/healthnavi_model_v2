import { useState, useEffect } from 'react'
import { adminApi } from '../../services/apiClient'
import './AdminPanel.css'
import './UserManagementPanel.css'

interface DeviceStatisticsPanelProps {
  devices?: { by_type?: Record<string, number>; total?: number } | null
  days?: number
}

export default function DeviceStatisticsPanel({ devices: devicesProp, days = 30 }: DeviceStatisticsPanelProps) {
  const [devices, setDevices] = useState<{ by_type?: Record<string, number>; total?: number } | null>(devicesProp ?? null)
  const [loading, setLoading] = useState(!devicesProp)
  const [error, setError] = useState<string | null>(null)

  const daysNum = typeof days === 'number' && !isNaN(days) ? Math.max(1, Math.min(365, Math.floor(days))) : 30

  useEffect(() => {
    if (devicesProp != null) {
      setDevices(devicesProp)
      setLoading(false)
      setError(null)
      return
    }
    let cancelled = false
    setLoading(true)
    setError(null)
    adminApi.getDeviceStatistics(daysNum)
      .then((r) => {
        if (!cancelled && r.success && r.data) {
          setDevices(r.data)
        }
      })
      .catch((e) => { if (!cancelled) setError(e?.message || 'Failed to load device statistics') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [devicesProp, daysNum])

  const byType = devices?.by_type ?? {}
  const total = devices?.total ?? 0
  const labels: Record<string, string> = {
    phone: 'Phone',
    tablet: 'Tablet',
    laptop: 'Laptop / Desktop',
    unknown: 'Unknown',
  }

  return (
    <div className="admin-panel">
      <div className="panel-header">
        <h2>Device Usage</h2>
      </div>
      <div className="panel-content">
        <p className="panel-description" style={{ marginTop: 0, marginBottom: '1rem', color: '#6b7280', fontSize: '0.875rem' }}>
          Logins and session starts in the last {daysNum} days by device type.
        </p>
        {loading && (
          <div className="loading-container" style={{ padding: '1.5rem' }}>
            <div className="spinner" />
            <p>Loading device statistics...</p>
          </div>
        )}
        {error && <p style={{ color: '#dc2626', margin: 0 }}>{error}</p>}
        {!loading && !error && total === 0 && (
          <p style={{ color: '#6b7280', margin: 0 }}>
            No device data for this period. Data is recorded when users log in or start a chat session. Ensure the backend has run the <code>add_device_activity_log</code> migration.
          </p>
        )}
        {!loading && !error && total > 0 && (
          <div className="statistics-list">
            {(['phone', 'tablet', 'laptop', 'unknown'] as const).map((key) => {
              const count = byType[key] ?? 0
              const pct = total > 0 ? ((count / total) * 100).toFixed(1) : '0'
              return (
                <div key={key} className="statistics-item">
                  <span className="statistics-label">{labels[key] || key}</span>
                  <span className="statistics-value">
                    {count} <span style={{ fontWeight: 400, color: '#6b7280', fontSize: '0.875rem' }}>({pct}%)</span>
                  </span>
                </div>
              )
            })}
          </div>
        )}
        {!loading && !error && total > 0 && (
          <div style={{ marginTop: '1rem', paddingTop: '1rem', borderTop: '1px solid #e5e7eb', fontWeight: 600, color: '#1a1a1a' }}>
            Total activities: {total}
          </div>
        )}
      </div>
    </div>
  )
}
