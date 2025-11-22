interface LoadingIndicatorProps {
  isVisible: boolean
  label?: string
}

export function LoadingIndicator({
  isVisible,
  label = 'Analyzing…',
}: LoadingIndicatorProps) {
  if (!isVisible) {
    return null
  }

  return (
    <div className="loading-indicator" role="status">
      <div className="loading-dots">
        <span />
        <span />
        <span />
      </div>
      <span className="loading-text">{label}</span>
    </div>
  )
}

