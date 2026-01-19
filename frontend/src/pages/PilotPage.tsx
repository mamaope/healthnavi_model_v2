import { useState, useEffect } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../providers/AuthProvider'
import { surveysApi } from '../services/apiClient'
import './PilotPage.css'

interface Survey {
  survey_type: string
  title: string
  description: string
  is_completed: boolean
  completed_at: string | null
}

export default function PilotPage() {
  const { isAuthenticated, initializing } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [surveys, setSurveys] = useState<Survey[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  useEffect(() => {
    if (initializing) return
    if (!isAuthenticated) {
      navigate('/')
      return
    }

    // Check for success message from navigation state
    if (location.state?.message) {
      setSuccessMessage(location.state.message)
      // Clear the state to prevent showing the message again on refresh
      window.history.replaceState({}, document.title)
      // Auto-hide success message after 5 seconds
      setTimeout(() => setSuccessMessage(null), 5000)
    }

    loadSurveys()
  }, [isAuthenticated, initializing, navigate, location.state])

  const loadSurveys = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await surveysApi.getAvailableSurveys()
      if (response.success && response.data) {
        setSurveys(response.data.surveys || [])
      } else {
        setError('Failed to load surveys')
      }
    } catch (err: any) {
      console.error('Error loading surveys:', err)
      setError(err.message || 'Failed to load surveys')
    } finally {
      setLoading(false)
    }
  }

  const handleSurveyClick = (surveyType: string) => {
    navigate(`/pilot/survey/${surveyType}`)
  }

  if (loading) {
    return (
      <div className="pilot-page">
        <div className="pilot-container">
          <div className="loading-state">
            <i className="fas fa-spinner fa-spin" />
            <p>Loading surveys...</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="pilot-page">
      <div className="pilot-container">
        <div className="pilot-header">
          <div className="pilot-header-content">
            <div>
              <h1>Pilot Surveys</h1>
              <p className="pilot-description">
                Complete the surveys below to help us improve the platform. Your feedback is essential.
              </p>
            </div>
            <button onClick={() => navigate('/')} className="btn-back">
              ← Back to Chat
            </button>
          </div>
        </div>

        {successMessage && (
          <div className="alert alert-success">
            <i className="fas fa-check-circle" />
            <span>{successMessage}</span>
          </div>
        )}

        {error && (
          <div className="alert alert-error">
            <i className="fas fa-exclamation-circle" />
            <span>{error}</span>
          </div>
        )}

        {surveys.length === 0 && !loading && (
          <div className="empty-state">
            <i className="fas fa-clipboard-list" />
            <h3>No surveys available</h3>
            <p>There are currently no surveys available. Surveys need to be enabled by an administrator.</p>
            <p style={{ fontSize: '0.9rem', color: '#6c757d', marginTop: '0.5rem' }}>
              If you're an admin, go to the Admin Dashboard → Survey Management to enable surveys.
            </p>
          </div>
        )}

        <div className="surveys-grid">
          {surveys.map((survey) => (
            <div
              key={survey.survey_type}
              className={`survey-card ${survey.is_completed ? 'completed' : ''}`}
              onClick={() => !survey.is_completed && handleSurveyClick(survey.survey_type)}
            >
              <div className="survey-card-header">
                <h3>{survey.title}</h3>
                {survey.is_completed && (
                  <span className="survey-badge completed-badge">
                    <i className="fas fa-check-circle" />
                    Completed
                  </span>
                )}
                {!survey.is_completed && (
                  <span className="survey-badge pending-badge">
                    <i className="fas fa-clock" />
                    Pending
                  </span>
                )}
              </div>
              <p className="survey-description">{survey.description}</p>
              {survey.is_completed && survey.completed_at && (
                <div className="survey-meta">
                  <i className="fas fa-calendar-check" />
                  <span>Completed on {new Date(survey.completed_at).toLocaleDateString()}</span>
                </div>
              )}
              {!survey.is_completed && (
                <button className="btn-start-survey">
                  Start Survey
                  <i className="fas fa-arrow-right" />
                </button>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
