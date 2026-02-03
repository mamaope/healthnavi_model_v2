/**
 * Branded loading skeleton shown during route transitions and initial load.
 * Matches the app layout (header + chat area) for a smooth perceived experience.
 */
export function AppLoadingSkeleton() {
  return (
    <div
      className="app-loading-skeleton"
      style={{
        minHeight: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: 'var(--bg-primary, #f9fafb)',
      }}
      aria-label="Loading"
    >
      <div
        className="skeleton-header"
        style={{
          height: 56,
          background: 'var(--bg-secondary, #ffffff)',
          borderBottom: '1px solid var(--border-color, #e5e7eb)',
          flexShrink: 0,
        }}
      />
      <div
        className="skeleton-chat"
        style={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          padding: 24,
          gap: 24,
        }}
      >
        <div
          className="skeleton-logo"
          style={{
            width: 80,
            height: 80,
            borderRadius: 16,
            background:
              'linear-gradient(90deg, var(--bg-tertiary, #e5e7eb) 25%, var(--bg-primary, #f3f4f6) 50%, var(--bg-tertiary, #e5e7eb) 75%)',
            backgroundSize: '200% 100%',
            animation: 'skeleton-shimmer 1.5s ease-in-out infinite',
          }}
        />
        <div
          className="skeleton-input"
          style={{
            width: '100%',
            maxWidth: 560,
            height: 52,
            borderRadius: 26,
            background:
              'linear-gradient(90deg, var(--bg-tertiary, #e5e7eb) 25%, var(--bg-primary, #f3f4f6) 50%, var(--bg-tertiary, #e5e7eb) 75%)',
            backgroundSize: '200% 100%',
            animation: 'skeleton-shimmer 1.5s ease-in-out infinite',
          }}
        />
        <div
          className="skeleton-dots"
          style={{
            display: 'flex',
            gap: 6,
            marginTop: 8,
          }}
        >
          <span
            style={{
              width: 8,
              height: 8,
              background: 'var(--primary-500, #0d9488)',
              borderRadius: '50%',
              animation: 'skeleton-pulse 1.2s ease-in-out infinite',
            }}
          />
          <span
            style={{
              width: 8,
              height: 8,
              background: 'var(--primary-500, #0d9488)',
              borderRadius: '50%',
              animation: 'skeleton-pulse 1.2s ease-in-out infinite',
              animationDelay: '0.2s',
            }}
          />
          <span
            style={{
              width: 8,
              height: 8,
              background: 'var(--primary-500, #0d9488)',
              borderRadius: '50%',
              animation: 'skeleton-pulse 1.2s ease-in-out infinite',
              animationDelay: '0.4s',
            }}
          />
        </div>
      </div>
    </div>
  )
}
