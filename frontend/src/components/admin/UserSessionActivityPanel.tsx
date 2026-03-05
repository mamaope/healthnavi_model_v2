import { useEffect, useState } from 'react'
import { adminApi, type AdminMetricsParams, type AdminUserSessionActivityItem } from '../../services/apiClient'
import './AdminPanel.css'

interface UserSessionActivityPanelProps {
  filters: AdminMetricsParams & { days: number }
}

export default function UserSessionActivityPanel({ filters }: UserSessionActivityPanelProps) {
  const [rows, setRows] = useState<AdminUserSessionActivityItem[]>([])
  const [summary, setSummary] = useState<{ total_users: number; total_sessions: number; period_start?: string | null; period_end?: string | null } | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await adminApi.getUserSessionActivity(filters)
        if (res.success && res.data) {
          setRows(res.data.items ?? [])
          setSummary({
            total_users: res.data.total_users ?? 0,
            total_sessions: res.data.total_sessions ?? 0,
            period_start: res.data.period_start,
            period_end: res.data.period_end,
          })
        } else {
          setRows([])
          setSummary(null)
        }
      } catch (e: any) {
        setError(e?.message || 'Failed to load user session activity')
        setRows([])
        setSummary(null)
      } finally {
        setLoading(false)
      }
    }
    void load()
  }, [
    filters.days,
    filters.startDate,
    filters.endDate,
    (filters.userIds ?? []).join(','),
    (filters.excludeUserIds ?? []).join(','),
  ])

  const handleExportCsv = () => {
    if (!rows.length) return
    const header = ['User', 'Email', 'Sessions', 'First session', 'Last session']
    const lines = [
      header.join(','),
      ...rows.map((row) => {
        const user = (row.full_name || '').replace(/"/g, '""')
        const email = (row.email || '').replace(/"/g, '""')
        const first = row.first_session_at ? row.first_session_at : ''
        const last = row.last_session_at ? row.last_session_at : ''
        return [`"${user}"`, `"${email}"`, String(row.session_count), `"${first}"`, `"${last}"`].join(',')
      }),
    ]
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `user_sessions_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="admin-panel">
      <div className="panel-header">
        <h2>User Session Activity</h2>
        <div className="panel-header-right">
          {summary && (
            <div className="panel-subtitle">
              <span>
                Users: <strong>{summary.total_users}</strong>
              </span>
              <span>
                Sessions: <strong>{summary.total_sessions}</strong>
              </span>
              {summary.period_start && summary.period_end && (
                <span>
                  Period: {summary.period_start.slice(0, 10)} – {summary.period_end.slice(0, 10)}
                </span>
              )}
            </div>
          )}
          <button
            type="button"
            className="btn-export"
            onClick={handleExportCsv}
            disabled={loading || !!error || rows.length === 0}
            title="Export current user session activity as CSV"
          >
            Export CSV
          </button>
        </div>
      </div>
      <div className="panel-content">
        {loading && (
          <div className="loading-container">
            <div className="spinner" />
            <p>Loading user session activity...</p>
          </div>
        )}
        {error && !loading && (
          <div className="error-container">
            <p>{error}</p>
          </div>
        )}
        {!loading && !error && rows.length === 0 && (
          <p className="empty-state">No sessions found for the selected period.</p>
        )}
        {!loading && !error && rows.length > 0 && (
          <div className="table-container">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Email</th>
                  <th>Sessions</th>
                  <th>First access</th>
                  <th>Last access</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.user_id}>
                    <td>{row.full_name || '—'}</td>
                    <td>{row.email}</td>
                    <td>{row.session_count}</td>
                    <td>{row.first_session_at ? row.first_session_at.slice(0, 19).replace('T', ' ') : '—'}</td>
                    <td>{row.last_session_at ? row.last_session_at.slice(0, 19).replace('T', ' ') : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

