export default function SettingsBilling() {
  return (
    <>
      <h1>Billing</h1>
      <div className="settings-section">
        <h3>Plan & payment</h3>
        <p>
          Manage your subscription, payment methods, and view invoice history. Billing is not yet
          enabled for this application.
        </p>
      </div>
      <div className="settings-placeholder">
        <i className="fas fa-credit-card" />
        <p>Billing coming soon</p>
        <p style={{ fontSize: '0.9rem', margin: 0 }}>
          When available, you will be able to update your payment method and view past invoices here.
        </p>
      </div>
    </>
  )
}
