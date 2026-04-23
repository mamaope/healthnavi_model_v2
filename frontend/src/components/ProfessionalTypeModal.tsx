import { useState } from 'react'
import { createPortal } from 'react-dom'
import { authApi } from '../services/apiClient'
import { useAuth } from '../providers/AuthProvider'

interface ProfessionalTypeModalProps {
  isOpen: boolean
  onClose: () => void
}

const PROFESSIONAL_TYPES = [
  'Consultant',
  'Specialist',
  'Senior House Officer',
  'Medical Officer',
  'Intern Clinician',
  'Other Clinical Practitioner',
  'Clinical/Medical Student',
]

export function ProfessionalTypeModal({ isOpen, onClose }: ProfessionalTypeModalProps) {
  const { refreshProfile } = useAuth()
  const [selectedType, setSelectedType] = useState<string>('')
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [error, setError] = useState<string>('')

  if (!isOpen) return null

  const handleSubmit = async () => {
    if (!selectedType) {
      setError('Please select your medical professional type')
      return
    }

    setIsSubmitting(true)
    setError('')

    try {
      const response = await authApi.updateProfile({ medical_professional_type: selectedType })
      // Check if response has data (indicates success)
      // Backend returns success: 1 (or true) for success, 0 (or false) for error
      const responseAny = response as any
      const isSuccess = response && response.data
      if (isSuccess) {
        // Close modal immediately after successful update
        onClose()
        // Refresh profile in background (don't wait for it)
        refreshProfile().catch(err => {
          console.error('Failed to refresh profile after update:', err)
        })
      } else {
        // Update failed - extract error message
        const errorMsg = responseAny?.message || responseAny?.data?.message || 'Failed to update profile. Please try again.'
        setError(errorMsg)
        setIsSubmitting(false)
      }
    } catch (err: any) {
      console.error('Failed to update profile:', err)
      // Extract error message from response
      const errorMessage = err?.response?.data?.message || 
                          err?.message || 
                          'Failed to update profile. Please try again.'
      setError(errorMessage)
      setIsSubmitting(false)
    }
  }

  const handleClose = () => {
    // Don't allow closing without selecting a type for first-time users
    // This ensures users complete their profile setup
    if (!isSubmitting && selectedType) {
      onClose()
    }
  }

  const modalContent = (
    <div className="professional-type-modal-overlay" onClick={(e) => {
      // Prevent closing by clicking outside - user must select a type
      e.stopPropagation()
    }}>
      <div className="professional-type-modal" onClick={(e) => e.stopPropagation()}>
        <div className="professional-type-modal-header">
          <h2>Select Your Medical Professional Type</h2>
          {/* Close button disabled for first-time users - they must select a type */}
          {selectedType && (
            <button
              type="button"
              className="professional-type-modal-close"
              onClick={handleClose}
              disabled={isSubmitting}
              aria-label="Close modal"
            >
              <i className="fas fa-times" />
            </button>
          )}
        </div>

        <div className="professional-type-modal-content">
          <p className="professional-type-modal-description">
            Please select your medical professional type to help us personalize your experience.
          </p>

          <div className="professional-type-options">
            {PROFESSIONAL_TYPES.map((type) => (
              <button
                key={type}
                type="button"
                className={`professional-type-option ${
                  selectedType === type ? 'selected' : ''
                }`}
                onClick={async () => {
                  if (isSubmitting) return
                  
                  setSelectedType(type)
                  setError('')
                  
                  // Auto-submit when a profession is selected
                  setIsSubmitting(true)
                  try {
                    const response = await authApi.updateProfile({ medical_professional_type: type })
                    // Check if response has data (indicates success)
                    // Backend returns success: 1 (or true) for success, 0 (or false) for error
                    const responseAny = response as any
                    const isSuccess = response && response.data
                    if (isSuccess) {
                      // Close modal immediately after successful update
                      onClose()
                      // Refresh profile in background (don't wait for it)
                      refreshProfile().catch(err => {
                        console.error('Failed to refresh profile after update:', err)
                      })
                    } else {
                      // Update failed - extract error message
                      const errorMsg = responseAny?.message || responseAny?.data?.message || 'Failed to update profile. Please try again.'
                      setError(errorMsg)
                      setIsSubmitting(false)
                    }
                  } catch (err: any) {
                    console.error('Failed to update profile:', err)
                    // Extract error message from response
                    const errorMessage = err?.response?.data?.message || 
                                       err?.message || 
                                       'Failed to update profile. Please try again.'
                    setError(errorMessage)
                    setIsSubmitting(false)
                  }
                }}
                disabled={isSubmitting}
              >
                <span className="professional-type-option-text">{type}</span>
                {selectedType === type && (
                  <i className="fas fa-check professional-type-option-check" />
                )}
              </button>
            ))}
          </div>

          {error && (
            <div className="professional-type-modal-error">
              <i className="fas fa-exclamation-circle" />
              <span>{error}</span>
            </div>
          )}
        </div>

        <div className="professional-type-modal-footer">
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={isSubmitting || !selectedType}
          >
            {isSubmitting ? (
              <>
                <i className="fas fa-spinner fa-spin" /> Saving...
              </>
            ) : (
              'Continue'
            )}
          </button>
        </div>
      </div>
    </div>
  )

  return createPortal(modalContent, document.body)
}

