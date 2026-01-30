import { useEffect, useState } from 'react'
import { adminApi } from '../../services/apiClient'
import './FeedbackCommentsPanel.css'

type FeedbackCommentsPanelProps = {
  filters: { startDate?: string; endDate?: string; userIds?: number[] }
}

export default function FeedbackCommentsPanel({ filters }: FeedbackCommentsPanelProps) {
  const [items, setItems] = useState<any[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [feedbackType, setFeedbackType] = useState<string>('')
  const [hasTextOnly, setHasTextOnly] = useState(false)
  const [page, setPage] = useState(0)
  const limit = 20

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    adminApi
      .getFeedbackList({
        startDate: filters.startDate,
        endDate: filters.endDate,
        userIds: filters.userIds,
        feedbackType: feedbackType || undefined,
        hasTextOnly,
        limit,
        offset: page * limit,
      })
      .then((res) => {
        if (cancelled || !res.success) return
        setItems(res.data?.items ?? [])
        setTotal(res.data?.total ?? 0)
      })
      .finally(() => setLoading(false))
    return () => { cancelled = true }
  }, [filters.startDate, filters.endDate, filters.userIds?.join(','), feedbackType, hasTextOnly, page])

  const totalPages = Math.ceil(total / limit)

  return (
    <section className="admin-panel feedback-comments-panel">
      <div className="panel-header">
        <h2>Feedback comments</h2>
        <div className="feedback-filters">
          <select
            value={feedbackType}
            onChange={(e) => { setFeedbackType(e.target.value); setPage(0) }}
            className="filter-select"
          >
            <option value="">All</option>
            <option value="helpful">Helpful</option>
            <option value="not_helpful">Not helpful</option>
          </select>
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={hasTextOnly}
              onChange={(e) => { setHasTextOnly(e.target.checked); setPage(0) }}
            />
            With text only
          </label>
        </div>
      </div>
      {loading && <p className="loading-text">Loading feedback…</p>}
      {!loading && items.length === 0 && <p className="empty-text">No feedback in this period.</p>}
      {!loading && items.length > 0 && (
        <>
          <p className="total-text">Total: {total}</p>
          <div className="feedback-list">
            {items.map((row) => (
              <div key={row.id} className="feedback-item">
                <div className="feedback-meta">
                  <span className="feedback-type">{row.feedback_type}</span>
                  {row.rating != null && <span className="feedback-rating">Rating: {row.rating}</span>}
                  <span className="feedback-date">{row.created_at ? new Date(row.created_at).toLocaleString() : ''}</span>
                  <span className="feedback-user">{row.user_email ?? row.user_id}</span>
                </div>
                {row.feedback_text && (
                  <div className="feedback-text">{row.feedback_text}</div>
                )}
              </div>
            ))}
          </div>
          {totalPages > 1 && (
            <div className="pagination">
              <button
                type="button"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                Previous
              </button>
              <span>Page {page + 1} of {totalPages}</span>
              <button
                type="button"
                disabled={page >= totalPages - 1}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
              </button>
            </div>
          )}
        </>
      )}
    </section>
  )
}
