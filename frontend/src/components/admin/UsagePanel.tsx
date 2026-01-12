import './AdminPanel.css'

interface UsagePanelProps {
  metrics: any
}

export default function UsagePanel({ metrics }: UsagePanelProps) {
  if (!metrics) return null

  return (
    <div className="admin-panel">
      <div className="panel-header">
        <h2>Usage Panel</h2>
      </div>
      <div className="panel-content">
        <div className="metrics-grid">
          <MetricCard
            label="Daily Active Users"
            value={metrics.daily_active_users}
            icon="👥"
          />
          <MetricCard
            label="Weekly Active Users"
            value={metrics.weekly_active_users}
            icon="📊"
          />
          <MetricCard
            label="Activated Users"
            value={metrics.activated_users}
            subtitle={typeof metrics.activation_rate === 'number' ? `${metrics.activation_rate.toFixed(1)}% of ${metrics.total_users || 0} total` : `0.0% of ${metrics.total_users || 0} total`}
            icon="✅"
          />
          <MetricCard
            label="Queries per Clinician"
            value={typeof metrics.queries_per_clinician === 'number' ? metrics.queries_per_clinician.toFixed(1) : '0.0'}
            icon="💬"
          />
          <MetricCard
            label="Sessions per User"
            value={typeof metrics.sessions_per_user === 'number' ? metrics.sessions_per_user.toFixed(1) : '0.0'}
            icon="📝"
          />
          <MetricCard
            label="Retention (W1→W3)"
            value={typeof metrics.retention_week1_to_week3 === 'number' ? `${metrics.retention_week1_to_week3.toFixed(1)}%` : '0.0%'}
            subtitle={`${metrics.week3_active_users || 0} of ${metrics.week1_users || 0} users`}
            icon="🔄"
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
