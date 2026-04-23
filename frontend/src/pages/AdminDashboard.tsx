import { useEffect, useState, useCallback } from 'react'
import { useAuth } from '../providers/AuthProvider'
import { adminApi } from '../services/apiClient'
import { useNavigate } from 'react-router-dom'
import AdminReportPdf from '../components/admin/AdminReportPdf'
import { exportElementToPdf } from '../utils/exportPdf'
import UsagePanel from '../components/admin/UsagePanel'
import UserTypeBreakdownPanel from '../components/admin/UserTypeBreakdownPanel'
import ClinicalValuePanel from '../components/admin/ClinicalValuePanel'
import SafetyPanel from '../components/admin/SafetyPanel'
import PmfPanel from '../components/admin/PmfPanel'
import UserManagementPanel from '../components/admin/UserManagementPanel'
import SessionManagementPanel from '../components/admin/SessionManagementPanel'
import AIResponseStatisticsPanel from '../components/admin/AIResponseStatisticsPanel'
import SurveyManagementPanel from '../components/admin/SurveyManagementPanel'
import SurveyStatisticsPanel from '../components/admin/SurveyStatisticsPanel'
import DeviceStatisticsPanel from '../components/admin/DeviceStatisticsPanel'
import FeedbackCommentsPanel from '../components/admin/FeedbackCommentsPanel'
import UsageOverTimePanel from '../components/admin/UsageOverTimePanel'
import UserSessionActivityPanel from '../components/admin/UserSessionActivityPanel'
import SessionDetailsPanel from '../components/admin/SessionDetailsPanel'
import './AdminDashboard.css'

type FilterMode = 'preset' | 'custom'
type AdminTab = 'overview' | 'users' | 'sessions' | 'feedback' | 'surveys' | 'system'

