import { useState, useEffect } from 'react'
import { authApi } from '../../services/apiClient'

interface DeletionStatus {
  pending: boolean
  requested_at: string | null
  scheduled_deletion_at: string | null
}

export default function SettingsCloseAccount() {
  const [status, setStatus] = useState<DeletionStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [actionLoading, setActionLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  const [showConfirm, setShowConfirm] = useState(false)

  const fetchStatus = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await authApi.getDeletionStatus()
      if (res?.success && res.data) {
        setStatus(res.data)
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to load deletion status.')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    fetchStatus()
  }, [])

  const handleRequestDeletion = async () => {
    setActionLoading(true)
    setError(null)
    setSuccess(null)
    try {
      const res = await authApi.requestDataDeletion()
      if (res?.success) {
        setSuccess(res.data?.message || 'Deletion request submitted. Your data will be removed in 6 months.')
        setShowConfirm(false)
        await fetchStatus()
        setTimeout(() => setSuccess(null), 6000)
      } else {
        setError((res as any)?.message || 'Failed to submit deletion request.')
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to submit deletion request.')
    } finally {
      setActionLoading(false)
    }
  }

  const handleCancelDeletion = async () => {
    setActionLoading(true)
    setError(null)
    setSuccess(null)
    try {
      const res = await authApi.cancelDataDeletion()
      if (res?.success) {
        setSuccess(res.data?.message || 'Deletion request cancelled. Your data will be retained.')
        await fetchStatus()
        setTimeout(() => setSuccess(null), 5000)
      } else {
        setError((res as any)?.message || 'Failed to cancel deletion request.')
      }
    } catch (e: any) {
      setError(e?.message || 'Failed to cancel deletion request.')
    } finally {
      setActionLoading(false)
    }
  }

  const formatDate = (iso: string | null) => {
    if (!iso) return null
    try {
      return new Date(iso).toLocaleDateString(undefined, {
        dateStyle: 'long',
        timeStyle: 'short',
      })
    } catch {
      return iso
    }
  }

  return (
    <>
      <h1>Close Account</h1>

      {error && (
        <div className="settings-alert settings-alert-error">
          <span>{error}</span>
          <button type="button" className="settings-alert-close" onClick={() => setError(null)} aria-label="Dismiss">×</button>
        </div>
      )}

      {success && (
        <div className="settings-alert settings-alert-success">
          <span>{success}</span>
          <button type="button" className="settings-alert-close" onClick={() => setSuccess(null)} aria-label="Dismiss">×</button>
        </div>
      )}

      <div className="settings-section">
        <h3>What happens when you close your account</h3>
        <p>
          Closing your account will permanently delete your profile, conversations, and all other
          data we hold about you. This cannot be undone. Deletion is processed <strong>6 months</strong> after
          you submit the request, so you can change your mind and cancel at any time before then.
        </p>
      </div>

      {loading ? (
        <div className="settings-section">
          <p>Loading…</p>
        </div>
      ) : status?.pending ? (
        <div className="settings-section">
          <div className="deletion-status-box">
            <h4>Deletion scheduled</h4>
            <p>
              You have requested that your data be permanently deleted. Your data will be removed on{' '}
              <span className="scheduled-date">{formatDate(status.scheduled_deletion_at) || status.scheduled_deletion_at}</span>.
            </p>
            <p>You can cancel this request at any time before that date.</p>
          </div>
          <div className="settings-actions">
            <button
              type="button"
              className="btn-secondary"
              onClick={handleCancelDeletion}
              disabled={actionLoading}
            >
              {actionLoading ? 'Cancelling…' : 'Cancel deletion request'}
            </button>
          </div>
        </div>
      ) : (
        <div className="settings-section">
          <div className="settings-alert settings-alert-warning">
            <span>This will permanently delete all your data. You can cancel the request within 6 months.</span>
          </div>
          <div className="settings-actions">
            <button
              type="button"
              className="btn-danger"
              onClick={() => setShowConfirm(true)}
            >
              Request account closure
            </button>
          </div>
        </div>
      )}

      {showConfirm && (
        <div
          className="modal-overlay"
          style={{
            position: 'fixed',
            inset: 0,
            background: 'rgba(0,0,0,0.5)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
          onClick={() => !actionLoading && setShowConfirm(false)}
        >
          <div
            className="modal-content"
            style={{ maxWidth: 440 }}
            onClick={(e) => e.stopPropagation()}
          >
            <h3>Request account closure?</h3>
            <p>
              Your data will be permanently deleted 6 months from today. You may cancel this
              request at any time before then from this page.
            </p>
            <div className="modal-actions" style={{ justifyContent: 'flex-end', gap: '0.75rem', marginTop: '1.5rem' }}>
              <button
                type="button"
                className="btn-secondary"
                onClick={() => !actionLoading && setShowConfirm(false)}
                disabled={actionLoading}
              >
                Cancel
              </button>
              <button
                type="button"
                className="btn-danger"
                onClick={handleRequestDeletion}
                disabled={actionLoading}
              >
                {actionLoading ? 'Submitting…' : 'Yes, request closure'}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
