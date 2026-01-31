import { useEffect, useState } from 'react'
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Area,
  AreaChart,
} from 'recharts'
import { adminApi } from '../../services/apiClient'
import type { AdminMetricsParams } from '../../services/apiClient'
import './UsageOverTimePanel.css'

type UsageOverTimePanelProps = {
  filters: { startDate?: string; endDate?: string; userIds?: number[]; excludeUserIds?: number[] }
  days: number
}

export default function UsageOverTimePanel({ filters, days }: UsageOverTimePanelProps) {
  const [series, setSeries] = useState<{ date: string; active_users: number; sessions: number; messages: number }[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    const params: AdminMetricsParams = {
      days: filters.startDate && filters.endDate ? undefined : days,
      startDate: filters.startDate,
      endDate: filters.endDate,
      userIds: filters.userIds,
      excludeUserIds: filters.excludeUserIds,
    }
    setLoading(true)
    setError(null)
    adminApi
      .getUsageOverTime(params)
      .then((res) => {
        if (cancelled || !res.success) return
        setSeries(res.data?.series ?? [])
      })
      .catch((e) => !cancelled && setError(e.message || 'Failed to load usage over time'))
      .finally(() => !cancelled && setLoading(false))
    return () => { cancelled = true }
  }, [days, filters.startDate, filters.endDate, filters.userIds?.join(','), filters.excludeUserIds?.join(',')])

  if (loading) {
    return (
      <section className="admin-panel usage-over-time-panel">
        <h2>Usage over time</h2>
        <p className="loading-text">Loading chart…</p>
      </section>
    )
  }

  if (error) {
    return (
      <section className="admin-panel usage-over-time-panel">
        <h2>Usage over time</h2>
        <p className="error-text">{error}</p>
      </section>
    )
  }

  if (series.length === 0) {
    return (
      <section className="admin-panel usage-over-time-panel">
        <h2>Usage over time</h2>
        <p className="empty-text">No data for the selected period.</p>
      </section>
    )
  }

  const data = series

  const tooltipDescriptions: Record<string, string> = {
    active_users: 'Unique users who had at least one session on this day.',
    sessions: 'Number of chat sessions started on this day.',
    messages: 'Total user messages (queries) sent on this day.',
  }

  const CustomTooltip = ({ active, payload, label }: any) => {
    if (!active || !payload?.length || !label) return null
    return (
      <div className="usage-chart-tooltip">
        <div className="usage-tooltip-date">{label}</div>
        {payload.map((p: any) => (
          <div key={p.dataKey} className="usage-tooltip-row">
            <span style={{ color: p.color }}>{p.name}:</span> {p.value}
            <div className="usage-tooltip-desc">{tooltipDescriptions[p.dataKey]}</div>
          </div>
        ))}
      </div>
    )
  }

  return (
    <section className="admin-panel usage-over-time-panel">
      <div className="panel-header">
        <h2>Usage over time</h2>
        <span className="panel-period" title="Daily counts of active users, sessions, and user messages. Hover for details.">Daily trends</span>
      </div>
      <div className="panel-content">
        <p className="panel-description">
          How usage changes day by day. Active users = unique users with at least one session. Hover over the chart for details.
        </p>
        <div className="usage-chart-container">
          <ResponsiveContainer width="100%" height={320}>
            <AreaChart data={data} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis
                dataKey="date"
                tick={{ fontSize: 11 }}
                interval="preserveStartEnd"
                tickFormatter={(v) => (v && v.length >= 10 ? v.slice(5) : v)}
              />
              <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
              <Tooltip content={<CustomTooltip />} contentStyle={{ fontSize: 12, borderRadius: 8, padding: '0.75rem 1rem', backgroundColor: 'transparent', border: 'none' }} />
              <Legend wrapperStyle={{ fontSize: 12 }} />
            <Area
              type="monotone"
              dataKey="active_users"
              name="Active users"
              stroke="#0ea5e9"
              fill="#0ea5e9"
              fillOpacity={0.3}
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="sessions"
              name="Sessions"
              stroke="#8b5cf6"
              fill="#8b5cf6"
              fillOpacity={0.3}
              strokeWidth={2}
            />
            <Area
              type="monotone"
              dataKey="messages"
              name="Queries (messages)"
              stroke="#10b981"
              fill="#10b981"
              fillOpacity={0.3}
              strokeWidth={2}
            />
          </AreaChart>
        </ResponsiveContainer>
        </div>
      </div>
    </section>
  )
}
