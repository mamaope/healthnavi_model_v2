interface LoadingIndicatorProps {
  isVisible: boolean
}

export function LoadingIndicator({
  isVisible,
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

