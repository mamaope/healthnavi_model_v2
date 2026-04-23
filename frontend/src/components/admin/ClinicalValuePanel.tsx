import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import MetricCardWithTooltip from './MetricCardWithTooltip'
import './AdminPanel.css'

interface ClinicalValuePanelProps {
  metrics: any
}

export default function ClinicalValuePanel({ metrics }: ClinicalValuePanelProps) {
  if (!metrics) return null

  const helpfulPercentage = typeof metrics.helpful_feedback_percentage === 'number' ? metrics.helpful_feedback_percentage : 0
  const helpfulColor = helpfulPercentage >= 70 ? '#10b981' : helpfulPercentage >= 50 ? '#f59e0b' : '#ef4444'
  const helpfulCount = metrics.helpful_feedback ?? 0
  const notHelpfulCount = metrics.not_helpful_feedback ?? 0
  const totalFeedback = helpfulCount + notHelpfulCount

  const feedbackPieData = [
    { name: 'Helpful', value: helpfulCount, color: '#10b981' },
    { name: 'Not helpful', value: notHelpfulCount, color: '#ef4444' },
  ].filter((d) => d.value > 0)

  return (
    <div className="admin-panel clinical-value-panel">
      <div className="panel-header">
        <h2>Clinical value</h2>
      </div>
      <div className="panel-content">
        <div className="metrics-grid">
          <MetricCardWithTooltip
            label="Helpful feedback"
            value={`${helpfulPercentage.toFixed(1)}%`}
            subtitle={`${helpfulCount} of ${metrics.total_feedback || 0} responses`}
            icon="👍"
            color={helpfulColor}
            metricKey="clinical_value.helpful_feedback_percentage"
          />
          <MetricCardWithTooltip
            label="Average usefulness score"
            value={typeof metrics.avg_usefulness_score === 'number' ? metrics.avg_usefulness_score.toFixed(1) : '0.0'}
            subtitle="Out of 5.0"
            icon="⭐"
            metricKey="clinical_value.avg_usefulness_score"
          />
          <MetricCardWithTooltip
            label="Relevant queries"
            value={typeof metrics.relevant_queries_percentage === 'number' ? `${metrics.relevant_queries_percentage.toFixed(1)}%` : '0.0%'}
            subtitle={`${metrics.relevant_queries || 0} of ${metrics.total_survey_queries || 0} queries`}
            icon="🎯"
            metricKey="clinical_value.relevant_queries_percentage"
          />
          <MetricCardWithTooltip
            label="Average time saved"
            value={typeof metrics.avg_time_saved_minutes === 'number' ? `${metrics.avg_time_saved_minutes.toFixed(0)} min` : '0 min'}
            subtitle="Per session (from surveys)"
            icon="⏱️"
            metricKey="clinical_value.avg_time_saved_minutes"
          />
        </div>
        {feedbackPieData.length > 0 && (
          <div className="panel-chart">
            <h3 className="chart-title">Feedback sentiment</h3>
            <p className="chart-description">How users rated the clinical usefulness of AI responses</p>
            <ResponsiveContainer width="100%" height={180}>
              <PieChart>
                <Pie
                  data={feedbackPieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={35}
                  outerRadius={70}
                  paddingAngle={2}
                  dataKey="value"
                  nameKey="name"
                >
                  {feedbackPieData.map((entry, i) => (
                    <Cell key={i} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value) => {
                    const numericValue = typeof value === 'number' ? value : Number(value ?? 0) || 0
                    const pct = totalFeedback > 0 ? ((numericValue / totalFeedback) * 100).toFixed(1) : '0'
                    return [`${numericValue} (${pct}%)`, '']
                  }}
                  contentStyle={{ fontSize: 12, borderRadius: 8, backgroundColor: '#ffffff', color: '#1f2937', border: '1px solid #e5e7eb' }}
                />
                <Legend />
              </PieChart>
            </ResponsiveContainer>
          </div>
        )}
      </div>
    </div>
  )
}
