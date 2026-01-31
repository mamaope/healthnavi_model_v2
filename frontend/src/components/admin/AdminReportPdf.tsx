/**
 * Report content for PDF export. Renders statistics, charts, and explanations
 * in a print-friendly layout. Captured by html2canvas for PDF generation.
 */
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, ResponsiveContainer, PieChart, Pie, Cell, Legend, BarChart, Bar } from 'recharts'
import './AdminReportPdf.css'

interface ReportData {
  overall_statistics: { metric_name: string; value: string | number; description: string }[]
  period_statistics: { metric_name: string; value: string | number; description: string }[]
  period_selected: { period_start?: string; period_end?: string }
  feedback_count: number
  feedback_comments: { created_at?: string; user_email?: string; feedback_type?: string; feedback_text?: string }[]
  filters: { start_date?: string; end_date?: string; exclude_user_ids?: number[] }
  generated_at: string
}

interface UsageOverTimePoint {
  date: string
  active_users: number
  sessions: number
  messages: number
}

interface AdminReportPdfProps {
  reportData: ReportData
  usageOverTime: UsageOverTimePoint[]
  devicesByType?: Record<string, number>
  usersByRole?: Record<string, number>
  usersByType?: Record<string, number>
  periodLabel: string
}

const CHART_COLORS = ['#0ea5e9', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899']
const DEVICE_COLORS: Record<string, string> = { phone: '#0ea5e9', tablet: '#8b5cf6', laptop: '#10b981', unknown: '#94a3b8' }
const DEVICE_LABELS: Record<string, string> = { phone: 'Phone', tablet: 'Tablet', laptop: 'Laptop', unknown: 'Unknown' }

function formatDate(iso?: string) {
  if (!iso) return '—'
  try {
    const d = new Date(iso)
    return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
  } catch {
    return iso.slice(0, 10)
  }
}

function getMetricValue(stats: { metric_name: string; value: string | number }[], name: string): number {
  const row = stats.find((r) => r.metric_name === name)
  if (!row) return 0
  const v = row.value
  if (typeof v === 'number') return v
  const n = Number(v)
  return Number.isFinite(n) ? n : 0
}

function formatRole(role: string) {
  if (!role || role === 'null') return 'Unknown'
  return role.charAt(0).toUpperCase() + role.slice(1).replace('_', ' ')
}

export default function AdminReportPdf({
  reportData,
  usageOverTime,
  devicesByType = {},
  usersByRole = {},
  usersByType = {},
  periodLabel,
}: AdminReportPdfProps) {
  const periodStats = reportData.period_statistics ?? []

  const devicePieData = Object.entries(devicesByType)
    .filter(([, v]) => (v ?? 0) > 0)
    .map(([k, v]) => ({ name: DEVICE_LABELS[k] ?? k, value: v ?? 0, type: k }))

  const userActivityData = [
    { name: 'Today', value: getMetricValue(periodStats, 'Daily active users'), fullName: 'Users active today' },
    { name: 'This week', value: getMetricValue(periodStats, 'Weekly active users'), fullName: 'Users active in last 7 days' },
    { name: 'Activated', value: getMetricValue(periodStats, 'Activated users'), fullName: 'Users who ever started a session' },
    { name: 'Total', value: getMetricValue(periodStats, 'Total users'), fullName: 'Total user accounts' },
  ].filter((d) => d.value > 0 || d.name === 'Total')

  const helpfulCount = getMetricValue(periodStats, 'Helpful feedback count')
  const notHelpfulCount = getMetricValue(periodStats, 'Not helpful feedback count')
  const feedbackPieData = [
    { name: 'Helpful', value: helpfulCount, color: '#10b981' },
    { name: 'Not helpful', value: notHelpfulCount, color: '#ef4444' },
  ].filter((d) => d.value > 0)

  const rolePieData = Object.entries(usersByRole)
    .filter(([k, v]) => k != null && k !== 'null' && (v ?? 0) > 0)
    .map(([role, count]) => ({ name: formatRole(role), value: count ?? 0 }))

  const typePieData = Object.entries(usersByType)
    .filter(([k, v]) => k != null && k !== 'null' && (v ?? 0) > 0)
    .map(([type, count]) => ({ name: type || 'Unknown', value: count ?? 0 }))

  return (
    <div className="admin-report-pdf" id="pdf-report-content">
      <div className="pdf-report-inner">
        <header className="pdf-header">
          <h1>HealthNavi Admin Report</h1>
          <p className="pdf-period">{periodLabel}</p>
          <p className="pdf-generated">Generated: {formatDate(reportData.generated_at)}</p>
          {reportData.filters?.exclude_user_ids?.length ? (
            <p className="pdf-filters">Excluded users: {reportData.filters.exclude_user_ids.join(', ')}</p>
          ) : null}
        </header>

        <section className="pdf-section">
          <h2>Overall statistics (all time)</h2>
          <p className="pdf-desc">Key metrics across the entire system history.</p>
          <table className="pdf-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>How it was calculated</th>
              </tr>
            </thead>
            <tbody>
              {reportData.overall_statistics.map((row, i) => (
                <tr key={i}>
                  <td>{row.metric_name}</td>
                  <td>{String(row.value)}</td>
                  <td className="pdf-desc-cell">{row.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        <section className="pdf-section">
          <h2>Period selected statistics</h2>
          <p className="pdf-desc">
            Metrics for the selected period: {formatDate(reportData.period_selected?.period_start)} to{' '}
            {formatDate(reportData.period_selected?.period_end)}.
          </p>
          <table className="pdf-table">
            <thead>
              <tr>
                <th>Metric</th>
                <th>Value</th>
                <th>How it was calculated</th>
              </tr>
            </thead>
            <tbody>
              {reportData.period_statistics.map((row, i) => (
                <tr key={i}>
                  <td>{row.metric_name}</td>
                  <td>{String(row.value)}</td>
                  <td className="pdf-desc-cell">{row.description}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>

        {userActivityData.length > 0 && (
          <section className="pdf-section pdf-chart-section">
            <h2>User activity at a glance</h2>
            <p className="pdf-desc">Key user counts for the selected period.</p>
            <div className="pdf-chart" style={{ width: '100%', height: 200 }}>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={userActivityData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                  <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                  <Bar dataKey="value" name="Count" fill="#0ea5e9" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        {usageOverTime.length > 0 && (
          <section className="pdf-section pdf-chart-section">
            <h2>Usage over time</h2>
            <p className="pdf-desc">Daily active users, sessions, and user messages for the selected period.</p>
            <div className="pdf-chart" style={{ width: '100%', height: 220 }}>
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={usageOverTime} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                  <XAxis dataKey="date" tick={{ fontSize: 10 }} tickFormatter={(v) => (v?.length >= 10 ? v.slice(5) : v)} />
                  <YAxis tick={{ fontSize: 10 }} allowDecimals={false} />
                  <Area type="monotone" dataKey="active_users" name="Active users" stroke="#0ea5e9" fill="#0ea5e9" fillOpacity={0.3} strokeWidth={2} />
                  <Area type="monotone" dataKey="sessions" name="Sessions" stroke="#8b5cf6" fill="#8b5cf6" fillOpacity={0.3} strokeWidth={2} />
                  <Area type="monotone" dataKey="messages" name="Queries" stroke="#10b981" fill="#10b981" fillOpacity={0.3} strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        {feedbackPieData.length > 0 && (
          <section className="pdf-section pdf-chart-section">
            <h2>Feedback breakdown</h2>
            <p className="pdf-desc">How users rated AI responses (helpful vs not helpful).</p>
            <div className="pdf-chart" style={{ width: '100%', height: 180 }}>
              <ResponsiveContainer width="100%" height={180}>
                <PieChart>
                  <Pie
                    data={feedbackPieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={35}
                    outerRadius={65}
                    paddingAngle={2}
                    dataKey="value"
                    nameKey="name"
                  >
                    {feedbackPieData.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Legend layout="horizontal" align="center" wrapperStyle={{ paddingTop: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        {(rolePieData.length > 0 || typePieData.length > 0) && (
          <section className="pdf-section pdf-chart-section">
            <h2>Users by role & type</h2>
            <p className="pdf-desc">Distribution of users by system role and professional type.</p>
            <div className="pdf-charts-row">
              {rolePieData.length > 0 && (
                <div className="pdf-chart" style={{ width: '100%', height: 180 }}>
                  <h3 className="pdf-chart-subtitle">By role</h3>
                  <ResponsiveContainer width="100%" height={160}>
                    <PieChart>
                      <Pie
                        data={rolePieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={30}
                        outerRadius={60}
                        paddingAngle={2}
                        dataKey="value"
                        nameKey="name"
                      >
                        {rolePieData.map((_, i) => (
                          <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Legend layout="horizontal" align="center" wrapperStyle={{ paddingTop: 6 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
              {typePieData.length > 0 && (
                <div className="pdf-chart" style={{ width: '100%', height: 180 }}>
                  <h3 className="pdf-chart-subtitle">By professional type</h3>
                  <ResponsiveContainer width="100%" height={160}>
                    <PieChart>
                      <Pie
                        data={typePieData}
                        cx="50%"
                        cy="50%"
                        innerRadius={30}
                        outerRadius={60}
                        paddingAngle={2}
                        dataKey="value"
                        nameKey="name"
                      >
                        {typePieData.map((_, i) => (
                          <Cell key={i} fill={CHART_COLORS[(i + 2) % CHART_COLORS.length]} />
                        ))}
                      </Pie>
                      <Legend layout="horizontal" align="center" wrapperStyle={{ paddingTop: 6 }} />
                    </PieChart>
                  </ResponsiveContainer>
                </div>
              )}
            </div>
          </section>
        )}

        {devicePieData.length > 0 && (
          <section className="pdf-section pdf-chart-section">
            <h2>Device usage breakdown</h2>
            <p className="pdf-desc">Logins and session starts by device type.</p>
            <div className="pdf-chart" style={{ width: '100%', height: 200 }}>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={devicePieData}
                    cx="50%"
                    cy="50%"
                    innerRadius={40}
                    outerRadius={70}
                    paddingAngle={2}
                    dataKey="value"
                    nameKey="name"
                  >
                    {devicePieData.map((entry, i) => (
                      <Cell key={i} fill={DEVICE_COLORS[entry.type] ?? CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Legend layout="horizontal" align="center" wrapperStyle={{ paddingTop: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          </section>
        )}

        <section className="pdf-section">
          <h2>Feedback comments</h2>
          <p className="pdf-desc">Total feedback submissions: {reportData.feedback_count}</p>
          {reportData.feedback_comments.length > 0 ? (
            <table className="pdf-table">
              <thead>
                <tr>
                  <th>Date</th>
                  <th>User</th>
                  <th>Type</th>
                  <th>Comment</th>
                </tr>
              </thead>
              <tbody>
                {reportData.feedback_comments.slice(0, 20).map((fb, i) => (
                  <tr key={i}>
                    <td>{formatDate(fb.created_at)}</td>
                    <td>{fb.user_email ?? '—'}</td>
                    <td>{fb.feedback_type ?? '—'}</td>
                    <td className="pdf-desc-cell">{(fb.feedback_text ?? '—').slice(0, 80)}{(fb.feedback_text?.length ?? 0) > 80 ? '…' : ''}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="pdf-empty">No feedback comments in this period.</p>
          )}
          {reportData.feedback_comments.length > 20 && (
            <p className="pdf-more">… and {reportData.feedback_comments.length - 20} more. See full export for complete list.</p>
          )}
        </section>
      </div>
    </div>
  )
}