export default function AdminDashboard() {
  const { user, isAuthenticated, initializing } = useAuth()
  const navigate = useNavigate()
  const userRole = user?.role ?? ''
  const [metrics, setMetrics] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [days, setDays] = useState(30)
  const [filterMode, setFilterMode] = useState<FilterMode>('preset')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [userList, setUserList] = useState<{ id: number; email: string; full_name?: string }[]>([])
  const [selectedUserIds, setSelectedUserIds] = useState<number[]>([])
  const [excludedUserIds, setExcludedUserIds] = useState<number[]>([])
  const [exporting, setExporting] = useState(false)
  const [pdfData, setPdfData] = useState<{
    report: any
    usageOverTime: { date: string; active_users: number; sessions: number; messages: number }[]
    usersByRole: Record<string, number>
    usersByType: Record<string, number>
    periodLabel: string
  } | null>(null)
  const [activeTab, setActiveTab] = useState<AdminTab>('overview')

  const metricsParams = {
    days: filterMode === 'preset' ? days : undefined,
    startDate: filterMode === 'custom' && startDate ? startDate : undefined,
    endDate: filterMode === 'custom' && endDate ? endDate : undefined,
    userIds: selectedUserIds.length > 0 ? selectedUserIds : undefined,
    excludeUserIds: excludedUserIds.length > 0 ? excludedUserIds : undefined,
  }

  const effectiveDays =
    filterMode === 'custom' && startDate && endDate
      ? Math.max(1, Math.ceil((new Date(endDate).getTime() - new Date(startDate).getTime()) / (24 * 60 * 60 * 1000)))
      : days

  const feedbackDateRange =
    filterMode === 'custom' && startDate && endDate
      ? { startDate, endDate }
      : (() => {
          const end = new Date()
          const start = new Date()
          start.setDate(start.getDate() - effectiveDays)
          return {
            startDate: start.toISOString().slice(0, 10),
            endDate: end.toISOString().slice(0, 10),
          }
        })()

  const loadMetrics = useCallback(async () => {
    try {
      setLoading(true)
      setError(null)
      const response = await adminApi.getMetrics(metricsParams)
      if (response.success) {
        setMetrics(response.data)
      } else {
        setError('Failed to load metrics')
      }
    } catch (err: any) {
      setError(err.message || 'Failed to load metrics')
    } finally {
      setLoading(false)
    }
  }, [filterMode, days, startDate, endDate, selectedUserIds.join(','), excludedUserIds.join(',')])

  useEffect(() => {
    if (initializing) return
    if (!isAuthenticated || !user || !['admin', 'super_admin'].includes(userRole)) {
      navigate('/')
      return
    }
    if (isAuthenticated && user && ['admin', 'super_admin'].includes(userRole)) {
      loadMetrics()
      const interval = setInterval(loadMetrics, 5 * 60 * 1000)
      return () => clearInterval(interval)
    }
  }, [isAuthenticated, user, userRole, initializing, loadMetrics, navigate])

  useEffect(() => {
    if (!isAuthenticated || !user || !['admin', 'super_admin'].includes(userRole)) return
    adminApi.getUsers(200, 0).then((res) => {
      if (res.success && res.data?.users) {
        setUserList(res.data.users.map((u: any) => ({ id: u.id, email: u.email, full_name: u.full_name })))
      }
    })
  }, [isAuthenticated, user, userRole])

  const handleExportPdf = useCallback(async () => {
    setExporting(true)
    setError(null)
    try {
      const [reportRes, usageRes, userStatsRes] = await Promise.all([
        adminApi.exportReport({
          startDate: metricsParams.startDate,
          endDate: metricsParams.endDate,
          userIds: metricsParams.userIds,
          excludeUserIds: metricsParams.excludeUserIds,
          activeUsersOnly: true,
          format: 'json',
        }),
        adminApi.getUsageOverTime({
          days: effectiveDays,
          startDate: metricsParams.startDate,
          endDate: metricsParams.endDate,
          userIds: metricsParams.userIds,
          excludeUserIds: metricsParams.excludeUserIds,
          activeUsersOnly: true,
        }),
        adminApi.getUserStatistics({
          days: effectiveDays,
          startDate: metricsParams.startDate,
          endDate: metricsParams.endDate,
          userIds: metricsParams.userIds,
          excludeUserIds: metricsParams.excludeUserIds,
          activeUsersOnly: true,
        }),
      ])
      const report = reportRes.success ? reportRes.data : null
      const usageOverTime = usageRes.success ? (usageRes.data?.series ?? []) : []
      const userStats = userStatsRes.success ? userStatsRes.data : null
      const usersByRole = (userStats?.users_by_role ?? {}) as Record<string, number>
      const usersByType = (userStats?.users_by_type ?? {}) as Record<string, number>
      const periodLabel =
        filterMode === 'custom' && startDate && endDate
          ? `${startDate} to ${endDate}`
          : `Last ${effectiveDays} days`
      if (!report) throw new Error('Failed to load report data')
      setPdfData({ report, usageOverTime, usersByRole, usersByType, periodLabel })
    } catch (e: any) {
      setError(e?.message || 'Failed to prepare PDF')
      setExporting(false)
    }
  }, [
    metricsParams.startDate,
    metricsParams.endDate,
    metricsParams.userIds,
    metricsParams.excludeUserIds,
    effectiveDays,
    filterMode,
    startDate,
    endDate,
  ])

  useEffect(() => {
    if (!pdfData) return
    const timer = setTimeout(() => {
      const el = document.getElementById('pdf-report-content')
      if (el) {
        exportElementToPdf(el, `admin_report_${new Date().toISOString().slice(0, 10)}.pdf`)
      }
      setPdfData(null)
      setExporting(false)
    }, 1200)
    return () => clearTimeout(timer)
  }, [pdfData])

  const handleExport = async (format: 'json' | 'csv') => {
    setExporting(true)
    try {
      if (format === 'csv') {
        await adminApi.exportReport({
          startDate: metricsParams.startDate,
          endDate: metricsParams.endDate,
          userIds: metricsParams.userIds,
          excludeUserIds: metricsParams.excludeUserIds,
          format: 'csv',
        })
      } else {
        const res = await adminApi.exportReport({
          startDate: metricsParams.startDate,
          endDate: metricsParams.endDate,
          userIds: metricsParams.userIds,
          excludeUserIds: metricsParams.excludeUserIds,
          format: 'json',
        })
        if (res.success && res.data) {
          const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
          const a = document.createElement('a')
          a.href = URL.createObjectURL(blob)
          a.download = `admin_report_${new Date().toISOString().slice(0, 10)}.json`
          a.click()
          URL.revokeObjectURL(a.href)
        }
      }
    } catch (e: any) {
      setError(e.message || 'Export failed')
    } finally {
      setExporting(false)
    }
  }


  // Show loading while auth initializes
  if (initializing) {
    return (
      <div className="admin-dashboard">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading...</p>
        </div>
      </div>
    )
  }

  // Redirect if not authenticated or not admin
  if (!isAuthenticated || !user || !['admin', 'super_admin'].includes(userRole)) {
    return null
  }

  return (
    <div className="admin-dashboard">
      <header className="admin-header">
        <div className="admin-header-content">
          <h1>Admin Dashboard</h1>
          <div className="admin-header-actions">
            <span className="filter-mode-label">Period:</span>
            <select
              value={filterMode}
              onChange={(e) => setFilterMode(e.target.value as FilterMode)}
              className="period-selector"
            >
              <option value="preset">Preset</option>
              <option value="custom">Custom range</option>
            </select>
            {filterMode === 'preset' && (
              <select
                value={days}
                onChange={(e) => setDays(Number(e.target.value))}
                className="period-selector"
              >
                <option value={7}>Last 7 days</option>
                <option value={30}>Last 30 days</option>
                <option value={90}>Last 90 days</option>
                <option value={365}>Last year</option>
              </select>
            )}
            {filterMode === 'custom' && (
              <>
                <label className="date-label">
                  From
                  <input
                    type="date"
                    value={startDate}
                    onChange={(e) => setStartDate(e.target.value)}
                    className="date-input"
                  />
                </label>
                <label className="date-label">
                  To
                  <input
                    type="date"
                    value={endDate}
                    onChange={(e) => setEndDate(e.target.value)}
                    className="date-input"
                  />
                </label>
              </>
            )}
            <label className="user-filter-label">
              Include users (optional)
              <select
                multiple
                value={selectedUserIds.map(String)}
                onChange={(e) => {
                  const opts = Array.from(e.target.selectedOptions, (o) => Number(o.value))
                  setSelectedUserIds(opts)
                }}
                className="user-multi-select"
                title="Hold Ctrl/Cmd to select multiple; empty = all users"
              >
                {userList.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name || u.email}
                  </option>
                ))}
              </select>
              {selectedUserIds.length > 0 && (
                <button type="button" className="btn-clear-users" onClick={() => setSelectedUserIds([])}>
                  Clear
                </button>
              )}
            </label>
            <label className="user-filter-label">
              Exclude users
              <select
                multiple
                value={excludedUserIds.map(String)}
                onChange={(e) => {
                  const opts = Array.from(e.target.selectedOptions, (o) => Number(o.value))
                  setExcludedUserIds(opts)
                }}
                className="user-multi-select"
                title="Hold Ctrl/Cmd to select multiple; these users are removed from all statistics"
              >
                {userList.map((u) => (
                  <option key={u.id} value={u.id}>
                    {u.full_name || u.email}
                  </option>
                ))}
              </select>
              {excludedUserIds.length > 0 && (
                <button type="button" className="btn-clear-users" onClick={() => setExcludedUserIds([])}>
                  Clear
                </button>
              )}
            </label>
            <button
              type="button"
              onClick={() => handleExport('csv')}
              disabled={exporting}
              className="btn-export"
              title="Export report as CSV"
            >
              {exporting ? 'Exporting…' : 'Export CSV'}
            </button>
            <button
              type="button"
              onClick={() => handleExport('json')}
              disabled={exporting}
              className="btn-export btn-export-json"
              title="Export report as JSON"
            >
              Export JSON
            </button>
            <button
              type="button"
              onClick={handleExportPdf}
              disabled={exporting}
              className="btn-export btn-export-pdf"
              title="Export report as PDF with graphs and explanations"
            >
              {exporting ? 'Preparing…' : 'Export PDF'}
            </button>
            <button onClick={() => navigate('/')} className="btn-back">
              Back to Chat
            </button>
          </div>
        </div>
      </header>

      {loading && !metrics && (
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading metrics...</p>
        </div>
      )}

      {error && (
        <div className="error-container">
          <p>Error: {error}</p>
          <button onClick={loadMetrics}>Retry</button>
        </div>
      )}

      {pdfData && (
        <>
          <div
            className="pdf-export-overlay"
            style={{
              position: 'fixed',
              inset: 0,
              zIndex: 10001,
              background: 'rgba(255,255,255,0.9)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              flexDirection: 'column',
              gap: '1rem',
            }}
          >
            <div className="spinner" />
            <p>Preparing PDF report…</p>
          </div>
          <div
            className="pdf-export-container"
            style={{
              position: 'fixed',
              left: 0,
              top: 0,
              width: '800px',
              zIndex: 10000,
              overflow: 'auto',
              maxHeight: '100vh',
            }}
            aria-hidden="true"
          >
            <AdminReportPdf
              reportData={pdfData.report}
              usageOverTime={pdfData.usageOverTime}
              devicesByType={metrics?.devices?.by_type}
              usersByRole={pdfData.usersByRole}
              usersByType={pdfData.usersByType}
              periodLabel={pdfData.periodLabel}
            />
          </div>
        </>
      )}

      {metrics && (
        <>
          <div className="admin-tabs" role="tablist" aria-label="Admin sections">
            <button type="button" role="tab" aria-selected={activeTab === 'overview'} className={`admin-tab ${activeTab === 'overview' ? 'active' : ''}`} onClick={() => setActiveTab('overview')}>
              Overview
            </button>
            <button type="button" role="tab" aria-selected={activeTab === 'users'} className={`admin-tab ${activeTab === 'users' ? 'active' : ''}`} onClick={() => setActiveTab('users')}>
              Users
            </button>
            <button type="button" role="tab" aria-selected={activeTab === 'sessions'} className={`admin-tab ${activeTab === 'sessions' ? 'active' : ''}`} onClick={() => setActiveTab('sessions')}>
              Sessions
            </button>
            <button type="button" role="tab" aria-selected={activeTab === 'feedback'} className={`admin-tab ${activeTab === 'feedback' ? 'active' : ''}`} onClick={() => setActiveTab('feedback')}>
              Feedback
            </button>
            <button type="button" role="tab" aria-selected={activeTab === 'surveys'} className={`admin-tab ${activeTab === 'surveys' ? 'active' : ''}`} onClick={() => setActiveTab('surveys')}>
              Surveys
            </button>
            <button type="button" role="tab" aria-selected={activeTab === 'system'} className={`admin-tab ${activeTab === 'system' ? 'active' : ''}`} onClick={() => setActiveTab('system')}>
              System
            </button>
          </div>

          {activeTab === 'overview' && (
            <div className="admin-panels">
              <UsageOverTimePanel
                filters={{
                  startDate: metricsParams.startDate,
                  endDate: metricsParams.endDate,
                  userIds: metricsParams.userIds,
                  excludeUserIds: metricsParams.excludeUserIds,
                }}
                days={effectiveDays}
              />
              <UsagePanel metrics={metrics.usage} days={effectiveDays} />
              <ClinicalValuePanel metrics={metrics.clinical_value} />
              <SafetyPanel metrics={metrics.safety} />
              <PmfPanel metrics={metrics.pmf} />
            </div>
          )}

          {activeTab === 'users' && (
            <div className="admin-panels">
              <UserTypeBreakdownPanel days={effectiveDays} />
              <UserManagementPanel days={effectiveDays} />
              <UserSessionActivityPanel
                filters={{
                  days: effectiveDays,
                  startDate: metricsParams.startDate,
                  endDate: metricsParams.endDate,
                  userIds: metricsParams.userIds,
                  excludeUserIds: metricsParams.excludeUserIds,
                }}
              />
            </div>
          )}

          {activeTab === 'sessions' && (
            <div className="admin-panels">
              <SessionManagementPanel days={effectiveDays} />
              <SessionDetailsPanel
                filters={{
                  days: effectiveDays,
                  startDate: metricsParams.startDate,
                  endDate: metricsParams.endDate,
                  userIds: metricsParams.userIds,
                  excludeUserIds: metricsParams.excludeUserIds,
                }}
              />
            </div>
          )}

          {activeTab === 'feedback' && (
            <div className="admin-panels">
              <AIResponseStatisticsPanel days={effectiveDays} />
              <FeedbackCommentsPanel
                filters={{
                  startDate: feedbackDateRange.startDate,
                  endDate: feedbackDateRange.endDate,
                  userIds: metricsParams.userIds,
                  excludeUserIds: metricsParams.excludeUserIds,
                }}
              />
            </div>
          )}

          {activeTab === 'surveys' && (
            <div className="admin-panels">
              <SurveyStatisticsPanel days={effectiveDays} />
              <SurveyManagementPanel />
            </div>
          )}

          {activeTab === 'system' && (
            <div className="admin-panels">
              <DeviceStatisticsPanel devices={metrics.devices} days={effectiveDays} />
            </div>
          )}
        </>
      )}
    </div>
  )
}
