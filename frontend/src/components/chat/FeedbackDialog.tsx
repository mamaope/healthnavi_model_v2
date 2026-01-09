import { useState } from 'react'
import { createPortal } from 'react-dom'

interface FeedbackDialogProps {
  isOpen: boolean
  feedbackType: 'helpful' | 'not_helpful' | null
  onClose: () => void
  onSubmit: (feedbackText: string, rating: number) => void
  isSubmitting?: boolean
}

export function FeedbackDialog({
  isOpen,
  feedbackType,
  onClose,
  onSubmit,
  isSubmitting = false,
}: FeedbackDialogProps) {
  const [feedbackText, setFeedbackText] = useState('')
  const [rating, setRating] = useState<number>(0)
  const [hoveredRating, setHoveredRating] = useState<number>(0)

  if (!isOpen || !feedbackType) return null

  const handleSubmit = () => {
    if (rating === 0) {
      alert('Please provide a rating from 1 to 5 stars')
      return
    }
    onSubmit(feedbackText.trim(), rating)
    // Reset form after submission
    setFeedbackText('')
    setRating(0)
    setHoveredRating(0)
  }

  const handleClose = () => {
    setFeedbackText('')
    setRating(0)
    setHoveredRating(0)
    onClose()
  }

  const displayRating = hoveredRating || rating

  const dialogContent = (
    <div className="feedback-dialog-overlay" onClick={handleClose}>
      <div className="feedback-dialog" onClick={(e) => e.stopPropagation()}>
        <div className="feedback-dialog-header">
          <h3>
            {feedbackType === 'helpful' ? '👍 Helpful' : '👎 Not Helpful'}
          </h3>
          <button
            type="button"
            className="feedback-dialog-close"
            onClick={handleClose}
            aria-label="Close dialog"
          >
            <i className="fas fa-times" />
          </button>
        </div>

        <div className="feedback-dialog-content">
          <div className="feedback-rating-section">
            <label className="feedback-label">
              Rate this response (1-5 stars)
            </label>
            <div className="feedback-stars">
              {[1, 2, 3, 4, 5].map((star) => (
                <button
                  key={star}
                  type="button"
                  className="feedback-star-btn"
                  onClick={() => setRating(star)}
                  onMouseEnter={() => setHoveredRating(star)}
                  onMouseLeave={() => setHoveredRating(0)}
                  aria-label={`Rate ${star} star${star !== 1 ? 's' : ''}`}
                >
                  <i
                    className={`fas fa-star ${
                      star <= displayRating ? 'filled' : 'empty'
                    }`}
                  />
                </button>
              ))}
            </div>
            {rating > 0 && (
              <span className="feedback-rating-text">
                {rating} star{rating !== 1 ? 's' : ''} selected
              </span>
            )}
          </div>

          <div className="feedback-text-section">
            <label htmlFor="feedback-text" className="feedback-label">
              {feedbackType === 'helpful'
                ? 'What made this response helpful? (Optional)'
                : 'How can we improve? (Optional)'}
            </label>
            <textarea
              id="feedback-text"
              className="feedback-textarea"
              value={feedbackText}
              onChange={(e) => setFeedbackText(e.target.value)}
              placeholder={
                feedbackType === 'helpful'
                  ? 'Share what you found most useful...'
                  : 'Tell us what we can do better...'
              }
              rows={4}
              maxLength={2000}
            />
            <div className="feedback-char-count">
              {feedbackText.length}/2000 characters
            </div>
          </div>
        </div>

        <div className="feedback-dialog-footer">
          <button
            type="button"
            className="btn btn-outline"
            onClick={handleClose}
            disabled={isSubmitting}
          >
            Cancel
          </button>
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleSubmit}
            disabled={isSubmitting || rating === 0}
          >
            {isSubmitting ? (
              <>
                <i className="fas fa-spinner fa-spin" /> Submitting...
              </>
            ) : (
              'Submit Feedback'
            )}
          </button>
        </div>
      </div>
    </div>
  )

  // Use portal to render at document body level to avoid positioning issues
  if (typeof document !== 'undefined') {
    return createPortal(dialogContent, document.body)
  }
  
  return dialogContent
}
