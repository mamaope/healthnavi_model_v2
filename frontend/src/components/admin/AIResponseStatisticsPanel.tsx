import { useState, useEffect } from 'react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import { adminApi } from '../../services/apiClient'
import MetricCardWithTooltip from './MetricCardWithTooltip'
import './AdminPanel.css'

interface AIResponseStatisticsPanelProps {
  days: number
}

export default function AIResponseStatisticsPanel({ days }: AIResponseStatisticsPanelProps) {
  const [statistics, setStatistics] = useState<any>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStatistics()
  }, [days])

  const loadStatistics = async () => {
    try {
      setLoading(true)
      const response = await adminApi.getAiResponseStatistics(days)
      if (response.success) {
        setStatistics(response.data)
      }
    } catch (err) {
      console.error('Failed to load AI response statistics:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="admin-panel">
        <div className="panel-header">
          <h2>AI response feedback</h2>
        </div>
        <div className="panel-content">
          <div className="loading-container">
            <div className="spinner" />
            <p>Loading AI response statistics...</p>
          </div>
        </div>
      </div>
    )
  }

  if (!statistics) return null

  const helpfulCount = statistics.helpful_count ?? 0
  const notHelpfulCount = statistics.not_helpful_count ?? 0
  const totalFeedback = helpfulCount + notHelpfulCount
  const helpfulPercentage = statistics.helpful_percentage ?? 0
  const helpfulColor = helpfulPercentage >= 70 ? '#10b981' : helpfulPercentage >= 50 ? '#f59e0b' : '#ef4444'

  const feedbackPieData = [
    { name: 'Helpful', value: helpfulCount, color: '#10b981' },
    { name: 'Not helpful', value: notHelpfulCount, color: '#ef4444' },
  ].filter((d) => d.value > 0)

  return (
    <div className="admin-panel ai-response-panel">
      <div className="panel-header">
        <h2>AI response feedback</h2>
        <button onClick={loadStatistics} className="btn-refresh">Refresh</button>
      </div>
      <div className="panel-content">
        <div className="metrics-grid">
          <MetricCardWithTooltip
            label="Total responses"
            value={statistics.total_responses ?? 0}
            subtitle={`Last ${days} days`}
            icon="🤖"
            metricKey="ai_response.total_responses"
          />
          <MetricCardWithTooltip
            label="Responses with feedback"
            value={statistics.responses_with_feedback ?? 0}
            subtitle={statistics.total_responses > 0 ? `${((statistics.responses_with_feedback / statistics.total_responses) * 100).toFixed(1)}% of total` : '0% of total'}
            icon="📝"
            description="Number of AI responses that received user feedback (helpful/not helpful)."
          />
          <MetricCardWithTooltip
            label="Helpful"
            value={statistics.helpful_count ?? 0}
            subtitle={`${helpfulPercentage.toFixed(1)}% of feedback`}
            icon="👍"
            color={helpfulColor}
            metricKey="ai_response.helpful_percentage"
          />
          <MetricCardWithTooltip
            label="Not helpful"
            value={statistics.not_helpful_count ?? 0}
            subtitle={`${(statistics.not_helpful_percentage ?? 0).toFixed(1)}% of feedback`}
            icon="👎"
            description="Number of AI responses marked as not helpful by users."
          />
          <MetricCardWithTooltip
            label="Average rating"
            value={typeof statistics.avg_rating === 'number' ? statistics.avg_rating.toFixed(2) : '0.00'}
            subtitle="Out of 5.0"
            icon="⭐"
            metricKey="ai_response.avg_rating"
          />
          <MetricCardWithTooltip
            label="Avg response time"
            value={typeof statistics.avg_response_time_ms === 'number' ? `${(statistics.avg_response_time_ms / 1000).toFixed(2)}s` : '0.00s'}
            subtitle="Time to generate"
            icon="⚡"
            metricKey="ai_response.avg_response_time_ms"
          />
        </div>
        {feedbackPieData.length > 0 && (
          <div className="panel-chart">
            <h3 className="chart-title">Feedback breakdown</h3>
            <p className="chart-description">How users rated AI responses (helpful vs not helpful)</p>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie
                  data={feedbackPieData}
                  cx="50%"
                  cy="50%"
                  innerRadius={40}
                  outerRadius={75}
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
