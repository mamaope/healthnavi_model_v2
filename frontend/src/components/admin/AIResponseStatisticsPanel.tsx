import { useState, useEffect } from 'react'
import { adminApi } from '../../services/apiClient'
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
          <h2>AI Response Statistics</h2>
        </div>
        <div className="panel-content">
          <div className="loading-container">
            <div className="spinner"></div>
            <p>Loading AI response statistics...</p>
          </div>
        </div>
      </div>
    )
  }

  if (!statistics) return null

  const helpfulPercentage = statistics.helpful_percentage || 0
  const notHelpfulPercentage = statistics.not_helpful_percentage || 0
  const helpfulColor = helpfulPercentage >= 70 ? '#10b981' : helpfulPercentage >= 50 ? '#f59e0b' : '#ef4444'

  return (
    <div className="admin-panel">
      <div className="panel-header">
        <h2>AI Response Statistics</h2>
        <button onClick={loadStatistics} className="btn-refresh">
          Refresh
        </button>
      </div>
      <div className="panel-content">
        <div className="metrics-grid">
          <MetricCard
            label="Total Responses"
            value={statistics.total_responses || 0}
            subtitle={`Last ${days} days`}
            icon="🤖"
          />
          <MetricCard
            label="Responses with Feedback"
            value={statistics.responses_with_feedback || 0}
            subtitle={`${statistics.total_responses > 0 ? ((statistics.responses_with_feedback / statistics.total_responses) * 100).toFixed(1) : 0}% of total`}
            icon="📝"
          />
          <MetricCard
            label="Helpful Responses"
            value={statistics.helpful_count || 0}
            subtitle={`${helpfulPercentage.toFixed(1)}% of feedback`}
            icon="👍"
            color={helpfulColor}
          />
          <MetricCard
            label="Not Helpful Responses"
            value={statistics.not_helpful_count || 0}
            subtitle={`${notHelpfulPercentage.toFixed(1)}% of feedback`}
            icon="👎"
          />
          <MetricCard
            label="Average Rating"
            value={typeof statistics.avg_rating === 'number' ? statistics.avg_rating.toFixed(2) : '0.00'}
            subtitle="Out of 5.0"
            icon="⭐"
          />
          <MetricCard
            label="Avg Response Time"
            value={typeof statistics.avg_response_time_ms === 'number' ? `${(statistics.avg_response_time_ms / 1000).toFixed(2)}s` : '0.00s'}
            subtitle="Time to generate response"
            icon="⚡"
          />
        </div>
      </div>
    </div>
  )
}

function MetricCard({ label, value, subtitle, icon, color }: { label: string; value: string | number; subtitle?: string; icon?: string; color?: string }) {
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
