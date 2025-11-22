import { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { authApi } from '../../services/apiClient'

interface ForgotPasswordModalProps {
  isOpen: boolean
  onClose: () => void
  onBackToLogin: () => void
}

interface ForgotPasswordFormValues {
  email: string
}

export function ForgotPasswordModal({
  isOpen,
  onClose,
  onBackToLogin,
}: ForgotPasswordModalProps) {
  const [serverError, setServerError] = useState<string | null>(null)
  const [serverSuccess, setServerSuccess] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const {
    register: registerField,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<ForgotPasswordFormValues>({
    defaultValues: {
      email: '',
    },
  })

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

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null)
    setServerSuccess(null)
    setIsSubmitting(true)
    try {
      const response = await authApi.forgotPassword(values.email)
      if (response.success && response.data?.message) {
        setServerSuccess(response.data.message)
      } else {
        setServerError('Failed to send password reset email. Please try again.')
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
      aria-labelledby="forgot-password-modal-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div className="modal-content" role="document">
        <div className="modal-header">
          <h2 id="forgot-password-modal-title">Reset Password</h2>
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
              <button
                type="button"
                className="btn btn-primary"
                onClick={onBackToLogin}
              >
                Back to Login
              </button>
            </div>
          ) : (
            <>
              <p className="auth-description">
                Enter your email address and we'll send you a link to reset your
                password.
              </p>
              <form onSubmit={onSubmit} className="auth-form">
                <div className="form-group">
                  <label htmlFor="forgot-password-email">Email</label>
                  <input
                    id="forgot-password-email"
                    type="email"
                    autoComplete="email"
                    placeholder="Enter your email address"
                    {...registerField('email', {
                      required: 'Email is required',
                      pattern: {
                        value:
                          /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/i,
                        message: 'Please enter a valid email address',
                      },
                    })}
                  />
                  {errors.email && (
                    <span className="form-error">{errors.email.message}</span>
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
                  {isSubmitting ? 'Sending…' : 'Send Reset Link'}
                </button>
              </form>
            </>
          )}
          <div className="modal-footer">
            <p>
              Remember your password?{' '}
              <button
                type="button"
                className="link-button"
                onClick={onBackToLogin}
              >
                Sign in
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

