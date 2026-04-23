import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { adminApi } from '../../services/apiClient'
import './SurveyStatisticsPanel.css'

interface SurveyStats {
  completed: number
  unique_users_completed: number
  pending: number
  completion_percentage: number
  total_users: number
}

interface SurveyStatistics {
  by_type: {
    baseline: SurveyStats
    mid: SurveyStats
    final: SurveyStats
  }
  overall: {
    total_completed: number
    total_unique_users_completed: number
    total_users: number
    overall_completion_percentage: number
  }
}

export default function SurveyStatisticsPanel({ days }: { days: number }) {
  const navigate = useNavigate()
  const [stats, setStats] = useState<SurveyStatistics | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadStatistics()
  }, [days])

  const loadStatistics = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await adminApi.getSurveyStatistics(days)
      if (response.success && response.data) {
        setStats(response.data)
      } else {
        setError('Failed to load survey statistics')
      }
    } catch (err: any) {
      console.error('Error loading survey statistics:', err)
      setError(err.message || 'Failed to load survey statistics')
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="admin-panel survey-statistics-panel">
        <div className="panel-header">
          <h2>Survey Statistics</h2>
        </div>
        <div className="panel-content">
          <div className="loading-state">
            <i className="fas fa-spinner fa-spin" />
            <p>Loading statistics...</p>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="admin-panel survey-statistics-panel">
        <div className="panel-header">
          <h2>Survey Statistics</h2>
        </div>
        <div className="panel-content">
          <div className="error-state">
            <i className="fas fa-exclamation-triangle" />
            <p>{error}</p>
            <button onClick={loadStatistics} className="btn-retry">
              Retry
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (!stats) {
    return null
  }

  const renderSurveyTypeStats = (type: 'baseline' | 'mid' | 'final', title: string) => {
    const typeStats = stats.by_type[type]
    if (!typeStats) return null

    return (
      <div key={type} className="survey-type-card">
        <div className="survey-type-header">
          <h3>{title}</h3>
          <span className={`completion-badge ${typeStats.completion_percentage >= 50 ? 'good' : typeStats.completion_percentage >= 25 ? 'medium' : 'low'}`}>
            {typeStats.completion_percentage.toFixed(1)}%
          </span>
        </div>
        <div className="survey-stats-grid">
          <div className="stat-item">
            <div className="stat-value">{typeStats.unique_users_completed}</div>
            <div className="stat-label">Completed</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{typeStats.pending}</div>
            <div className="stat-label">Pending</div>
          </div>
          <div className="stat-item">
            <div className="stat-value">{typeStats.total_users}</div>
            <div className="stat-label">Total Users</div>
          </div>
        </div>
        <div className="progress-bar-container">
          <div 
            className="progress-bar" 
            style={{ width: `${typeStats.completion_percentage}%` }}
          />
        </div>
      </div>
    )
  }

  return (
    <div className="admin-panel survey-statistics-panel">
      <div className="panel-header">
        <h2>Survey Statistics</h2>
        <button 
          onClick={() => navigate('/admin/surveys')} 
          className="btn-view-details"
        >
          View All Submissions
          <i className="fas fa-arrow-right" />
        </button>
      </div>
      <div className="panel-content">
        <div className="overall-stats">
          <div className="overall-stat-card" title="Number of distinct users who submitted at least one survey. Completion rate = this ÷ total users × 100.">
            <div className="overall-stat-value">{stats.overall.total_unique_users_completed}</div>
            <div className="overall-stat-label">Users who completed surveys</div>
            <div className="overall-stat-subtext">
              {stats.overall.overall_completion_percentage.toFixed(1)}% of {stats.overall.total_users} total users
            </div>
          </div>
          <div className="overall-stat-card" title="Total number of survey submissions across all survey types (baseline, mid, final).">
            <div className="overall-stat-value">{stats.overall.total_completed}</div>
            <div className="overall-stat-label">Total survey submissions</div>
          </div>
        </div>

        <div className="survey-types-grid">
          {renderSurveyTypeStats('baseline', 'Pre-pilot survey')}
          {renderSurveyTypeStats('mid', 'Mid-pilot survey')}
          {renderSurveyTypeStats('final', 'Post-pilot survey')}
        </div>
      </div>
    </div>
  )
}
