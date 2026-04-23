import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '../providers/AuthProvider'
import { adminApi, surveysApi } from '../services/apiClient'
import './SurveySubmissionsPage.css'

interface SurveySubmission {
  id: number
  user_id: number
  user_name: string
  user_email: string
  survey_type: string
  pmf_score: number | null
  very_disappointed: boolean | null
  willingness_to_pay: number | null
  replacement_behavior: string | null
  time_saved_minutes: number | null
  usefulness_score: number | null
  query_relevance: boolean | null
  survey_data: Record<string, any> | null
  created_at: string
}

export default function SurveySubmissionsPage() {
  const { user, isAuthenticated, initializing } = useAuth()
  const navigate = useNavigate()
  const userRole = user?.role ?? ''
  const [surveys, setSurveys] = useState<SurveySubmission[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [selectedSurveyType, setSelectedSurveyType] = useState<string>('')
  const [startDate, setStartDate] = useState<string>('')
  const [endDate, setEndDate] = useState<string>('')
  const [selectedSubmission, setSelectedSubmission] = useState<SurveySubmission | null>(null)
  const [surveyQuestions, setSurveyQuestions] = useState<any>(null)
  const [loadingQuestions, setLoadingQuestions] = useState(false)
  const [exportingExcel, setExportingExcel] = useState(false)
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const limit = 20

  useEffect(() => {
    if (initializing) return
    if (!isAuthenticated || !user || !['admin', 'super_admin'].includes(userRole)) {
      navigate('/')
      return
    }
    if (startDate && endDate && new Date(startDate) > new Date(endDate)) {
      setError('Start date cannot be after end date')
      return
    }
    loadSurveys()
  }, [isAuthenticated, user, userRole, initializing, selectedSurveyType, startDate, endDate, page, navigate])

  const loadSurveys = async () => {
    try {
      setLoading(true)
      setError(null)
      const offset = (page - 1) * limit
      const response = await adminApi.getSurveys(
        selectedSurveyType || undefined,
        limit,
        offset,
        startDate || undefined,
        endDate || undefined,
      )
      if (response.success && response.data) {
        setSurveys(response.data.surveys || [])
        setTotal(response.data.total || 0)
      } else {
        setError('Failed to load survey submissions')
      }
    } catch (err: any) {
      console.error('Error loading surveys:', err)
      setError(err.message || 'Failed to load survey submissions')
    } finally {
      setLoading(false)
    }
  }

  const getSurveyTypeLabel = (type: string) => {
    const labels: Record<string, string> = {
      baseline: 'Pre-Pilot Survey',
      mid: 'Mid-Pilot Survey',
      final: 'Post-Pilot Survey',
    }
    return labels[type] || type
  }

  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString()
  }

  const loadSurveyQuestions = async (surveyType: string) => {
    try {
      setLoadingQuestions(true)
      const response = await surveysApi.getSurveyQuestions(surveyType)
      if (response.success && response.data) {
        setSurveyQuestions(response.data)
      }
    } catch (err: any) {
      console.error('Error loading survey questions:', err)
    } finally {
      setLoadingQuestions(false)
    }
  }

  const handleSubmissionClick = (submission: SurveySubmission) => {
    setSelectedSubmission(submission)
    if (submission.survey_type) {
      loadSurveyQuestions(submission.survey_type)
    }
  }

  const renderSurveyData = (surveyData: Record<string, any> | null) => {
    if (!surveyData) return null

    if (surveyQuestions && surveyQuestions.sections) {
      // Render with questions organized by sections
      return (
        <div className="survey-data-display">
          {surveyQuestions.sections.map((section: any, sectionIndex: number) => {
            const sectionAnswers: Array<{ question: any; answer: any }> = []
            
            section.questions?.forEach((question: any) => {
              if (surveyData[question.id] !== undefined && surveyData[question.id] !== null && surveyData[question.id] !== '') {
                sectionAnswers.push({
                  question,
                  answer: surveyData[question.id]
                })
              }
            })

            if (sectionAnswers.length === 0) return null

            return (
              <div key={sectionIndex} className="survey-section-group">
                <h4 className="section-group-title">{section.title}</h4>
                {sectionAnswers.map(({ question, answer }, idx) => (
                  <div key={idx} className="survey-qa-item">
                    <div className="survey-question">
                      <strong>{question.id}:</strong> {question.text}
                    </div>
                    <div className="survey-answer">
                      {Array.isArray(answer) ? (
                        <ul className="answer-list">
                          {answer.map((item: string, i: number) => (
                            <li key={i}>{item}</li>
                          ))}
                        </ul>
                      ) : (
                        <span>{String(answer)}</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )
          })}
        </div>
      )
    }

    // Fallback: render without questions if not loaded yet
    return (
      <div className="survey-data-display">
        {Object.entries(surveyData).map(([key, value]) => (
          <div key={key} className="survey-data-item">
            <strong>{key}:</strong>
            <span>{Array.isArray(value) ? value.join(', ') : String(value)}</span>
          </div>
        ))}
      </div>
    )
  }

  const normalizeCellValue = (value: unknown): string | number | boolean => {
    if (value === null || value === undefined) return ''
    if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
      return value
    }
    return JSON.stringify(value)
  }

  const fetchAllFilteredSurveys = async (): Promise<SurveySubmission[]> => {
    const exportBatchSize = 500
    let offset = 0
    let fetchedTotal = Infinity
    const all: SurveySubmission[] = []

    while (offset < fetchedTotal) {
      const response = await adminApi.getSurveys(
        selectedSurveyType || undefined,
        exportBatchSize,
        offset,
        startDate || undefined,
        endDate || undefined,
      )
      if (!response.success || !response.data) {
        throw new Error('Failed to load surveys for export')
      }
      const chunk = (response.data.surveys || []) as SurveySubmission[]
      all.push(...chunk)
      fetchedTotal = response.data.total || chunk.length
      offset += exportBatchSize
      if (chunk.length === 0) break
    }

    return all
  }

  const handleExportExcel = async () => {
    try {
      setExportingExcel(true)
      setError(null)

      const allSurveys = await fetchAllFilteredSurveys()
      if (allSurveys.length === 0) {
        setError('No submissions available to export')
        return
      }

      const responseKeys = new Set<string>()
      allSurveys.forEach((submission) => {
        Object.keys(submission.survey_data || {}).forEach((key) => responseKeys.add(key))
      })
      const sortedResponseKeys = [...responseKeys].sort()

      const rows = allSurveys.map((submission) => {
        const base: Record<string, string | number | boolean> = {
          submission_id: submission.id,
          user_id: submission.user_id,
          user_name: submission.user_name || '',
          user_email: submission.user_email || '',
          survey_type: submission.survey_type || '',
          submitted_at: submission.created_at,
          pmf_score: submission.pmf_score ?? '',
          very_disappointed: submission.very_disappointed ?? '',
          willingness_to_pay: submission.willingness_to_pay ?? '',
          replacement_behavior: submission.replacement_behavior ?? '',
          time_saved_minutes: submission.time_saved_minutes ?? '',
          usefulness_score: submission.usefulness_score ?? '',
          query_relevance: submission.query_relevance ?? '',
        }

        const responses = submission.survey_data || {}
        sortedResponseKeys.forEach((key) => {
          base[`response_${key}`] = normalizeCellValue(responses[key])
        })

        return base
      })

      const XLSX = await import('xlsx')
      const worksheet = XLSX.utils.json_to_sheet(rows)
      const workbook = XLSX.utils.book_new()
      XLSX.utils.book_append_sheet(workbook, worksheet, 'Survey Submissions')

      const datePart = new Date().toISOString().slice(0, 10)
      const filterPart = selectedSurveyType ? `_${selectedSurveyType}` : '_all'
      const rangePart =
        startDate && endDate ? `_${startDate}_to_${endDate}` : ''
      XLSX.writeFile(workbook, `survey_submissions${filterPart}${rangePart}_${datePart}.xlsx`)
    } catch (err: any) {
      console.error('Error exporting surveys to Excel:', err)
      setError(err.message || 'Failed to export surveys to Excel')
    } finally {
      setExportingExcel(false)
    }
  }

  if (initializing) {
    return (
      <div className="survey-submissions-page">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated || !user || !['admin', 'super_admin'].includes(userRole)) {
    return null
  }

  const totalPages = Math.ceil(total / limit)

  return (
    <div className="survey-submissions-page">
      <div className="submissions-container">
        <div className="submissions-header">
          <div>
            <h1>Survey Submissions</h1>
            <p className="submissions-description">
              Review and analyze survey responses from users
            </p>
          </div>
          <button onClick={() => navigate('/admin')} className="btn-back">
            ← Back to Dashboard
          </button>
        </div>

        <div className="submissions-filters">
          <select
            value={selectedSurveyType}
            onChange={(e) => {
              setSelectedSurveyType(e.target.value)
              setPage(1)
            }}
            className="filter-select"
          >
            <option value="">All Surveys</option>
            <option value="baseline">Pre-Pilot Survey</option>
            <option value="mid">Mid-Pilot Survey</option>
            <option value="final">Post-Pilot Survey</option>
          </select>
          <input
            type="date"
            value={startDate}
            onChange={(e) => {
              setStartDate(e.target.value)
              setPage(1)
            }}
            className="filter-date"
            aria-label="Start date"
          />
          <input
            type="date"
            value={endDate}
            onChange={(e) => {
              setEndDate(e.target.value)
              setPage(1)
            }}
            className="filter-date"
            aria-label="End date"
          />
          {(startDate || endDate) && (
            <button
              type="button"
              className="btn-clear-dates"
              onClick={() => {
                setStartDate('')
                setEndDate('')
                setPage(1)
              }}
            >
              Clear dates
            </button>
          )}
          <div className="submissions-count">
            {total} total submission{total !== 1 ? 's' : ''}
          </div>
          <button
            onClick={handleExportExcel}
            className="btn-export-excel"
            disabled={loading || exportingExcel}
          >
            {exportingExcel ? (
              <>
                <i className="fas fa-spinner fa-spin" />
                Exporting...
              </>
            ) : (
              <>
                <i className="fas fa-file-excel" />
                Export Excel
              </>
            )}
          </button>
        </div>

        {error && (
          <div className="alert alert-error">
            <i className="fas fa-exclamation-circle" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="loading-state">
            <i className="fas fa-spinner fa-spin" />
            <p>Loading submissions...</p>
          </div>
        ) : surveys.length === 0 ? (
          <div className="empty-state">
            <i className="fas fa-clipboard-list" />
            <h3>No submissions found</h3>
            <p>No survey submissions match your filters.</p>
          </div>
        ) : (
          <>
            <div className="submissions-list">
              {surveys.map((survey) => (
                <div
                  key={survey.id}
                  className="submission-card"
                  onClick={() => handleSubmissionClick(survey)}
                >
                  <div className="submission-header">
                    <div>
                      <h3>{getSurveyTypeLabel(survey.survey_type)}</h3>
                      <p className="submission-user">
                        {survey.user_name} ({survey.user_email})
                      </p>
                    </div>
                    <div className="submission-meta">
                      <span className="submission-date">
                        {formatDate(survey.created_at)}
                      </span>
                    </div>
                  </div>
                  <div className="submission-preview">
                    {survey.pmf_score !== null && (
                      <span className="preview-badge">PMF Score: {survey.pmf_score}</span>
                    )}
                    {survey.very_disappointed !== null && (
                      <span className="preview-badge">
                        {survey.very_disappointed ? 'Very Disappointed' : 'Not Disappointed'}
                      </span>
                    )}
                    {survey.time_saved_minutes !== null && (
                      <span className="preview-badge">
                        {survey.time_saved_minutes} min saved
                      </span>
                    )}
                  </div>
                </div>
              ))}
            </div>

            {totalPages > 1 && (
              <div className="pagination">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="btn-pagination"
                >
                  Previous
                </button>
                <span className="page-info">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page === totalPages}
                  className="btn-pagination"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>

      {selectedSubmission && (
        <div className="modal-overlay" onClick={() => {
          setSelectedSubmission(null)
          setSurveyQuestions(null)
        }}>
          <div className="modal-content modal-content-wide" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>{getSurveyTypeLabel(selectedSubmission.survey_type)}</h2>
              <button
                className="btn-close"
                onClick={() => {
                  setSelectedSubmission(null)
                  setSurveyQuestions(null)
                }}
              >
                <i className="fas fa-times" />
              </button>
            </div>
            <div className="modal-body">
              <div className="submission-details">
                <div className="detail-section">
                  <h3>User Information</h3>
                  <p><strong>Name:</strong> {selectedSubmission.user_name}</p>
                  <p><strong>Email:</strong> {selectedSubmission.user_email}</p>
                  <p><strong>Submitted:</strong> {formatDate(selectedSubmission.created_at)}</p>
                </div>

                {(selectedSubmission.pmf_score !== null ||
                  selectedSubmission.very_disappointed !== null ||
                  selectedSubmission.willingness_to_pay !== null ||
                  selectedSubmission.replacement_behavior ||
                  selectedSubmission.time_saved_minutes !== null ||
                  selectedSubmission.usefulness_score !== null) && (
                  <div className="detail-section">
                    <h3>PMF Metrics</h3>
                    {selectedSubmission.pmf_score !== null && (
                      <p><strong>PMF Score:</strong> {selectedSubmission.pmf_score}/10</p>
                    )}
                    {selectedSubmission.very_disappointed !== null && (
                      <p>
                        <strong>Very Disappointed:</strong>{' '}
                        {selectedSubmission.very_disappointed ? 'Yes' : 'No'}
                      </p>
                    )}
                    {selectedSubmission.willingness_to_pay !== null && (
                      <p>
                        <strong>Willingness to Pay:</strong> ${selectedSubmission.willingness_to_pay}
                      </p>
                    )}
                    {selectedSubmission.replacement_behavior && (
                      <p>
                        <strong>Replacement Behavior:</strong>{' '}
                        {selectedSubmission.replacement_behavior}
                      </p>
                    )}
                    {selectedSubmission.time_saved_minutes !== null && (
                      <p>
                        <strong>Time Saved:</strong> {selectedSubmission.time_saved_minutes} minutes
                      </p>
                    )}
                    {selectedSubmission.usefulness_score !== null && (
                      <p>
                        <strong>Usefulness Score:</strong> {selectedSubmission.usefulness_score}/5
                      </p>
                    )}
                  </div>
                )}

                {selectedSubmission.survey_data && (
                  <div className="detail-section">
                    <h3>Survey Responses</h3>
                    {loadingQuestions ? (
                      <div className="loading-questions">
                        <i className="fas fa-spinner fa-spin" />
                        <span>Loading questions...</span>
                      </div>
                    ) : (
                      renderSurveyData(selectedSubmission.survey_data)
                    )}
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
