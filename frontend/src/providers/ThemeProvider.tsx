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
import { STORAGE_KEYS } from '../config'

export type Theme = 'light' | 'dark'

interface ThemeContextValue {
  theme: Theme
  setTheme: (theme: Theme) => void
  toggleTheme: () => void
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined)

function getStoredTheme(): Theme | null {
  if (typeof window === 'undefined') {
    return null
  }
  const stored = window.localStorage.getItem(STORAGE_KEYS.theme) as Theme | null
  return stored ?? null
}

function applyTheme(theme: Theme) {
  if (typeof document === 'undefined') {
    return
  }
  const root = document.documentElement
  if (theme === 'dark') {
    root.setAttribute('data-theme', 'dark')
  } else {
    root.removeAttribute('data-theme')
  }
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [theme, setThemeState] = useState<Theme>(() => {
    return getStoredTheme() ?? 'light'
  })

  useEffect(() => {
    applyTheme(theme)
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(STORAGE_KEYS.theme, theme)
    }
  }, [theme])

  useEffect(() => {
    if (typeof window === 'undefined') return
    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
    const handler = (event: MediaQueryListEvent) => {
      const stored = getStoredTheme()
      if (!stored) {
        setThemeState(event.matches ? 'dark' : 'light')
      }
    }
    mediaQuery.addEventListener('change', handler)
    return () => mediaQuery.removeEventListener('change', handler)
  }, [])

  const setTheme = useCallback((nextTheme: Theme) => {
    setThemeState(nextTheme)
  }, [])

  const toggleTheme = useCallback(() => {
    setThemeState((current) => (current === 'light' ? 'dark' : 'light'))
  }, [])

  const value = useMemo(
    () => ({
      theme,
      setTheme,
      toggleTheme,
    }),
    [setTheme, theme, toggleTheme],
  )

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
}

export function useTheme() {
  const context = useContext(ThemeContext)
  if (!context) {
    throw new Error('useTheme must be used within ThemeProvider')
  }
  return context
}

