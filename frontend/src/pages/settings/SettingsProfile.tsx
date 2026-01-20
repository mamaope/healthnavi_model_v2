import { Link } from 'react-router-dom'

export default function SettingsProfile() {
  return (
    <>
      <h1>Profile</h1>
      <div className="settings-section">
        <h3>Account information</h3>
        <p>
          Update your name, professional type, and other account details. You can also change your
          password from your profile.
        </p>
        <div className="settings-actions">
          <Link to="/profile" className="btn-primary" style={{ textDecoration: 'none' }}>
            Open profile
          </Link>
        </div>
      </div>
    </>
  )
}
