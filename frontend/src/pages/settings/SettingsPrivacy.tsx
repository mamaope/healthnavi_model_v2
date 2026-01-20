import { Link } from 'react-router-dom'

export default function SettingsPrivacy() {
  return (
    <>
      <h1>Privacy & Data</h1>
      <div className="settings-section">
        <h3>Your data</h3>
        <p>
          We process your data in line with our{' '}
          <Link to="/privacy">Privacy Policy</Link>
          . You can request a copy of your data or ask us to delete it.
        </p>
      </div>
      <div className="settings-section">
        <h3>Delete your data and close your account</h3>
        <p>
          If you want to permanently delete your data and close your account, you can submit a
          request. Deletion is processed 6 months after your request; you may cancel at any time
          before then.
        </p>
        <div className="settings-actions">
          <Link to="/settings/close-account" className="btn-secondary" style={{ textDecoration: 'none' }}>
            Go to Close Account
          </Link>
        </div>
      </div>
    </>
  )
}
