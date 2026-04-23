import { useState, useEffect } from 'react'
import { adminApi } from '../../services/apiClient'
import './SurveyManagementPanel.css'

export default function SurveyManagementPanel() {
  const [configs, setConfigs] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [updating, setUpdating] = useState<Record<string, boolean>>({})

  useEffect(() => {
    loadConfigs()
  }, [])

  const loadConfigs = async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await adminApi.getSurveyConfigs()
      if (response.success && response.data) {
        setConfigs(response.data.configs || [])
      } else {
        setError('Failed to load survey configurations')
      }
    } catch (err: any) {
      console.error('Error loading survey configs:', err)
      setError(err.message || 'Failed to load survey configurations')
    } finally {
      setLoading(false)
    }
  }

  const handleToggleVisibility = async (surveyType: string, currentValue: boolean) => {
    try {
      setUpdating((prev) => ({ ...prev, [surveyType]: true }))
      const response = await adminApi.toggleSurveyVisibility(surveyType, !currentValue)
      if (response.success) {
        // Update local state
        setConfigs((prev) =>
          prev.map((config) =>
            config.survey_type === surveyType
              ? { ...config, is_visible: !currentValue }
              : config,
          ),
        )
      } else {
        setError('Failed to update survey visibility')
      }
    } catch (err: any) {
      console.error('Error updating survey visibility:', err)
      setError(err.message || 'Failed to update survey visibility')
    } finally {
      setUpdating((prev) => ({ ...prev, [surveyType]: false }))
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

  if (loading) {
    return (
      <div className="survey-management-panel">
        <div className="panel-header">
          <h2>Survey Management</h2>
        </div>
        <div className="loading-state">
          <i className="fas fa-spinner fa-spin" />
          <span>Loading...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="survey-management-panel">
      <div className="panel-header">
        <h2>Survey Management</h2>
        <p className="panel-description">
          Control which surveys are visible to users. Toggle visibility to enable or disable surveys.
        </p>
      </div>

      {error && (
        <div className="alert alert-error">
          <i className="fas fa-exclamation-circle" />
          <span>{error}</span>
        </div>
      )}

      <div className="survey-configs-list">
        {configs.map((config) => (
          <div key={config.id} className="survey-config-card">
            <div className="survey-config-info">
              <h3>{config.title || getSurveyTypeLabel(config.survey_type)}</h3>
              <p className="survey-type-badge">{config.survey_type}</p>
              {config.description && (
                <p className="survey-config-description">{config.description}</p>
              )}
            </div>
            <div className="survey-config-actions">
              <div className="visibility-status">
                <span className={`status-badge ${config.is_visible ? 'visible' : 'hidden'}`}>
                  <i className={`fas fa-${config.is_visible ? 'eye' : 'eye-slash'}`} />
                  {config.is_visible ? 'Visible' : 'Hidden'}
                </span>
              </div>
              <button
                className={`btn-toggle ${config.is_visible ? 'btn-hide' : 'btn-show'}`}
                onClick={() => handleToggleVisibility(config.survey_type, config.is_visible)}
                disabled={updating[config.survey_type]}
              >
                {updating[config.survey_type] ? (
                  <>
                    <i className="fas fa-spinner fa-spin" />
                    Updating...
                  </>
                ) : config.is_visible ? (
                  <>
                    <i className="fas fa-eye-slash" />
                    Hide Survey
                  </>
                ) : (
                  <>
                    <i className="fas fa-eye" />
                    Show Survey
                  </>
                )}
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
