import { useState, useEffect } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { useAuth } from '../../providers/AuthProvider'
import { surveysApi } from '../../services/apiClient'
import './SurveyForm.css'

interface Question {
  id: string
  text: string
  type: 'single_choice' | 'multiple_choice' | 'text'
  options?: string[]
  required: boolean
  conditional?: {
    question: string
    value: string
  }
}

interface Section {
  title: string
  questions: Question[]
}

interface SurveyData {
  survey_type: string
  title: string
  description: string
  sections: Section[]
  is_completed: boolean
}

export default function SurveyForm() {
  const { surveyType } = useParams<{ surveyType: string }>()
  const { isAuthenticated, initializing } = useAuth()
  const navigate = useNavigate()
  const [surveyData, setSurveyData] = useState<SurveyData | null>(null)
  const [responses, setResponses] = useState<Record<string, any>>({})
  const [loading, setLoading] = useState(true)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (initializing) return
    if (!isAuthenticated) {
      navigate('/')
      return
    }

    if (surveyType) {
      loadSurvey()
    }
  }, [surveyType, isAuthenticated, initializing, navigate])

  const loadSurvey = async () => {
    if (!surveyType) return

    try {
      setLoading(true)
      setError(null)
      const response = await surveysApi.getSurveyQuestions(surveyType)
      if (response.success && response.data) {
        setSurveyData(response.data)
        if (response.data.is_completed) {
          navigate('/pilot')
        }
      } else {
        // Extract error message from response if available
        const errorData = (response as any)?.data
        const errorMsg = errorData?.message || (response as any)?.message || 'Failed to load survey'
        setError(errorMsg)
      }
    } catch (err: any) {
      console.error('Error loading survey:', err)
      // Check for specific error messages
      let errorMessage = 'Failed to load survey'
      if (err.message) {
        if (err.message.includes('not available') || err.message.includes('Survey is not available')) {
          errorMessage = 'This survey is not currently available. An administrator needs to make it visible first.'
        } else if (err.message.includes('Invalid survey type') || err.message.includes('not found')) {
          errorMessage = 'Invalid survey type. Please try again from the surveys list.'
        } else {
          errorMessage = err.message
        }
      }
      setError(errorMessage)
    } finally {
      setLoading(false)
    }
  }

  const handleResponseChange = (questionId: string, value: any) => {
    setResponses((prev) => ({
      ...prev,
      [questionId]: value,
    }))
  }

  const isQuestionVisible = (question: Question): boolean => {
    if (!question.conditional) return true
    const conditionalValue = responses[question.conditional.question]
    const expected = question.conditional.value
    // For multiple_choice, response is an array; show if it contains the value (e.g. "Other")
    if (Array.isArray(conditionalValue)) return conditionalValue.includes(expected)
    return conditionalValue === expected
  }

  const validateForm = (): boolean => {
    if (!surveyData) return false

    for (const section of surveyData.sections) {
      for (const question of section.questions) {
        if (question.required && isQuestionVisible(question)) {
          const value = responses[question.id]
          if (!value || (Array.isArray(value) && value.length === 0)) {
            setError(`Please answer: ${question.text}`)
            return false
          }
        }
      }
    }
    return true
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()

    if (!validateForm()) {
      return
    }

    if (!surveyType) return

    try {
      setSubmitting(true)
      setError(null)
      const response = await surveysApi.submitSurvey(surveyType, responses)
      
      // Check if response indicates success
      if (response && (response.success === true || (response as any).data)) {
        // Navigate back to surveys list with success message
        navigate('/pilot', { 
          state: { message: 'Survey submitted successfully!' },
          replace: true  // Replace current history entry
        })
      } else {
        // Extract error message from response if available
        const errorData = (response as any)?.data
        const errorMsg = errorData?.message || (response as any)?.message || 'Failed to submit survey'
        setError(errorMsg)
      }
    } catch (err: any) {
      console.error('Error submitting survey:', err)
      // Extract more specific error message
      const errorMsg = err?.response?.data?.message || err?.message || 'Failed to submit survey'
      setError(errorMsg)
    } finally {
      setSubmitting(false)
    }
  }

  if (loading) {
    return (
      <div className="survey-form-page">
        <div className="survey-form-container">
          <div className="loading-state">
            <i className="fas fa-spinner fa-spin" />
            <p>Loading survey...</p>
          </div>
        </div>
      </div>
    )
  }

  if (!surveyData) {
    return (
      <div className="survey-form-page">
        <div className="survey-form-container">
          <div className="error-state">
            <i className="fas fa-exclamation-triangle" />
            <p>{error || 'Survey not found'}</p>
            <button className="btn-back" onClick={() => navigate('/pilot')}>
              Back to Surveys
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="survey-form-page">
      <div className="survey-form-container">
        <div className="survey-form-header">
          <div className="survey-form-header-content">
            <div>
              <h1>{surveyData.title}</h1>
              <p className="survey-description">{surveyData.description}</p>
            </div>
            <div className="survey-form-header-actions">
              <button className="btn-back" onClick={() => navigate('/pilot')}>
                ← Back to Surveys
              </button>
              <button className="btn-back" onClick={() => navigate('/')}>
                ← Back to Chat
              </button>
            </div>
          </div>
        </div>

        {error && (
          <div className="alert alert-error">
            <i className="fas fa-exclamation-circle" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="survey-form">
          {surveyData.sections.map((section, sectionIndex) => (
            <div key={sectionIndex} className="survey-section">
              <h2 className="section-title">{section.title}</h2>
              {section.questions.map((question) => {
                if (!isQuestionVisible(question)) return null

                return (
                  <div key={question.id} className="question-group">
                    <label className="question-label">
                      {question.text}
                      {question.required && <span className="required">*</span>}
                    </label>

                    {question.type === 'single_choice' && question.options && (
                      <div className="options-group">
                        {question.options.map((option) => (
                          <label key={option} className="option-label">
                            <input
                              type="radio"
                              name={question.id}
                              value={option}
                              checked={responses[question.id] === option}
                              onChange={(e) => handleResponseChange(question.id, e.target.value)}
                              required={question.required}
                            />
                            <span>{option}</span>
                          </label>
                        ))}
                      </div>
                    )}

                    {question.type === 'multiple_choice' && question.options && (
                      <div className="options-group">
                        {question.options.map((option) => (
                          <label key={option} className="option-label">
                            <input
                              type="checkbox"
                              checked={(responses[question.id] || []).includes(option)}
                              onChange={(e) => {
                                const current = responses[question.id] || []
                                if (e.target.checked) {
                                  handleResponseChange(question.id, [...current, option])
                                } else {
                                  handleResponseChange(
                                    question.id,
                                    current.filter((v: string) => v !== option),
                                  )
                                }
                              }}
                            />
                            <span>{option}</span>
                          </label>
                        ))}
                      </div>
                    )}

                    {question.type === 'text' && (
                      <textarea
                        className="text-input"
                        value={responses[question.id] || ''}
                        onChange={(e) => handleResponseChange(question.id, e.target.value)}
                        required={question.required}
                        rows={4}
                        placeholder="Enter your response..."
                      />
                    )}
                  </div>
                )
              })}
            </div>
          ))}

          <div className="form-actions">
            <button type="button" className="btn-cancel" onClick={() => navigate('/pilot')}>
              Cancel
            </button>
            <button type="submit" className="btn-submit" disabled={submitting}>
              {submitting ? (
                <>
                  <i className="fas fa-spinner fa-spin" />
                  Submitting...
                </>
              ) : (
                <>
                  Submit Survey
                  <i className="fas fa-check" />
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}
