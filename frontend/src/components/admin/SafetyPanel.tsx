import './AdminPanel.css'

interface SafetyPanelProps {
  metrics: any
}

export default function SafetyPanel({ metrics }: SafetyPanelProps) {
  if (!metrics) return null

  const flagRate = typeof metrics.flags_per_100_queries === 'number' ? metrics.flags_per_100_queries : 0
  const flagRateColor = flagRate > 5 ? '#ef4444' : flagRate > 2 ? '#f59e0b' : '#10b981'
  const flagRate24h = typeof metrics.flag_rate_24h === 'number' ? metrics.flag_rate_24h : 0
  const flagRate24hColor = flagRate24h > 5 ? '#ef4444' : flagRate24h > 2 ? '#f59e0b' : '#10b981'

  return (
    <div className="admin-panel">
      <div className="panel-header">
        <h2>Safety Panel</h2>
      </div>
      <div className="panel-content">
        <div className="metrics-grid">
          <MetricCard
            label="Flags per 100 Queries"
            value={`${flagRate.toFixed(2)}%`}
            subtitle={`${metrics.total_flags || 0} flags, ${metrics.total_queries || 0} queries`}
            icon="🚩"
            color={flagRateColor}
          />
          <MetricCard
            label="Flag Rate (24h)"
            value={`${flagRate24h.toFixed(2)}%`}
            subtitle={`${metrics.flags_24h || 0} flags, ${metrics.queries_24h || 0} queries`}
            icon="⚠️"
            color={flagRate24hColor}
            highlight={flagRate24h > 5}
          />
          <MetricCard
            label="Open Safety Events"
            value={metrics.open_safety_events || 0}
            icon="📋"
          />
          <MetricCard
            label="Critical Incidents"
            value={metrics.critical_incidents || 0}
            icon="🔴"
            color={(metrics.critical_incidents || 0) > 0 ? '#ef4444' : undefined}
          />
          <MetricCard
            label="Responses with Citations"
            value={typeof metrics.citations_percentage === 'number' ? `${metrics.citations_percentage.toFixed(1)}%` : '0.0%'}
            icon="📚"
          />
          <MetricCard
            label="Red Flag Accuracy"
            value={typeof metrics.red_flag_accuracy_percentage === 'number' ? `${metrics.red_flag_accuracy_percentage.toFixed(1)}%` : '0.0%'}
            subtitle={`${metrics.correctly_flagged_red_flags || 0} of ${metrics.red_flag_queries || 0} flagged correctly`}
            icon="🎯"
          />
        </div>
      </div>
    </div>
  )
}

function MetricCard({ label, value, subtitle, icon, color, highlight }: { 
  label: string; 
  value: string | number; 
  subtitle?: string; 
  icon?: string;
  color?: string;
  highlight?: boolean;
}) {
  return (
    <div 
      className={`metric-card ${highlight ? 'metric-card-highlight' : ''}`}
      style={color ? { borderTopColor: color } : undefined}
    >
      {icon && <div className="metric-icon">{icon}</div>}
      <div className="metric-content">
        <div className="metric-label">{label}</div>
        <div className="metric-value" style={color ? { color } : undefined}>{value}</div>
        {subtitle && <div className="metric-subtitle">{subtitle}</div>}
      </div>
    </div>
  )
}
