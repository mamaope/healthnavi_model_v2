import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import MetricCardWithTooltip from './MetricCardWithTooltip'
import './AdminPanel.css'

interface UsagePanelProps {
  metrics: any
  days?: number
}

const CHART_COLORS = ['#0ea5e9', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899', '#6366f1']

export default function UsagePanel({ metrics, days = 30 }: UsagePanelProps) {
  if (!metrics) return null

  const chartData = [
    { name: 'Today', value: metrics.daily_active_users ?? 0, fullName: 'Users active today' },
    { name: 'This week', value: metrics.weekly_active_users ?? 0, fullName: 'Users active in last 7 days' },
    { name: 'Activated', value: metrics.activated_users ?? 0, fullName: 'Users who ever started a session' },
    { name: 'Total', value: metrics.total_users ?? 0, fullName: 'Total user accounts' },
  ].filter((d) => d.value > 0 || d.name === 'Total')

  return (
    <div className="admin-panel usage-panel">
      <div className="panel-header">
        <h2>Usage Overview</h2>
        <span className="panel-period">Last {days} days</span>
      </div>
      <div className="panel-content">
        <div className="metrics-grid">
          <MetricCardWithTooltip
            label="Daily active users"
            value={metrics.daily_active_users ?? 0}
            icon="👥"
            metricKey="usage.daily_active_users"
          />
          <MetricCardWithTooltip
            label="Weekly active users"
            value={metrics.weekly_active_users ?? 0}
            icon="📊"
            metricKey="usage.weekly_active_users"
          />
          <MetricCardWithTooltip
            label="Activated users"
            value={metrics.activated_users ?? 0}
            subtitle={typeof metrics.activation_rate === 'number' ? `${metrics.activation_rate.toFixed(1)}% of ${metrics.total_users || 0} total` : `0.0% of ${metrics.total_users || 0} total`}
            icon="✅"
            metricKey="usage.activated_users"
          />
          <MetricCardWithTooltip
            label="Average queries per user"
            value={typeof metrics.queries_per_clinician === 'number' ? metrics.queries_per_clinician.toFixed(1) : '0.0'}
            icon="💬"
            metricKey="usage.queries_per_clinician"
          />
          <MetricCardWithTooltip
            label="Average sessions per user"
            value={typeof metrics.sessions_per_user === 'number' ? metrics.sessions_per_user.toFixed(1) : '0.0'}
            icon="📝"
            metricKey="usage.sessions_per_user"
          />
          <MetricCardWithTooltip
            label="Total users"
            value={metrics.total_users ?? 0}
            icon="👥"
            metricKey="usage.total_users"
          />
        </div>
        {chartData.length > 0 && (
          <div className="panel-chart">
            <h3 className="chart-title">User activity at a glance</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={chartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="name" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip
                  formatter={(value) => {
                    const numericValue = typeof value === 'number' ? value : Number(value ?? 0) || 0
                    return [numericValue, 'Count']
                  }}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.fullName ?? ''}
                  contentStyle={{ fontSize: 12, borderRadius: 8, backgroundColor: '#ffffff', color: '#1f2937', border: '1px solid #e5e7eb' }}
                />
                <Bar dataKey="value" name="Users" radius={[4, 4, 0, 0]}>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
