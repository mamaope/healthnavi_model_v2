import { lazy, Suspense } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'

// Lazy-load pages so the initial bundle is small and first paint is fast
const HomePage = lazy(() => import('./pages/HomePage'))
const TermsOfService = lazy(() => import('./pages/TermsOfService'))
const PrivacyPolicy = lazy(() => import('./pages/PrivacyPolicy'))
const AdminDashboard = lazy(() => import('./pages/AdminDashboard'))
const ProfilePage = lazy(() => import('./pages/ProfilePage'))
const PilotPage = lazy(() => import('./pages/PilotPage'))
const SurveyForm = lazy(() => import('./components/surveys/SurveyForm'))
const SurveySubmissionsPage = lazy(() => import('./pages/SurveySubmissionsPage'))
const SettingsPage = lazy(() => import('./pages/settings/SettingsPage'))
const SettingsProfile = lazy(() => import('./pages/settings/SettingsProfile'))
const SettingsBilling = lazy(() => import('./pages/settings/SettingsBilling'))
const SettingsPrivacy = lazy(() => import('./pages/settings/SettingsPrivacy'))
const SettingsCloseAccount = lazy(() => import('./pages/settings/SettingsCloseAccount'))

function PageFallback() {
  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '60vh',
        fontFamily: 'system-ui, sans-serif',
        color: 'var(--text-secondary, #666)',
      }}
      aria-label="Loading"
    >
      <span>Loading…</span>
    </div>
  )
}

export default function App() {
  return (
    <Suspense fallback={<PageFallback />}>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/auth/google/success" element={<HomePage />} />
        <Route path="/auth/google/error" element={<HomePage />} />
        <Route path="/terms" element={<TermsOfService />} />
        <Route path="/privacy" element={<PrivacyPolicy />} />
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/admin/surveys" element={<SurveySubmissionsPage />} />
        <Route path="/profile" element={<ProfilePage />} />
        <Route path="/pilot" element={<PilotPage />} />
        <Route path="/pilot/survey/:surveyType" element={<SurveyForm />} />
        <Route path="/settings" element={<SettingsPage />}>
          <Route index element={<Navigate to="/settings/profile" replace />} />
          <Route path="profile" element={<SettingsProfile />} />
          <Route path="billing" element={<SettingsBilling />} />
          <Route path="privacy" element={<SettingsPrivacy />} />
          <Route path="close-account" element={<SettingsCloseAccount />} />
        </Route>
      </Routes>
    </Suspense>
  )
}
