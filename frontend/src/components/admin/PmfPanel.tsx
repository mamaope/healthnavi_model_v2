import './AdminPanel.css'

interface PmfPanelProps {
  metrics: any
}

export default function PmfPanel({ metrics }: PmfPanelProps) {
  if (!metrics) return null

  const veryDisappointed = typeof metrics.very_disappointed_percentage === 'number' ? metrics.very_disappointed_percentage : 0
  const pmfColor = veryDisappointed >= 40 ? '#10b981' : veryDisappointed >= 25 ? '#f59e0b' : '#ef4444'

  return (
    <div className="admin-panel">
      <div className="panel-header">
        <h2>Product-Market Fit Panel</h2>
      </div>
      <div className="panel-content">
        <div className="metrics-grid">
          <MetricCard
            label="Heavy Users"
            value={metrics.heavy_users || 0}
            subtitle=">20 queries/week"
            icon="🔥"
          />
          <MetricCard
            label="Users Active in Week 3"
            value={metrics.users_active_week3 || 0}
            icon="📈"
          />
          <MetricCard
            label="Very Disappointed"
            value={`${veryDisappointed.toFixed(1)}%`}
            subtitle={`${metrics.very_disappointed_count || 0} of ${metrics.total_pmf_responses || 0} responses`}
            icon="😢"
            color={pmfColor}
          />
          <MetricCard
            label="Avg PMF Score"
            value={typeof metrics.avg_pmf_score === 'number' ? metrics.avg_pmf_score.toFixed(1) : '0.0'}
            subtitle="Out of 10.0"
            icon="📊"
          />
          <MetricCard
            label="Avg Willingness to Pay"
            value={typeof metrics.avg_willingness_to_pay === 'number' ? `$${metrics.avg_willingness_to_pay.toFixed(0)}` : '$0'}
            icon="💰"
          />
          <ReplacementBehaviorCard replacementBehavior={metrics.replacement_behavior} />
        </div>
      </div>
    </div>
  )
}

function MetricCard({ label, value, subtitle, icon, color }: { 
  label: string; 
  value: string | number; 
  subtitle?: string; 
  icon?: string;
  color?: string;
}) {
  return (
    <div className="metric-card" style={color ? { borderTopColor: color } : undefined}>
      {icon && <div className="metric-icon">{icon}</div>}
      <div className="metric-content">
        <div className="metric-label">{label}</div>
        <div className="metric-value" style={color ? { color } : undefined}>{value}</div>
        {subtitle && <div className="metric-subtitle">{subtitle}</div>}
      </div>
    </div>
  )
}

function ReplacementBehaviorCard({ replacementBehavior }: { replacementBehavior: Record<string, number> }) {
  if (!replacementBehavior || Object.keys(replacementBehavior).length === 0) {
    return (
      <div className="metric-card">
        <div className="metric-icon">🔄</div>
        <div className="metric-content">
          <div className="metric-label">Replacement Behavior</div>
          <div className="metric-value">No data</div>
        </div>
      </div>
    )
  }

  const total = Object.values(replacementBehavior).reduce((sum, count) => sum + count, 0)
  const sorted = Object.entries(replacementBehavior).sort((a, b) => b[1] - a[1])

  return (
    <div className="metric-card metric-card-wide">
      <div className="metric-icon">🔄</div>
      <div className="metric-content">
        <div className="metric-label">Replacement Behavior</div>
        <div className="replacement-list">
          {sorted.map(([behavior, count]) => (
            <div key={behavior} className="replacement-item">
              <span className="replacement-name">{behavior}</span>
              <span className="replacement-count">{count} ({(count / total * 100).toFixed(1)}%)</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
