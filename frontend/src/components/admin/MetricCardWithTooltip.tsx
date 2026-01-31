import { useState } from 'react'
import { METRIC_DESCRIPTIONS } from './metricDescriptions'
import './MetricCardWithTooltip.css'

interface MetricCardWithTooltipProps {
  label: string
  value: string | number
  subtitle?: string
  icon?: string
  color?: string
  highlight?: boolean
  /** Metric key for lookup in METRIC_DESCRIPTIONS (e.g. 'usage.daily_active_users') */
  metricKey?: string
  /** Custom description shown on hover (overrides metricKey lookup) */
  description?: string
}

export default function MetricCardWithTooltip({
  label,
  value,
  subtitle,
  icon,
  color,
  highlight,
  metricKey,
  description,
}: MetricCardWithTooltipProps) {
  const [showTooltip, setShowTooltip] = useState(false)
  const meta = metricKey ? METRIC_DESCRIPTIONS[metricKey] : null
  const tooltipText = description ?? meta?.description ?? 'No description available.'

  return (
    <div
      className={`metric-card-tooltip ${highlight ? 'metric-card-highlight' : ''}`}
      style={color ? { borderTopColor: color } : undefined}
      onMouseEnter={() => setShowTooltip(true)}
      onMouseLeave={() => setShowTooltip(false)}
    >
      {icon && <div className="metric-icon">{icon}</div>}
      <div className="metric-content">
        <div className="metric-label">
          {label}
          <span className="metric-info-icon" title="How is this calculated?">ⓘ</span>
        </div>
        <div className="metric-value" style={color ? { color } : undefined}>
          {value}
        </div>
        {subtitle && <div className="metric-subtitle">{subtitle}</div>}
      </div>
      {showTooltip && (
        <div className="metric-tooltip" role="tooltip">
          <strong>How it&apos;s calculated:</strong>
          <p>{tooltipText}</p>
        </div>
      )}
    </div>
  )
}
