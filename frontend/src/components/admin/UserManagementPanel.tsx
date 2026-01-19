import { useState, useEffect } from 'react'
import { adminApi } from '../../services/apiClient'
import './AdminPanel.css'
import './UserManagementPanel.css'

interface UserManagementPanelProps {
  days: number
}

export default function UserManagementPanel({ days }: UserManagementPanelProps) {
  const [users, setUsers] = useState<any[]>([])
  const [statistics, setStatistics] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState({
    isActive: undefined as boolean | undefined,
    role: '',
    medicalProfessionalType: '',
    search: '',
  })
  const [selectedUser, setSelectedUser] = useState<any>(null)
  const [showPasswordModal, setShowPasswordModal] = useState(false)
  const [newPassword, setNewPassword] = useState('')
  const [page, setPage] = useState(0)
  const [total, setTotal] = useState(0)
  const limit = 20

  useEffect(() => {
    loadUsers()
    loadStatistics()
  }, [days, filters, page])

  const loadUsers = async () => {
    try {
      setLoading(true)
      const response = await adminApi.getUsers(
        limit,
        page * limit,
        filters.isActive,
        filters.role || undefined,
        filters.medicalProfessionalType || undefined,
        filters.search || undefined
      )
      if (response.success) {
        setUsers(response.data.users)
        setTotal(response.data.total)
      }
    } catch (err) {
      console.error('Failed to load users:', err)
    } finally {
      setLoading(false)
    }
  }

  const loadStatistics = async () => {
    try {
      const response = await adminApi.getUserStatistics(days)
      if (response.success) {
        setStatistics(response.data)
      }
    } catch (err) {
      console.error('Failed to load user statistics:', err)
    }
  }

  const handleUpdateUser = async (userId: number, updates: any, closeModal: boolean = false) => {
    try {
      const response = await adminApi.updateUser(userId, updates)
      if (response && response.success) {
        loadUsers()
        loadStatistics()
        // Update selectedUser state if it's still the same user
        if (selectedUser && selectedUser.id === userId) {
          setSelectedUser({ ...selectedUser, ...updates })
        }
        if (closeModal) {
          setSelectedUser(null)
        }
      } else {
        const errorMsg = (response as any)?.message || 'Failed to update user'
        alert(errorMsg)
      }
    } catch (err: any) {
      console.error('Failed to update user:', err)
      const errorMsg = err?.response?.data?.message || err?.message || 'Failed to update user'
      alert(errorMsg)
    }
  }

  const handleChangePassword = async () => {
    if (!selectedUser || !newPassword || newPassword.length < 8) {
      alert('Password must be at least 8 characters long')
      return
    }
    try {
      const response = await adminApi.changeUserPassword(selectedUser.id, newPassword)
      if (response && response.success) {
        setShowPasswordModal(false)
        setNewPassword('')
        setSelectedUser(null)
        alert('Password changed successfully')
        loadUsers() // Refresh the user list
      } else {
        const errorMsg = (response as any)?.message || 'Failed to change password'
        alert(errorMsg)
      }
    } catch (err: any) {
      console.error('Failed to change password:', err)
      const errorMsg = err?.response?.data?.message || err?.message || 'Failed to change password'
      alert(errorMsg)
    }
  }

  const totalPages = Math.ceil(total / limit)

  return (
    <div className="admin-panel admin-panel-full-width">
      <div className="panel-header">
        <h2>User Management</h2>
        <button onClick={loadUsers} className="btn-refresh">
          Refresh
        </button>
      </div>
      <div className="panel-content">
        {statistics && (
          <div className="user-statistics">
            <div className="metrics-grid">
              <MetricCard
                label="Total Users"
                value={statistics.total_users || 0}
                icon="👥"
              />
              <MetricCard
                label="Active Users"
                value={statistics.active_users || 0}
                icon="✅"
              />
              <MetricCard
                label="Activated Users"
                value={statistics.activated_users || 0}
                subtitle={`${statistics.new_users || 0} new in period`}
                icon="🚀"
              />
              <MetricCard
                label="Active in Period"
                value={statistics.active_in_period || 0}
                icon="📊"
              />
            </div>
          </div>
        )}

        <div className="user-filters">
          <input
            type="text"
            placeholder="Search by email, username, or name..."
            value={filters.search}
            onChange={(e) => {
              setFilters({ ...filters, search: e.target.value })
              setPage(0)
            }}
            className="filter-input"
          />
          <select
            value={filters.isActive === undefined ? '' : filters.isActive.toString()}
            onChange={(e) => {
              setFilters({
                ...filters,
                isActive: e.target.value === '' ? undefined : e.target.value === 'true',
              })
              setPage(0)
            }}
            className="filter-select"
          >
            <option value="">All Users</option>
            <option value="true">Active Only</option>
            <option value="false">Inactive Only</option>
          </select>
          <select
            value={filters.role}
            onChange={(e) => {
              setFilters({ ...filters, role: e.target.value })
              setPage(0)
            }}
            className="filter-select"
          >
            <option value="">All Roles</option>
            <option value="user">User</option>
            <option value="admin">Admin</option>
            <option value="super_admin">Super Admin</option>
          </select>
        </div>

        {loading ? (
          <div className="loading-container">
            <div className="spinner"></div>
            <p>Loading users...</p>
          </div>
        ) : (
          <>
            <div className="users-table">
              <table>
                <thead>
                  <tr>
                    <th>ID</th>
                    <th>Email</th>
                    <th>Username</th>
                    <th>Full Name</th>
                    <th>Role</th>
                    <th>Type</th>
                    <th>Status</th>
                    <th>Sessions</th>
                    <th>Messages</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td>{user.id}</td>
                      <td>{user.email}</td>
                      <td>{user.username}</td>
                      <td>{user.full_name || '-'}</td>
                      <td>
                        <span className={`role-badge role-${user.role}`}>{user.role}</span>
                      </td>
                      <td>{user.medical_professional_type || '-'}</td>
                      <td>
                        <span className={`status-badge ${user.is_active ? 'active' : 'inactive'}`}>
                          {user.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td>{user.session_count || 0}</td>
                      <td>{user.message_count || 0}</td>
                      <td>
                        <div className="action-buttons">
                          <button
                            onClick={() => setSelectedUser(user)}
                            className="btn-action btn-edit"
                            title="Edit User"
                          >
                            ✏️
                          </button>
                          <button
                            onClick={() => {
                              setSelectedUser(user)
                              setShowPasswordModal(true)
                            }}
                            className="btn-action btn-password"
                            title="Change Password"
                          >
                            🔑
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {totalPages > 1 && (
              <div className="pagination">
                <button
                  onClick={() => setPage(Math.max(0, page - 1))}
                  disabled={page === 0}
                  className="btn-pagination"
                >
                  Previous
                </button>
                <span className="pagination-info">
                  Page {page + 1} of {totalPages} ({total} total)
                </span>
                <button
                  onClick={() => setPage(Math.min(totalPages - 1, page + 1))}
                  disabled={page >= totalPages - 1}
                  className="btn-pagination"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}

        {selectedUser && !showPasswordModal && (
          <div className="modal-overlay" onClick={() => setSelectedUser(null)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <h3>Edit User: {selectedUser.email}</h3>
              <div className="form-group">
                <label>Active Status</label>
                <select
                  value={selectedUser.is_active ? 'true' : 'false'}
                  onChange={(e) =>
                    handleUpdateUser(selectedUser.id, {
                      is_active: e.target.value === 'true',
                    })
                  }
                >
                  <option value="true">Active</option>
                  <option value="false">Inactive</option>
                </select>
              </div>
              <div className="form-group">
                <label>Role</label>
                <select
                  value={selectedUser.role}
                  onChange={(e) =>
                    handleUpdateUser(selectedUser.id, { role: e.target.value })
                  }
                >
                  <option value="user">User</option>
                  <option value="admin">Admin</option>
                  <option value="super_admin">Super Admin</option>
                </select>
              </div>
              <div className="form-group">
                <label>Full Name</label>
                <input
                  type="text"
                  value={selectedUser.full_name || ''}
                  onChange={(e) =>
                    setSelectedUser({ ...selectedUser, full_name: e.target.value })
                  }
                  onBlur={() =>
                    handleUpdateUser(selectedUser.id, {
                      full_name: selectedUser.full_name,
                    })
                  }
                />
              </div>
              <div className="form-group">
                <label>Medical Professional Type</label>
                <select
                  value={selectedUser.medical_professional_type || ''}
                  onChange={(e) =>
                    handleUpdateUser(selectedUser.id, {
                      medical_professional_type: e.target.value || null,
                    })
                  }
                >
                  <option value="">Not Specified</option>
                  <option value="Consultant">Consultant</option>
                  <option value="Specialist">Specialist</option>
                  <option value="Senior House Officer">Senior House Officer</option>
                  <option value="Medical Officer">Medical Officer</option>
                  <option value="Intern Clinician">Intern Clinician</option>
                  <option value="Other Clinical Practitioner">Other Clinical Practitioner</option>
                  <option value="Clinical/Medical Student">Clinical/Medical Student</option>
                </select>
              </div>
              <button onClick={() => setSelectedUser(null)} className="btn-close">
                Close
              </button>
            </div>
          </div>
        )}

        {showPasswordModal && selectedUser && (
          <div className="modal-overlay" onClick={() => setShowPasswordModal(false)}>
            <div className="modal-content" onClick={(e) => e.stopPropagation()}>
              <h3>Change Password for {selectedUser.email}</h3>
              <div className="form-group">
                <label>New Password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="Enter new password (min 8 characters)"
                />
              </div>
              <div className="modal-actions">
                <button onClick={handleChangePassword} className="btn-primary">
                  Change Password
                </button>
                <button
                  onClick={() => {
                    setShowPasswordModal(false)
                    setNewPassword('')
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
    </div>
  )
}

function MetricCard({ label, value, subtitle, icon }: { label: string; value: string | number; subtitle?: string; icon?: string }) {
  return (
    <div className="metric-card">
      {icon && <div className="metric-icon">{icon}</div>}
      <div className="metric-content">
        <div className="metric-label">{label}</div>
        <div className="metric-value">{value}</div>
        {subtitle && <div className="metric-subtitle">{subtitle}</div>}
      </div>
    </div>
  )
}
