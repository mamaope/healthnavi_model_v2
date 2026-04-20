import { useState, useEffect } from 'react'
import { PieChart, Pie, Cell, ResponsiveContainer, Tooltip, Legend } from 'recharts'
import { adminApi } from '../../services/apiClient'
import './AdminPanel.css'

interface UserTypeBreakdownPanelProps {
  days?: number
}

const CHART_COLORS = ['#0ea5e9', '#8b5cf6', '#10b981', '#f59e0b', '#ec4899', '#6366f1', '#14b8a6']

function formatRole(role: string) {
  if (!role || role === 'null') return 'Unknown'
  return role.charAt(0).toUpperCase() + role.slice(1).replace('_', ' ')
}

export default function UserTypeBreakdownPanel({ days = 30 }: UserTypeBreakdownPanelProps) {
  const [statistics, setStatistics] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadStatistics()
  }, [days])

  const loadStatistics = async () => {
    try {
      setLoading(true)
      setError(null)
      const daysNum = typeof days === 'number' ? days : parseInt(String(days), 10)
      const response = await adminApi.getUserStatistics(daysNum)
      if (response?.success && response.data) {
        setStatistics(response.data)
      } else {
        setError((response as any)?.message || 'Failed to load user statistics')
        setStatistics(null)
      }
    } catch (err: any) {
      setError(err?.message || 'Failed to load user statistics')
      setStatistics(null)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return (
      <div className="admin-panel">
        <div className="panel-header">
          <h2>Users by role & type</h2>
        </div>
        <div className="panel-content">
          <div className="loading-container">
            <div className="spinner" />
            <p>Loading statistics...</p>
          </div>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="admin-panel">
        <div className="panel-header">
          <h2>Users by role & type</h2>
          <button onClick={loadStatistics} className="btn-refresh">Retry</button>
        </div>
        <div className="panel-content">
          <div className="error-container">
            <p>{error}</p>
            <button onClick={loadStatistics} className="btn-primary">Try again</button>
          </div>
        </div>
      </div>
    )
  }

  if (!statistics) return null

  const roleEntries = statistics.users_by_role
    ? Object.entries(statistics.users_by_role)
        .filter(([role, count]: [string, any]) => role != null && role !== 'null' && count != null)
        .map(([role, count]: [string, any]) => ({ name: formatRole(role), value: count || 0 }))
    : []

  const typeEntries = statistics.users_by_type
    ? Object.entries(statistics.users_by_type)
        .filter(([type, count]: [string, any]) => type != null && type !== 'null' && count != null)
        .map(([type, count]: [string, any]) => ({ name: type || 'Unknown', value: count || 0 }))
    : []

  const hasRoleData = roleEntries.length > 0
  const hasTypeData = typeEntries.length > 0

  return (
    <div className="admin-panel user-type-panel">
      <div className="panel-header">
        <h2>Users by role & type</h2>
        <button onClick={loadStatistics} className="btn-refresh">Refresh</button>
      </div>
      <div className="panel-content">
        <p className="panel-description" title="How users are distributed by role (admin, clinician, etc.) and professional type.">
          Distribution of users in the selected period. Hover over charts for details.
        </p>
        <div className="panel-charts-row">
          {hasRoleData && (
            <div className="panel-chart pie-chart chart-container">
              <h3 className="chart-title">By role</h3>
              <p className="chart-description">User accounts by their system role</p>
              <ResponsiveContainer width="100%" height={260}>
                <PieChart margin={{ top: 10, right: 10, bottom: 10, left: 10 }}>
                  <Pie
                    data={roleEntries}
                    cx="50%"
                    cy="50%"
                    innerRadius={40}
                    outerRadius={75}
                    paddingAngle={2}
                    dataKey="value"
                    nameKey="name"
                  >
                    {roleEntries.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[i % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => {
                      const numericValue = typeof value === 'number' ? value : Number(value ?? 0) || 0
                      return [numericValue, 'Users']
                    }}
                    contentStyle={{ fontSize: 12, borderRadius: 8, backgroundColor: '#ffffff', color: '#1f2937', border: '1px solid #e5e7eb' }}
                  />
                  <Legend layout="horizontal" align="center" wrapperStyle={{ paddingTop: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
          {hasTypeData && (
            <div className="panel-chart pie-chart chart-container">
              <h3 className="chart-title">By professional type</h3>
              <p className="chart-description">Users by their clinical specialty or type</p>
              <ResponsiveContainer width="100%" height={260}>
                <PieChart margin={{ top: 10, right: 10, bottom: 10, left: 10 }}>
                  <Pie
                    data={typeEntries}
                    cx="50%"
                    cy="50%"
                    innerRadius={40}
                    outerRadius={75}
                    paddingAngle={2}
                    dataKey="value"
                    nameKey="name"
                  >
                    {typeEntries.map((_, i) => (
                      <Cell key={i} fill={CHART_COLORS[(i + 2) % CHART_COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(value) => {
                      const numericValue = typeof value === 'number' ? value : Number(value ?? 0) || 0
                      return [numericValue, 'Users']
                    }}
                    contentStyle={{ fontSize: 12, borderRadius: 8, backgroundColor: '#ffffff', color: '#1f2937', border: '1px solid #e5e7eb' }}
                  />
                  <Legend layout="horizontal" align="center" wrapperStyle={{ paddingTop: 8 }} />
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </div>
        {!hasRoleData && !hasTypeData && (
          <p className="panel-empty">No user breakdown data available.</p>
        )}
      </div>
    </div>
  )
}
