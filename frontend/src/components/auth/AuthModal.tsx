import { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useAuth } from '../../providers/AuthProvider'
import { API_URL } from '../../config'

export type AuthMode = 'login' | 'register'

interface AuthModalProps {
  isOpen: boolean
  mode: AuthMode
  onClose: () => void
  onSwitchMode: (mode: AuthMode) => void
  onForgotPassword?: () => void
}

interface AuthFormValues {
  email: string
  password: string
  fullName: string
  confirmPassword: string
}

export function AuthModal({ isOpen, mode, onClose, onSwitchMode, onForgotPassword }: AuthModalProps) {
  const { login, register } = useAuth()
  const [serverError, setServerError] = useState<string | null>(null)
  const [isSubmitting, setIsSubmitting] = useState(false)

  const {
    register: registerField,
    handleSubmit,
    reset,
    formState: { errors },
    watch,
  } = useForm<AuthFormValues>({
    defaultValues: {
      email: '',
      password: '',
      fullName: '',
      confirmPassword: '',
    },
  })

  const title = mode === 'login' ? 'Sign In' : 'Create Account'
  const submitLabel = mode === 'login' ? 'Sign In' : 'Sign Up'
  const toggleLabel =
    mode === 'login'
      ? "Don't have an account? "
      : 'Already have an account? '

  useEffect(() => {
    if (isOpen) {
      setServerError(null)
      setIsSubmitting(false)
      reset()
    }
  }, [isOpen, mode, reset])

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

  const confirmPassword = watch('confirmPassword')

  const onSubmit = handleSubmit(async (values) => {
    setServerError(null)
    setIsSubmitting(true)
    try {
      if (mode === 'login') {
        const loginValues = values
        await login({
          email: loginValues.email,
          password: loginValues.password,
        })
      } else {
        if (values.password !== values.confirmPassword) {
          setServerError('Passwords do not match.')
          setIsSubmitting(false)
          return
        }

        await register({
          email: values.email,
          password: values.password,
          fullName: values.fullName ?? '',
        })
      }
      onClose()
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

  const toggleMode = () => {
    onSwitchMode(mode === 'login' ? 'register' : 'login')
  }

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
      aria-labelledby="auth-modal-title"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) {
          onClose()
        }
      }}
    >
      <div className="modal-content" role="document">
        <div className="modal-header">
          <h2 id="auth-modal-title">{title}</h2>
          <button className="modal-close" onClick={onClose} aria-label="Close dialog">
            &times;
          </button>
        </div>
        <div className="modal-body">
          <form onSubmit={onSubmit} className="auth-form">
            <div className="form-group">
              <label htmlFor="auth-email">Email</label>
              <input
                id="auth-email"
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

            {mode === 'register' && (
              <div className="form-group">
                <label htmlFor="auth-full-name">Full Name</label>
                <input
                  id="auth-full-name"
                  type="text"
                  autoComplete="name"
                  placeholder="Enter your full name"
                  {...registerField('fullName', {
                    required: 'Full name is required',
                    minLength: {
                      value: 3,
                      message: 'Full name must be at least 3 characters',
                    },
                  })}
                />
                {errors.fullName && (
                  <span className="form-error">{errors.fullName.message}</span>
                )}
              </div>
            )}

            <div className="form-group">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                <label htmlFor="auth-password">Password</label>
                {mode === 'login' && onForgotPassword && (
                  <button
                    type="button"
                    className="link-button"
                    onClick={(e) => {
                      e.preventDefault()
                      onForgotPassword()
                    }}
                    style={{ 
                      fontSize: '0.875rem',
                      color: 'var(--primary-color, #3b82f6)',
                      fontWeight: '500',
                      padding: 0,
                      margin: 0,
                      textDecoration: 'underline'
                    }}
                  >
                    Forgot password?
                  </button>
                )}
              </div>
              <input
                id="auth-password"
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                placeholder="Enter your password"
                {...registerField('password', {
                  required: 'Password is required',
                  minLength: {
                    value: 4,
                    message: 'Password must be at least 4 characters long',
                  },
                })}
              />
              {errors.password && (
                <span className="form-error">{errors.password.message}</span>
              )}
            </div>

            {mode === 'register' && (
              <div className="form-group">
                <label htmlFor="auth-confirm-password">Confirm Password</label>
                <input
                  id="auth-confirm-password"
                  type="password"
                  autoComplete="new-password"
                  placeholder="Re-enter your password"
                  {...registerField('confirmPassword', {
                    required: 'Please confirm your password',
                    validate: (value) =>
                      value === confirmPassword || 'Passwords do not match',
                  })}
                />
                {errors.confirmPassword && (
                  <span className="form-error">
                    {errors.confirmPassword.message}
                  </span>
                )}
              </div>
            )}

            {serverError && <div className="auth-error">{serverError}</div>}

            <button type="submit" className="btn btn-primary" disabled={isSubmitting}>
              {isSubmitting ? 'Please wait…' : submitLabel}
            </button>
          </form>

          <div className="auth-divider">
            <span>or</span>
          </div>

          <a
            href={`${API_URL.startsWith('/') ? window.location.origin : ''}${API_URL}/auth/google/login`}
            className="btn btn-google"
            onClick={(e) => {
              e.preventDefault()
              // Close modal first
              onClose()
              // Then navigate after a brief delay to ensure modal closes
              setTimeout(() => {
                window.location.href = `${API_URL.startsWith('/') ? window.location.origin : ''}${API_URL}/auth/google/login`
              }, 100)
            }}
            style={{ textDecoration: 'none', display: 'inline-block' }}
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path
                d="M17.64 9.20454C17.64 8.56636 17.5827 7.95272 17.4764 7.36363H9V10.845H13.8436C13.635 11.97 13.0009 12.9231 12.0477 13.5613V15.8195H15.9564C17.1582 14.7527 17.64 13.1954 17.64 9.20454Z"
                fill="#4285F4"
              />
              <path
                d="M9 18C11.43 18 13.467 17.1941 14.9564 15.8195L12.0477 13.5613C11.2418 14.1013 10.2109 14.4204 9 14.4204C6.65454 14.4204 4.67182 12.8372 3.96409 10.71H0.957275V13.0418C2.43818 15.9831 5.48182 18 9 18Z"
                fill="#34A853"
              />
              <path
                d="M3.96409 10.71C3.78409 10.17 3.68182 9.59318 3.68182 9C3.68182 8.40681 3.78409 7.83 3.96409 7.29V4.95818H0.957273C0.347727 6.17318 0 7.54772 0 9C0 10.4523 0.347727 11.8268 0.957273 13.0418L3.96409 10.71Z"
                fill="#FBBC05"
              />
              <path
                d="M9 3.57955C10.3214 3.57955 11.5077 4.03364 12.4405 4.92545L15.0218 2.34409C13.4632 0.891818 11.4259 0 9 0C5.48182 0 2.43818 2.01682 0.957275 4.95818L3.96409 7.29C4.67182 5.16273 6.65454 3.57955 9 3.57955Z"
                fill="#EA4335"
              />
            </svg>
            Continue with Google
          </a>

          <div className="modal-footer">
            <p>
              {toggleLabel}
              <button type="button" className="link-button" onClick={toggleMode}>
                {mode === 'login' ? 'Sign up' : 'Sign in'}
              </button>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

