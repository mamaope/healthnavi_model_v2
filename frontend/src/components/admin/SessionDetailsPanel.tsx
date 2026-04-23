import { useEffect, useMemo, useState } from 'react'
import { adminApi, type AdminMetricsParams, type AdminSessionDetailItem } from '../../services/apiClient'
import './AdminPanel.css'

function formatIso(ts?: string | null) {
  if (!ts) return '—'
  return ts.slice(0, 19).replace('T', ' ')
}

function escapeCsvCell(value: string) {
  const v = value ?? ''
  const escaped = v.replace(/"/g, '""')
  return `"${escaped}"`
}

interface SessionDetailsPanelProps {
  filters: AdminMetricsParams & { days: number }
}

export default function SessionDetailsPanel({ filters }: SessionDetailsPanelProps) {
  const [rows, setRows] = useState<AdminSessionDetailItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [excludeEmailsText, setExcludeEmailsText] = useState('')
  const [limit, setLimit] = useState(200)
  const [offset, setOffset] = useState(0)
  const [total, setTotal] = useState(0)

  const excludeEmails = useMemo(() => {
    return excludeEmailsText
      .split(/[,\n;]/g)
      .map((s) => s.trim())
      .filter(Boolean)
  }, [excludeEmailsText])

  useEffect(() => {
    setOffset(0)
  }, [filters.days, filters.startDate, filters.endDate, (filters.userIds ?? []).join(','), (filters.excludeUserIds ?? []).join(','), excludeEmails.join(',')])

  useEffect(() => {
    const load = async () => {
      try {
        setLoading(true)
        setError(null)
        const res = await adminApi.getSessionDetails({
          ...filters,
          excludeEmails,
          limit,
          offset,
        })
        if (res.success && res.data) {
          setRows(res.data.items ?? [])
          setTotal(res.data.total ?? 0)
        } else {
          setRows([])
          setTotal(0)
        }
      } catch (e: any) {
        setError(e?.message || 'Failed to load session details')
        setRows([])
        setTotal(0)
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
    excludeEmails.join(','),
    limit,
    offset,
  ])

  const handleExportCsv = () => {
    if (!rows.length) return
    const header = [
      'session_id',
      'user_id',
      'full_name',
      'email',
      'created_at',
      'updated_at',
      'message_count',
      'user_message_count',
      'assistant_message_count',
    ]
    const lines = [
      header.join(','),
      ...rows.map((r) =>
        [
          String(r.session_id),
          String(r.user_id),
          escapeCsvCell(r.full_name ?? ''),
          escapeCsvCell(r.email ?? ''),
          escapeCsvCell(r.created_at ?? ''),
          escapeCsvCell(r.updated_at ?? ''),
          String(r.message_count ?? 0),
          String(r.user_message_count ?? 0),
          String(r.assistant_message_count ?? 0),
        ].join(','),
      ),
    ]
    const blob = new Blob([lines.join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `session_details_${new Date().toISOString().slice(0, 10)}.csv`
    a.click()
    URL.revokeObjectURL(url)
  }

  const canPrev = offset > 0
  const canNext = offset + limit < total

  return (
    <div className="admin-panel">
      <div className="panel-header">
        <h2>Session Details</h2>
        <div className="panel-header-right">
          <button type="button" className="btn-export" onClick={handleExportCsv} disabled={loading || !!error || rows.length === 0}>
            Export CSV
          </button>
        </div>
      </div>

      <div className="panel-content">
        <div className="filters-row" style={{ display: 'grid', gridTemplateColumns: '1fr auto auto', gap: '0.75rem', alignItems: 'end', marginBottom: '0.75rem' }}>
          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Exclude emails (comma/newline separated)</span>
            <textarea
              value={excludeEmailsText}
              onChange={(e) => setExcludeEmailsText(e.target.value)}
              rows={2}
              placeholder="test@example.com, internal@company.com"
              style={{ width: '100%' }}
            />
          </label>

          <label style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
            <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Rows</span>
            <select value={String(limit)} onChange={(e) => setLimit(Number(e.target.value))} className="period-selector">
              <option value={50}>50</option>
              <option value={100}>100</option>
              <option value={200}>200</option>
              <option value={500}>500</option>
            </select>
          </label>

          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button type="button" className="btn-refresh" onClick={() => setOffset((v) => Math.max(0, v - limit))} disabled={!canPrev || loading}>
              Prev
            </button>
            <button type="button" className="btn-refresh" onClick={() => setOffset((v) => v + limit)} disabled={!canNext || loading}>
              Next
            </button>
          </div>
        </div>

        {loading && (
          <div className="loading-container">
            <div className="spinner" />
            <p>Loading session details...</p>
          </div>
        )}
        {error && !loading && (
          <div className="error-container">
            <p>{error}</p>
          </div>
        )}
        {!loading && !error && rows.length === 0 && <p className="empty-state">No sessions found for the selected period.</p>}

        {!loading && !error && rows.length > 0 && (
          <>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8, color: 'var(--text-secondary)', fontSize: 12 }}>
              <span>
                Showing {offset + 1}–{Math.min(offset + limit, total)} of {total}
              </span>
            </div>
            <div className="table-container">
              <table className="admin-table">
                <thead>
                  <tr>
                    <th>When</th>
                    <th>User</th>
                    <th>Email</th>
                    <th>Msgs</th>
                    <th>User</th>
                    <th>AI</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((r) => (
                    <tr key={r.session_id}>
                      <td>
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span>{formatIso(r.created_at)}</span>
                          <span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>Updated: {formatIso(r.updated_at)}</span>
                        </div>
                      </td>
                      <td>{r.full_name || '—'}</td>
                      <td>{r.email}</td>
                      <td>{r.message_count}</td>
                      <td>{r.user_message_count}</td>
                      <td>{r.assistant_message_count}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}
      </div>
    </div>
  )
}

