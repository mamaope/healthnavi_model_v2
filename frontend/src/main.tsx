import React, { lazy, Suspense } from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ThemeProvider } from './providers/ThemeProvider'
import { AuthProvider } from './providers/AuthProvider'
import './styles/app.css'

// Lazy-load App so initial bundle is smaller; app chunk loads in parallel after first paint
const App = lazy(() => import('./App'))

// Minimal fallback matching the HTML skeleton (same class names) so no extra CSS or component
function ShellFallback() {
  return (
    <div className="app-loading-skeleton" aria-hidden="true">
      <div className="skeleton-header" />
      <div className="skeleton-chat">
        <div className="skeleton-logo" />
        <div className="skeleton-input" />
        <div className="skeleton-dots">
          <span className="skeleton-dot" />
          <span className="skeleton-dot" />
          <span className="skeleton-dot" />
        </div>
      </div>
    </div>
  )
}

// Preload home page chunk so it’s ready as soon as the user sees the app
if (typeof window !== 'undefined') {
  if ('requestIdleCallback' in window) {
    (window as any).requestIdleCallback(() => import('./pages/HomePage').catch(() => {}), { timeout: 2000 })
  }
}

// Error boundary component
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  constructor(props: { children: React.ReactNode }) {
    super(props)
    this.state = { hasError: false, error: null }
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('React Error Boundary caught an error:', error, errorInfo)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', fontFamily: 'sans-serif' }}>
          <h1>Something went wrong</h1>
          <p>{this.state.error?.message || 'Unknown error'}</p>
          <pre style={{ background: '#f5f5f5', padding: '10px', overflow: 'auto' }}>
            {this.state.error?.stack}
          </pre>
          <button onClick={() => window.location.reload()}>Reload Page</button>
        </div>
      )
    }

    return this.props.children
  }
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
    mutations: {
      retry: false,
    },
  },
})

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Root element with id "root" not found')
}

try {
  ReactDOM.createRoot(rootElement).render(
    <React.StrictMode>
      <ErrorBoundary>
        <BrowserRouter>
          <QueryClientProvider client={queryClient}>
            <ThemeProvider>
              <AuthProvider>
                <Suspense fallback={<ShellFallback />}>
                  <App />
                </Suspense>
              </AuthProvider>
            </ThemeProvider>
          </QueryClientProvider>
        </BrowserRouter>
      </ErrorBoundary>
    </React.StrictMode>,
  )
} catch (error) {
  console.error('Failed to render app:', error)
  rootElement.innerHTML = `
    <div style="padding: 20px; font-family: sans-serif;">
      <h1>Failed to load application</h1>
      <p>${error instanceof Error ? error.message : 'Unknown error'}</p>
      <pre style="background: #f5f5f5; padding: 10px; overflow: auto;">
        ${error instanceof Error ? error.stack : String(error)}
      </pre>
    </div>
  `
}

