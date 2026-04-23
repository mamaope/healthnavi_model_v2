import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Cell } from 'recharts'
import MetricCardWithTooltip from './MetricCardWithTooltip'
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

  const safetyChartData = [
    { name: 'Open events', value: metrics.open_safety_events ?? 0, fullName: 'Open safety events' },
    { name: 'Critical', value: metrics.critical_incidents ?? 0, fullName: 'Critical incidents' },
    { name: 'Total flags', value: metrics.total_flags ?? 0, fullName: 'Total safety flags in period' },
  ].filter((d) => d.value > 0 || d.name === 'Open events')

  return (
    <div className="admin-panel safety-panel">
      <div className="panel-header">
        <h2>Safety & quality</h2>
      </div>
      <div className="panel-content">
        <div className="metrics-grid">
          <MetricCardWithTooltip
            label="Flags per 100 queries"
            value={`${flagRate.toFixed(2)}%`}
            subtitle={`${metrics.total_flags || 0} flags, ${metrics.total_queries || 0} queries`}
            icon="🚩"
            color={flagRateColor}
            metricKey="safety.flags_per_100_queries"
          />
          <MetricCardWithTooltip
            label="Flag rate (24h)"
            value={`${flagRate24h.toFixed(2)}%`}
            subtitle={`${metrics.flags_24h || 0} flags, ${metrics.queries_24h || 0} queries`}
            icon="⚠️"
            color={flagRate24hColor}
            highlight={flagRate24h > 5}
            description="Safety flags per 100 queries in the last 24 hours. High values may need attention."
          />
          <MetricCardWithTooltip
            label="Open safety events"
            value={metrics.open_safety_events ?? 0}
            icon="📋"
            metricKey="safety.open_safety_events"
          />
          <MetricCardWithTooltip
            label="Critical incidents"
            value={metrics.critical_incidents ?? 0}
            icon="🔴"
            color={(metrics.critical_incidents || 0) > 0 ? '#ef4444' : undefined}
            metricKey="safety.critical_incidents"
          />
          <MetricCardWithTooltip
            label="Responses with citations"
            value={typeof metrics.citations_percentage === 'number' ? `${metrics.citations_percentage.toFixed(1)}%` : '0.0%'}
            icon="📚"
            metricKey="safety.citations_percentage"
          />
          <MetricCardWithTooltip
            label="Red-flag accuracy"
            value={typeof metrics.red_flag_accuracy_percentage === 'number' ? `${metrics.red_flag_accuracy_percentage.toFixed(1)}%` : '0.0%'}
            subtitle={`${metrics.correctly_flagged_red_flags || 0} of ${metrics.red_flag_queries || 0} correct`}
            icon="🎯"
            metricKey="safety.red_flag_accuracy_percentage"
          />
        </div>
        {safetyChartData.length > 0 && (
          <div className="panel-chart">
            <h3 className="chart-title">Safety overview</h3>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={safetyChartData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} />
                <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
                <Tooltip
                  formatter={(value) => {
                    const numericValue = typeof value === 'number' ? value : Number(value ?? 0) || 0
                    return [numericValue, 'Count']
                  }}
                  labelFormatter={(_, payload) => payload?.[0]?.payload?.fullName ?? ''}
                  contentStyle={{ fontSize: 12, borderRadius: 8, backgroundColor: '#ffffff', color: '#1f2937', border: '1px solid #e5e7eb' }}
                />
                <Bar dataKey="value" name="Count" radius={[4, 4, 0, 0]}>
                  {safetyChartData.map((_, i) => (
                    <Cell key={i} fill={['#ef4444', '#f59e0b', '#6b7280'][i % 3]} />
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
