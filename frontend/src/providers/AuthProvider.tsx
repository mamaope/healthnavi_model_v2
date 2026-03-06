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
      console.log('Refreshing profile with token:', stored.token ? 'present' : 'missing')
      const response = await authApi.me(stored.token)
      console.log('Profile refresh response:', response.success ? 'success' : 'failed', response.data ? 'with data' : 'no data')
      if (response.success && response.data) {
        persistAuth(stored.token, response.data)
        setAuthState({
          user: response.data,
          token: stored.token,
          initializing: false,
          isAuthenticated: true,
        })
        console.log('Auth state updated - user authenticated:', response.data.email)
      } else {
        clearPersistedAuth()
        setAuthState({
          user: null,
          token: null,
          initializing: false,
          isAuthenticated: false,
        })
        // Clear chat state when auth fails
        if (typeof window !== 'undefined') {
          try {
            const { useChatStore } = require('../store/useChatStore')
            useChatStore.getState().reset()
            window.localStorage.removeItem('empirico.chat')
          } catch (error) {
            window.localStorage.removeItem('empirico.chat')
          }
          // Refresh the page when auth fails
          window.location.href = '/'
        }
      }
    } catch (error: any) {
      console.warn('Failed to refresh profile', error)
      
      // Check if this is a 401/403 error (token invalid) vs other errors
      const isAuthError = error?.message?.includes('401') || 
                         error?.message?.includes('403') ||
                         error?.message?.includes('Unauthorized') ||
                         error?.message?.includes('Forbidden') ||
                         error?.message?.includes('authentication')
      
      if (isAuthError) {
        // Token is invalid, clear everything
        clearPersistedAuth()
        setAuthState({
          user: null,
          token: null,
          initializing: false,
          isAuthenticated: false,
        })
        // Clear chat state when auth fails
        if (typeof window !== 'undefined') {
          try {
            const { useChatStore } = require('../store/useChatStore')
            useChatStore.getState().reset()
            window.localStorage.removeItem('empirico.chat')
          } catch (error) {
            window.localStorage.removeItem('empirico.chat')
          }
        }
      } else {
        // Other error (network, server, etc.) - keep token but mark as not authenticated
        // Don't clear the token in case it's a temporary issue
        console.warn('Non-auth error during profile refresh, keeping token for retry')
        setAuthState({
          user: stored.user, // Keep existing user data if available
          token: stored.token,
          initializing: false,
          isAuthenticated: Boolean(stored.user), // Only authenticated if we have user data
        })
      }
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

    // Show UI immediately with cached user - don't block on auth API
    // Run refreshProfile in background; UI updates when it completes
    setAuthState({
      user: stored.user,
      token: stored.token,
      initializing: false, // No longer blocking - show app right away
      isAuthenticated: Boolean(stored.token),
    })

    // Verify token in background; refreshProfile will update state when done
    refreshProfile().catch((error) => {
      console.error('Failed to initialize auth state', error)
    })

    // Set up periodic token validation (every 30 minutes)
    const validationInterval = setInterval(() => {
      const currentStored = getStoredAuth()
      if (currentStored.token) {
        refreshProfile().catch((error) => {
          console.warn('Periodic token validation failed:', error)
        })
      }
    }, 30 * 60 * 1000) // 30 minutes

    // Listen for storage changes (e.g., token cleared by apiClient, or new token added)
    const handleStorageChange = (e: StorageEvent | null = null) => {
      const updatedStored = getStoredAuth()
      
      // If token was removed, clear auth state
      if (!updatedStored.token) {
        setAuthState({
          user: null,
          token: null,
          initializing: false,
          isAuthenticated: false,
        })
        // Clear chat state when auth is cleared
        if (typeof window !== 'undefined') {
          try {
            const { useChatStore } = require('../store/useChatStore')
            useChatStore.getState().reset()
            window.localStorage.removeItem('empirico.chat')
          } catch (error) {
            window.localStorage.removeItem('empirico.chat')
          }
          // Refresh the page when auth is cleared
          window.location.href = '/'
        }
      } else if (updatedStored.token && updatedStored.token !== stored.token) {
        // New token was added (e.g., from OAuth), refresh profile
        console.log('New token detected in storage, refreshing profile...')
        refreshProfile().catch((error) => {
          console.error('Failed to refresh profile after token change:', error)
        })
      }
    }
    window.addEventListener('storage', handleStorageChange)
    
    // Also listen for custom 'auth-token-updated' event for same-window updates
    const handleTokenUpdate = () => {
      console.log('Auth token updated event received, refreshing profile...')
      // Get the latest token from storage
      const latestStored = getStoredAuth()
      if (latestStored.token) {
        refreshProfile().catch((error) => {
          console.error('Failed to refresh profile after token update event:', error)
        })
      }
    }
    window.addEventListener('auth-token-updated', handleTokenUpdate)
    
    // Also listen for custom logout events
    const handleLogout = () => {
      if (typeof window !== 'undefined' && window.location.pathname !== '/') {
        window.location.href = '/'
      }
    }
    window.addEventListener('logout', handleLogout)

    return () => {
      clearInterval(validationInterval)
      window.removeEventListener('storage', handleStorageChange)
      window.removeEventListener('logout', handleLogout)
      window.removeEventListener('auth-token-updated', handleTokenUpdate)
    }
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
        // Start fresh conversation after login: clear any persisted guest chat so user sees new conversation UI
        try {
          const { useChatStore } = require('../store/useChatStore')
          const chat = useChatStore.getState()
          chat.reset()
          chat.setSessions([])
          chat.setFollowupQuestions([])
          if (typeof window !== 'undefined') {
            window.localStorage.removeItem('empirico.chat')
          }
        } catch (err) {
          if (typeof window !== 'undefined') {
            window.localStorage.removeItem('empirico.chat')
          }
        }
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
          // Improve error messages based on common backend errors
          const errorMessage = error.message.toLowerCase()
          
          if (errorMessage.includes('email already registered') || 
              errorMessage.includes('email or username already exists')) {
            throw new Error('This email is already registered. Please sign in instead.')
          } else if (errorMessage.includes('invalid email')) {
            throw new Error('Please enter a valid email address.')
          } else if (errorMessage.includes('network') || errorMessage.includes('fetch')) {
            throw new Error('Network error. Please check your connection and try again.')
          } else if (errorMessage.includes('service temporarily unavailable')) {
            throw new Error('Service is temporarily unavailable. Please try again later.')
          }
          
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
    
    // Fully clear chat from memory and storage so after reload user sees clean home
    if (typeof window !== 'undefined') {
      try {
        const { useChatStore } = require('../store/useChatStore')
        const chat = useChatStore.getState()
        chat.reset()
        chat.setSessions([])
        chat.setFollowupQuestions([])
      } catch (error) {
        console.warn('Failed to clear chat state on logout:', error)
      }
      // Remove persisted chat so next load has no chat data (must do before navigation)
      window.localStorage.removeItem('empirico.chat')
      window.dispatchEvent(new Event('logout'))
      // Full navigation to home so user sees landing UI (nav + login/signup). Reload when already on / so chat is gone.
      const path = window.location.pathname
      const onHome = path === '/' || path === '' || path === '/index.html'
      if (onHome) {
        window.location.reload()
      } else {
        window.location.assign(window.location.origin + '/')
      }
    }
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

