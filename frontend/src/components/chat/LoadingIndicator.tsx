interface LoadingIndicatorProps {
  isVisible: boolean
  label?: string
}

export function LoadingIndicator({
  isVisible,
  label = 'HealthNavy thinking',
}: LoadingIndicatorProps) {
  if (!isVisible) {
    return null
  }

  return (
    <div className="loading-indicator" role="status">
      <div className="loading-spinner">
        <i className="fas fa-sync-alt" aria-hidden="true" />
      </div>
      <span className="loading-text">{label}</span>
    </div>
  )
}

