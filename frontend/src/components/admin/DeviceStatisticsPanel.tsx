import { useState, useEffect } from 'react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import { adminApi } from '../../services/apiClient'
import MetricCardWithTooltip from './MetricCardWithTooltip'
import './AdminPanel.css'

interface DeviceStatisticsPanelProps {
  devices?: { by_type?: Record<string, number>; total?: number } | null
  days?: number
}

const DEVICE_COLORS: Record<string, string> = {
  phone: '#0ea5e9',
  tablet: '#8b5cf6',
  laptop: '#10b981',
  unknown: '#94a3b8',
}

const DEVICE_LABELS: Record<string, string> = {
  phone: 'Phone',
  tablet: 'Tablet',
  laptop: 'Laptop / Desktop',
  unknown: 'Unknown',
}

export default function DeviceStatisticsPanel({ devices: devicesProp, days = 30 }: DeviceStatisticsPanelProps) {
  const [devices, setDevices] = useState<{ by_type?: Record<string, number>; total?: number } | null>(devicesProp ?? null)
  const [loading, setLoading] = useState(!devicesProp)
  const [error, setError] = useState<string | null>(null)
  const [seeding, setSeeding] = useState(false)

  const daysNum = typeof days === 'number' && !isNaN(days) ? Math.max(1, Math.min(365, Math.floor(days))) : 30

  const runSeedTest = () => {
    setSeeding(true)
    setError(null)
    adminApi.seedTestDeviceActivity()
      .then(() => adminApi.getDeviceStatistics(daysNum))
      .then((r) => { if (r.success && r.data) setDevices(r.data) })
      .catch((e) => setError(e?.message || 'Seed test failed'))
      .finally(() => setSeeding(false))
  }

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
      .catch((e) => { if (!cancelled) setError(e.message || 'Failed to load device statistics') })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [devicesProp, daysNum])

  const byType = devices?.by_type ?? {}
  const total = devices?.total ?? 0
  const pieData = (['phone', 'tablet', 'laptop', 'unknown'] as const)
    .filter((k) => (byType[k] ?? 0) > 0)
    .map((k) => ({ name: DEVICE_LABELS[k], value: byType[k] ?? 0, type: k }))

  return (
    <div className="admin-panel device-panel">
      <div className="panel-header">
        <h2>Device usage</h2>
        <button
          type="button"
          className="btn-refresh"
          onClick={runSeedTest}
          disabled={seeding}
          title="Insert a test row to verify the table and pipeline"
        >
          {seeding ? 'Inserting…' : 'Insert test row'}
        </button>
      </div>
      <div className="panel-content">
        <p className="panel-description">
          Logins and session starts in the last {daysNum} days by device type.
        </p>
        {loading && (
          <div className="loading-container">
            <div className="spinner" />
            <p>Loading device statistics...</p>
          </div>
        )}
        {error && <p className="panel-error">{error}</p>}
        {!loading && !error && total === 0 && (
          <p className="panel-empty">
            No device data yet. Data is recorded when users log in or start a new chat session.
          </p>
        )}
        {!loading && !error && total > 0 && (
          <>
            <div className="panel-chart-row">
              <div className="panel-chart pie-chart chart-container">
                <h3 className="chart-title">Devices used</h3>
                <ResponsiveContainer width="100%" height={240}>
                  <PieChart margin={{ top: 10, right: 10, bottom: 10, left: 10 }}>
                    <Pie
                      data={pieData}
                      cx="50%"
                      cy="50%"
                      innerRadius={45}
                      outerRadius={80}
                      paddingAngle={2}
                      dataKey="value"
                      nameKey="name"
                    >
                      {pieData.map((entry, i) => (
                        <Cell key={entry.type} fill={DEVICE_COLORS[entry.type] ?? '#94a3b8'} />
                      ))}
                    </Pie>
                    <Tooltip
                      formatter={(value: number, name: string) => {
                        const pct = total > 0 ? ((value / total) * 100).toFixed(1) : '0'
                        return [`${value} (${pct}%)`, name]
                      }}
                      contentStyle={{ fontSize: 12, borderRadius: 8, backgroundColor: '#ffffff', color: '#1f2937', border: '1px solid #e5e7eb' }}
                    />
                    <Legend layout="horizontal" align="center" wrapperStyle={{ paddingTop: 8 }} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
              <div className="device-summary">
                <MetricCardWithTooltip
                  label="Total activities"
                  value={total}
                  description="Total device activity log entries (logins, session starts) in the period."
                  icon="📱"
                />
              </div>
            </div>
            <div className="statistics-list device-list">
              {(['phone', 'tablet', 'laptop', 'unknown'] as const).map((key) => {
                const count = byType[key] ?? 0
                const pct = total > 0 ? ((count / total) * 100).toFixed(1) : '0'
                return (
                  <div key={key} className="statistics-item">
                    <span className="statistics-label">{DEVICE_LABELS[key]}</span>
                    <span className="statistics-value">
                      {count} <span className="stat-pct">({pct}%)</span>
                    </span>
                  </div>
                )
              })}
            </div>
          </>
        )}
      </div>
    </div>
  )
}
