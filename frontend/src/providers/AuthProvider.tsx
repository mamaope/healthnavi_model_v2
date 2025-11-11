/* eslint-disable react-refresh/only-export-components */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react'
import { APP_METADATA, STORAGE_KEYS } from '../config'
import { authApi } from '../services/apiClient'
import type { User } from '../types/auth'

interface AuthState {
  user: User | null
  token: string | null
  initializing: boolean
  isAuthenticated: boolean
}

interface AuthContextValue extends AuthState {
  login: (payload: { email: string; password: string }) => Promise<void>
  register: (payload: {
    fullName: string
    email: string
    password: string
  }) => Promise<void>
  logout: () => void
  refreshProfile: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

function parseFullName(fullName: string) {
  const trimmed = fullName.trim()
  if (!trimmed) {
    return { firstName: '', lastName: '' }
  }

  const [firstName, ...rest] = trimmed.split(/\s+/)
  return {
    firstName,
    lastName: rest.join(' '),
  }
}

function getStoredAuth() {
  if (typeof window === 'undefined') {
    return { token: null, user: null }
  }

  const token = window.localStorage.getItem(STORAGE_KEYS.accessToken)
  const userRaw = window.localStorage.getItem(STORAGE_KEYS.currentUser)

  if (!userRaw) {
    return { token, user: null }
  }

  try {
    const user = JSON.parse(userRaw) as User
    return { token, user }
  } catch {
    return { token, user: null }
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [{ user, token, initializing }, setAuthState] = useState<AuthState>({
    user: null,
    token: null,
    initializing: true,
    isAuthenticated: false,
  })

  const persistAuth = useCallback((accessToken: string, profile: User) => {
    if (typeof window === 'undefined') {
      return
    }
    window.localStorage.setItem(STORAGE_KEYS.accessToken, accessToken)
    window.localStorage.setItem(STORAGE_KEYS.currentUser, JSON.stringify(profile))
  }, [])

  const clearPersistedAuth = useCallback(() => {
    if (typeof window === 'undefined') {
      return
    }
    window.localStorage.removeItem(STORAGE_KEYS.accessToken)
    window.localStorage.removeItem(STORAGE_KEYS.currentUser)
  }, [])

  const refreshProfile = useCallback(async () => {
    const stored = getStoredAuth()
    if (!stored.token) {
      setAuthState({
        user: null,
        token: null,
        initializing: false,
        isAuthenticated: false,
      })
      return
    }

    try {
      const response = await authApi.me(stored.token)
      if (response.success && response.data) {
        persistAuth(stored.token, response.data)
        setAuthState({
          user: response.data,
          token: stored.token,
          initializing: false,
          isAuthenticated: true,
        })
      } else {
        clearPersistedAuth()
        setAuthState({
          user: null,
          token: null,
          initializing: false,
          isAuthenticated: false,
        })
      }
    } catch (error) {
      console.warn('Failed to refresh profile', error)
      clearPersistedAuth()
      setAuthState({
        user: null,
        token: null,
        initializing: false,
        isAuthenticated: false,
      })
    }
  }, [clearPersistedAuth, persistAuth])

  useEffect(() => {
    const stored = getStoredAuth()
    if (!stored.token) {
      setAuthState({
        user: null,
        token: null,
        initializing: false,
        isAuthenticated: false,
      })
      return
    }

    // We optimistically set the state while verifying the token
    setAuthState({
      user: stored.user,
      token: stored.token,
      initializing: true,
      isAuthenticated: Boolean(stored.token),
    })

    refreshProfile().catch((error) => {
      console.error('Failed to initialize auth state', error)
    })
  }, [refreshProfile])

  const login = useCallback(
    async ({ email, password }: { email: string; password: string }) => {
      try {
        const response = await authApi.login(email, password)
        if (!response.success) {
          throw new Error('Login failed. Please verify your credentials.')
        }

        const accessToken = response.data.access_token
        const profile = response.data.user

        persistAuth(accessToken, profile)
        setAuthState({
          user: profile,
          token: accessToken,
          initializing: false,
          isAuthenticated: true,
        })
      } catch (error) {
        if (error instanceof Error) {
          throw error
        }
        throw new Error('Unable to sign in at the moment. Please try again.')
      }
    },
    [persistAuth],
  )

  const register = useCallback(
    async ({
      fullName,
      email,
      password,
    }: {
      fullName: string
      email: string
      password: string
    }) => {
      const { firstName, lastName } = parseFullName(fullName)
      if (!firstName || !lastName) {
        throw new Error('Please enter your first and last name.')
      }

      try {
        const response = await authApi.register(
          firstName,
          lastName,
          email,
          password,
        )

        if (!response.success) {
          throw new Error('Registration failed. Please try again.')
        }

        // Automatically log in the user after successful registration
        await login({ email, password })
      } catch (error) {
        if (error instanceof Error) {
          throw error
        }
        throw new Error('Unable to create an account at the moment.')
      }
    },
    [login],
  )

  const logout = useCallback(() => {
    clearPersistedAuth()
    setAuthState({
      user: null,
      token: null,
      initializing: false,
      isAuthenticated: false,
    })
  }, [clearPersistedAuth])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      token,
      initializing,
      isAuthenticated: Boolean(token),
      login,
      register,
      logout,
      refreshProfile,
    }),
    [initializing, login, logout, refreshProfile, register, token, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}

export function getDisplayName(user: User | null | undefined) {
  if (!user) {
    return 'User'
  }

  if (user.full_name) {
    return user.full_name
  }

  const nameParts = [user.first_name, user.last_name].filter(Boolean)
  if (nameParts.length) {
    return nameParts.join(' ')
  }

  return user.username ?? user.email ?? 'User'
}

export function getRoleLabel(user: User | null | undefined) {
  return user?.role ?? APP_METADATA.defaultRole
}

