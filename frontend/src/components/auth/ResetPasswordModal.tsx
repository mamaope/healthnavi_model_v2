import { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { authApi } from '../../services/apiClient'

interface ResetPasswordModalProps {
  isOpen: boolean
  token: string
  onClose: () => void
  onSuccess: () => void
}

interface ResetPasswordFormValues {
  newPassword: string
  confirmPassword: string
}

export function ResetPasswordModal({
  isOpen,
  token,
  onClose,
  onSuccess,
}: ResetPasswordModalProps) {
  const [serverError, setServerError] = useState<string | null>(null)
  const [serverSuccess, setServerSuccess] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)

  const {
    register: registerField,
    handleSubmit,
    reset,
    formState: { errors },
    watch,
  } = useForm<ResetPasswordFormValues>({
    defaultValues: {
      newPassword: '',
      confirmPassword: '',
    },
  })

  const confirmPassword = watch('confirmPassword')

  useEffect(() => {
    if (isOpen) {
      setServerError(null)
      setServerSuccess(null)
      setIsSubmitting(false)
      reset()
    }
  }, [isOpen, reset])

  useEffect(() => {
    if (!isOpen) return

    const handleKeydown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeydown)
    return () => window.removeEventListener('keydown', handleKeydown)
  }, [isOpen, onClose])

  const onSubmit = handleSubmit(async (values: ResetPasswordFormValues) => {
    if (values.newPassword !== values.confirmPassword) {
      setServerError('Passwords do not match.')
      return
    }

    setServerError(null)
    setServerSuccess(null)
    setIsSubmitting(true)
    try {
      const response = await authApi.resetPassword(token, values.newPassword)
      if (response.success && response.data?.message) {
        setServerSuccess(response.data.message)
        // Auto-close and redirect to login after 2 seconds
        setTimeout(() => {
          onSuccess()
        }, 2000)
      } else {
        setServerError('Failed to reset password. Please try again.')
      }
    } catch (error) {
      if (error instanceof Error) {
        setServerError(error.message)
      } else {
        setServerError('Something went wrong. Please try again.')
      }
    } finally {
      setIsSubmitting(false)
    }
  })

  const modalClassName = useMemo(
    () => `modal ${isOpen ? 'show' : ''}`,
    [isOpen],
  )

  if (!isOpen) {
    return null
  }

  return (
    <div
      className={modalClassName}
      role="dialog"
      aria-modal="true"
      aria-labelledby="reset-password-modal-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div className="modal-content" role="document">
        <div className="modal-header">
          <h2 id="reset-password-modal-title">Set New Password</h2>
          <button
            className="modal-close"
            onClick={onClose}
            aria-label="Close dialog"
          >
            &times;
          </button>
        </div>
        <div className="modal-body">
          {serverSuccess ? (
            <div className="auth-success">
              <p>{serverSuccess}</p>
              <p>Redirecting to login...</p>
            </div>
          ) : (
            <>
              <p className="auth-description">
                Please enter your new password below.
              </p>
              <form onSubmit={onSubmit} className="auth-form">
                <div className="form-group">
                  <label htmlFor="reset-password-new">New Password</label>
                  <div style={{ position: 'relative' }}>
                    <input
                      id="reset-password-new"
                      type={showNewPassword ? 'text' : 'password'}
                      autoComplete="new-password"
                      placeholder="Enter your new password"
                      style={{ paddingRight: '40px' }}
                      {...registerField('newPassword', {
                        required: 'Password is required',
                        minLength: {
                          value: 4,
                          message: 'Password must be at least 4 characters long',
                        },
                      })}
                    />
                    <button
                      type="button"
                      onClick={() => setShowNewPassword(!showNewPassword)}
                      style={{
                        position: 'absolute',
                        right: '10px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--text-tertiary)',
                        padding: '5px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                      aria-label={showNewPassword ? 'Hide password' : 'Show password'}
                    >
                      <i className={showNewPassword ? 'fas fa-eye-slash' : 'fas fa-eye'} />
                    </button>
                  </div>
                  {errors.newPassword && (
                    <span className="form-error">
                      {errors.newPassword.message}
                    </span>
                  )}
                </div>

                <div className="form-group">
                  <label htmlFor="reset-password-confirm">
                    Confirm New Password
                  </label>
                  <div style={{ position: 'relative' }}>
                    <input
                      id="reset-password-confirm"
                      type={showConfirmPassword ? 'text' : 'password'}
                      autoComplete="new-password"
                      placeholder="Re-enter your new password"
                      style={{ paddingRight: '40px' }}
                      {...registerField('confirmPassword', {
                        required: 'Please confirm your password',
                        validate: (value: string) =>
                          value === confirmPassword || 'Passwords do not match',
                      })}
                    />
                    <button
                      type="button"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      style={{
                        position: 'absolute',
                        right: '10px',
                        top: '50%',
                        transform: 'translateY(-50%)',
                        background: 'none',
                        border: 'none',
                        cursor: 'pointer',
                        color: 'var(--text-tertiary)',
                        padding: '5px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center'
                      }}
                      aria-label={showConfirmPassword ? 'Hide password' : 'Show password'}
                    >
                      <i className={showConfirmPassword ? 'fas fa-eye-slash' : 'fas fa-eye'} />
                    </button>
                  </div>
                  {errors.confirmPassword && (
                    <span className="form-error">
                      {errors.confirmPassword.message}
                    </span>
                  )}
                </div>

                {serverError && (
                  <div className="auth-error">{serverError}</div>
                )}

                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'Resetting…' : 'Reset Password'}
                </button>
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  )
}

