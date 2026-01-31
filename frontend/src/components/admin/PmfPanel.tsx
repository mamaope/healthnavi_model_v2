import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import MetricCardWithTooltip from './MetricCardWithTooltip'
import './AdminPanel.css'

interface PmfPanelProps {
  metrics: any
}

export default function PmfPanel({ metrics }: PmfPanelProps) {
  if (!metrics) return null

  const veryDisappointed = typeof metrics.very_disappointed_percentage === 'number' ? metrics.very_disappointed_percentage : 0
  const pmfColor = veryDisappointed >= 40 ? '#10b981' : veryDisappointed >= 25 ? '#f59e0b' : '#ef4444'

  const replacementBehavior = metrics.replacement_behavior ?? {}
  const replacementData = Object.entries(replacementBehavior)
    .filter(([, count]) => (count as number) > 0)
    .map(([name, value]) => ({ name, value: value as number }))
    .sort((a, b) => b.value - a.value)
    .slice(0, 6)

  return (
    <div className="admin-panel pmf-panel">
      <div className="panel-header">
        <h2>Product-market fit</h2>
      </div>
      <div className="panel-content">
        <div className="metrics-grid">
          <MetricCardWithTooltip
            label="Heavy users"
            value={metrics.heavy_users ?? 0}
            subtitle=">20 queries/week"
            icon="🔥"
            metricKey="pmf.heavy_users"
          />
          <MetricCardWithTooltip
            label="Users active (week 3)"
            value={metrics.users_active_week3 ?? 0}
            icon="📈"
            description="Users active in the last 7 days (retention indicator)."
          />
          <MetricCardWithTooltip
            label="Very disappointed"
            value={`${veryDisappointed.toFixed(1)}%`}
            subtitle={`${metrics.very_disappointed_count || 0} of ${metrics.total_pmf_responses || 0} responses`}
            icon="😢"
            color={pmfColor}
            metricKey="pmf.very_disappointed_percentage"
          />
          <MetricCardWithTooltip
            label="Average PMF score"
            value={typeof metrics.avg_pmf_score === 'number' ? metrics.avg_pmf_score.toFixed(1) : '0.0'}
            subtitle="Out of 10.0"
            icon="📊"
            metricKey="pmf.avg_pmf_score"
          />
          <MetricCardWithTooltip
            label="Avg willingness to pay"
            value={typeof metrics.avg_willingness_to_pay === 'number' ? `$${metrics.avg_willingness_to_pay.toFixed(0)}` : '$0'}
            icon="💰"
            description="Average amount users said they would pay, from PMF surveys."
          />
        </div>
        {replacementData.length > 0 && (
          <div className="panel-chart">
            <h3 className="chart-title">If product disappeared, users would...</h3>
            <p className="chart-description">Replacement behavior from PMF surveys</p>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={replacementData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={75}
                  paddingAngle={2}
                  dataKey="value"
                  nameKey="name"
                >
                  {replacementData.map((_, i) => (
                    <Cell key={i} fill={['#0ea5e9', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899', '#6366f1'][i % 6]} />
                  ))}
                </Pie>
                <Tooltip
                  formatter={(value: number, name: string, props: any) => {
                    const total = replacementData.reduce((s, d) => s + d.value, 0)
                    const pct = total > 0 ? ((value / total) * 100).toFixed(1) : '0'
                    return [`${value} (${pct}%)`, name]
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
