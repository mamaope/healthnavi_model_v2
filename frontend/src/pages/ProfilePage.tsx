import { useState, useEffect } from 'react'
import { useAuth } from '../providers/AuthProvider'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../services/apiClient'
import './ProfilePage.css'

const PROFESSIONAL_TYPES = [
  'Consultant',
  'Specialist',
  'Senior House Officer',
  'Medical Officer',
  'Intern Clinician',
  'Other Clinical Practitioner',
  'Clinical/Medical Student',
]

export default function ProfilePage() {
  const { user, isAuthenticated, initializing, refreshProfile } = useAuth()
  const navigate = useNavigate()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)
  
  // Profile fields
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [username, setUsername] = useState('')
  const [professionalType, setProfessionalType] = useState('')
  const [role, setRole] = useState('')
  const [isEmailVerified, setIsEmailVerified] = useState(false)
  
  // Password change
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [passwordLoading, setPasswordLoading] = useState(false)

  useEffect(() => {
    if (initializing) return
    
    if (!isAuthenticated || !user) {
      navigate('/')
      return
    }
    
    // Initialize form with user data
    setFullName(user.full_name || '')
    setEmail(user.email || '')
    setUsername(user.username || '')
    setProfessionalType(user.medical_professional_type || '')
    setRole(user.role || 'user')
    setIsEmailVerified(user.is_email_verified || false)
  }, [user, isAuthenticated, initializing, navigate])

  const handleUpdateProfile = async () => {
    if (!user) return
    
    setLoading(true)
    setError(null)
    setSuccess(null)
    
    try {
      const updates: { full_name?: string; medical_professional_type?: string } = {}
      
      if (fullName !== (user.full_name || '')) {
        updates.full_name = fullName || undefined
      }
      
      if (professionalType !== (user.medical_professional_type || '')) {
        updates.medical_professional_type = professionalType || undefined
      }
      
      if (Object.keys(updates).length === 0) {
        setError('No changes to save')
        setLoading(false)
        return
      }
      
      const response = await authApi.updateProfile(updates)
      
      if (response && response.success) {
        setSuccess('Profile updated successfully')
        await refreshProfile()
        setTimeout(() => setSuccess(null), 3000)
      } else {
        const errorMsg = (response as any)?.message || 'Failed to update profile'
        setError(errorMsg)
      }
    } catch (err: any) {
      console.error('Failed to update profile:', err)
      const errorMsg = err?.response?.data?.message || err?.message || 'Failed to update profile'
      setError(errorMsg)
    } finally {
      setLoading(false)
    }
  }

  const handleChangePassword = async () => {
    if (!newPassword || newPassword.length < 8) {
      setPasswordError('Password must be at least 8 characters long')
      return
    }
    
    if (newPassword !== confirmPassword) {
      setPasswordError('Passwords do not match')
      return
    }
    
    setPasswordLoading(true)
    setPasswordError(null)
    
    try {
      const response = await authApi.changePassword(currentPassword, newPassword)
      
      if (response && response.success) {
        setShowPasswordModal(false)
        setCurrentPassword('')
        setNewPassword('')
        setConfirmPassword('')
        setSuccess('Password changed successfully')
        setTimeout(() => setSuccess(null), 3000)
      } else {
        const errorMsg = (response as any)?.message || 'Failed to change password'
        setPasswordError(errorMsg)
      }
    } catch (err: any) {
      console.error('Failed to change password:', err)
      const errorMsg = err?.response?.data?.message || err?.message || 'Failed to change password'
      setPasswordError(errorMsg)
    } finally {
      setPasswordLoading(false)
    }
  }

  if (initializing) {
    return (
      <div className="profile-page">
        <div className="loading-container">
          <div className="spinner"></div>
          <p>Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated || !user) {
    return null
  }

  return (
    <div className="profile-page">
      <div className="profile-container">
        <div className="profile-header">
          <h1>My Profile</h1>
          <button onClick={() => navigate('/')} className="btn-back">
            ← Back to Chat
          </button>
        </div>

        {error && (
          <div className="alert alert-error">
            {error}
            <button onClick={() => setError(null)} className="alert-close">×</button>
          </div>
        )}

        {success && (
          <div className="alert alert-success">
            {success}
            <button onClick={() => setSuccess(null)} className="alert-close">×</button>
          </div>
        )}

        <div className="profile-content">
          <div className="profile-section">
            <h2>Account Information</h2>
            <div className="profile-info-grid">
              <div className="info-item">
                <label>Email</label>
                <div className="info-value">
                  {email}
                  {isEmailVerified ? (
                    <span className="badge badge-success">Verified</span>
                  ) : (
                    <span className="badge badge-warning">Not Verified</span>
                  )}
                </div>
              </div>
              <div className="info-item">
                <label>Username</label>
                <div className="info-value">{username}</div>
              </div>
              <div className="info-item">
                <label>Role</label>
                <div className="info-value">
                  <span className={`role-badge role-${role}`}>{role}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="profile-section">
            <h2>Profile Details</h2>
            <div className="form-group">
              <label htmlFor="fullName">Full Name</label>
              <input
                id="fullName"
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Enter your full name"
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="professionalType">Medical Professional Type</label>
              <select
                id="professionalType"
                value={professionalType}
                onChange={(e) => setProfessionalType(e.target.value)}
                className="form-select"
              >
                <option value="">Not Specified</option>
                {PROFESSIONAL_TYPES.map((type) => (
                  <option key={type} value={type}>
                    {type}
                  </option>
                ))}
              </select>
            </div>

            <div className="form-actions">
              <button
                onClick={handleUpdateProfile}
                disabled={loading}
                className="btn-primary"
              >
                {loading ? 'Saving...' : 'Save Changes'}
              </button>
            </div>
          </div>

          <div className="profile-section">
            <h2>Security</h2>
            <div className="security-actions">
              <button
                onClick={() => setShowPasswordModal(true)}
                className="btn-secondary"
              >
                Change Password
              </button>
            </div>
          </div>
        </div>
      </div>

      {showPasswordModal && (
        <div className="modal-overlay" onClick={() => {
          setShowPasswordModal(false)
          setPasswordError(null)
          setCurrentPassword('')
          setNewPassword('')
          setConfirmPassword('')
        }}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <h3>Change Password</h3>
            
            {passwordError && (
              <div className="alert alert-error">
                {passwordError}
                <button onClick={() => setPasswordError(null)} className="alert-close">×</button>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="currentPassword">Current Password</label>
              <input
                id="currentPassword"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
                placeholder="Enter your current password"
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="newPassword">New Password</label>
              <input
                id="newPassword"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
                placeholder="Enter new password (min 8 characters)"
                className="form-input"
              />
            </div>

            <div className="form-group">
              <label htmlFor="confirmPassword">Confirm New Password</label>
              <input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                placeholder="Confirm your new password"
                className="form-input"
              />
            </div>

            <div className="modal-actions">
              <button
                onClick={handleChangePassword}
                disabled={passwordLoading}
                className="btn-primary"
              >
                {passwordLoading ? 'Changing...' : 'Change Password'}
              </button>
              <button
                onClick={() => {
                  setShowPasswordModal(false)
                  setPasswordError(null)
                  setCurrentPassword('')
                  setNewPassword('')
                  setConfirmPassword('')
                }}
                className="btn-secondary"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
