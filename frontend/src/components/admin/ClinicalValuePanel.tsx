import './AdminPanel.css'

interface ClinicalValuePanelProps {
  metrics: any
}

export default function ClinicalValuePanel({ metrics }: ClinicalValuePanelProps) {
  if (!metrics) return null

  const helpfulPercentage = typeof metrics.helpful_feedback_percentage === 'number' ? metrics.helpful_feedback_percentage : 0
  const helpfulColor = helpfulPercentage >= 70 ? '#10b981' : helpfulPercentage >= 50 ? '#f59e0b' : '#ef4444'

  return (
    <div className="admin-panel">
      <div className="panel-header">
        <h2>Clinical Value Panel</h2>
      </div>
      <div className="panel-content">
        <div className="metrics-grid">
          <MetricCard
            label="Helpful Feedback"
            value={`${helpfulPercentage.toFixed(1)}%`}
            subtitle={`${metrics.helpful_feedback || 0} of ${metrics.total_feedback || 0} responses`}
            icon="👍"
            color={helpfulColor}
          />
          <MetricCard
            label="Avg Usefulness Score"
            value={typeof metrics.avg_usefulness_score === 'number' ? metrics.avg_usefulness_score.toFixed(1) : '0.0'}
            subtitle="Out of 5.0"
            icon="⭐"
          />
          <MetricCard
            label="Relevant Queries"
            value={typeof metrics.relevant_queries_percentage === 'number' ? `${metrics.relevant_queries_percentage.toFixed(1)}%` : '0.0%'}
            subtitle={`${metrics.relevant_queries || 0} of ${metrics.total_survey_queries || 0} queries`}
            icon="🎯"
          />
          <MetricCard
            label="Avg Time Saved"
            value={typeof metrics.avg_time_saved_minutes === 'number' ? `${metrics.avg_time_saved_minutes.toFixed(0)} min` : '0 min'}
            subtitle="Per query (from surveys)"
            icon="⏱️"
          />
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
