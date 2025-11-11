import { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useAuth } from '../../providers/AuthProvider'

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

