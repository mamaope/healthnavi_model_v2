import { adminApi } from '../../services/apiClient'
import './AdminPanel.css'

interface AlertsPanelProps {
  alerts: any[]
  onMarkRead: (alertId: number) => void
  onRefresh: () => void
}

export default function AlertsPanel({ alerts, onMarkRead, onRefresh }: AlertsPanelProps) {
  const getSeverityColor = (severity: string) => {
    switch (severity) {
      case 'critical': return '#dc2626'
      case 'high': return '#f59e0b'
      case 'medium': return '#3b82f6'
      default: return '#6b7280'
    }
  }

  if (alerts.length === 0) {
    return (
      <div className="admin-panel">
        <div className="panel-header">
          <h2>Alerts</h2>
        </div>
        <div className="panel-content">
          <div className="no-alerts">
            <div className="no-alerts-icon">✅</div>
            <p>No unread alerts</p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="admin-panel admin-panel-full-width">
      <div className="panel-header">
        <h2>Alerts</h2>
        <button onClick={onRefresh} className="btn-refresh">Refresh</button>
      </div>
      <div className="panel-content">
        <div className="alerts-list">
          {alerts.map((alert) => (
            <div 
              key={alert.id} 
              className={`alert-item ${!alert.is_read ? 'alert-unread' : ''}`}
              style={{ borderLeftColor: getSeverityColor(alert.severity) }}
            >
              <div className="alert-header">
                <div className="alert-title-row">
                  <span className="alert-severity" style={{ backgroundColor: getSeverityColor(alert.severity) }}>
                    {alert.severity.toUpperCase()}
                  </span>
                  <h3 className="alert-title">{alert.title}</h3>
                </div>
                {!alert.is_read && (
                  <button 
                    onClick={() => onMarkRead(alert.id)}
                    className="btn-mark-read"
                  >
                    Mark Read
                  </button>
                )}
              </div>
              <p className="alert-message">{alert.message}</p>
              <div className="alert-footer">
                <span className="alert-type">{alert.alert_type}</span>
                <span className="alert-time">{new Date(alert.created_at).toLocaleString()}</span>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
