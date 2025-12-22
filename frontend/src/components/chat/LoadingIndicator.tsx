interface LoadingIndicatorProps {
  isVisible: boolean
  label?: string
}

export function LoadingIndicator({
  isVisible,
  label,
}: LoadingIndicatorProps) {
  if (!isVisible) {
    return null
  }

  return (
    <div className="loading-indicator" role="status">
      <div className="loading-dots">
        <span className="dot"></span>
        <span className="dot"></span>
        <span className="dot"></span>
      </div>
    </div>
  )
}

