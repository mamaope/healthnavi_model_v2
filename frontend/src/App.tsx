import { lazy, Suspense, type ReactNode } from 'react'
import { Routes, Route, Navigate } from 'react-router-dom'
import { AppLoadingSkeleton } from './components/AppLoadingSkeleton'
import HomePage from './pages/HomePage'
import './styles/app.css'

// Lazy-load pages so the initial bundle is small and first paint is fast
const AboutPage = lazy(() => import('./pages/AboutPage'))
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

function LazyPage({ children }: { children: ReactNode }) {
  return <Suspense fallback={<AppLoadingSkeleton />}>{children}</Suspense>
}

export default function App() {
  return (
    <Routes>
      {/* Eager route: first paint should never wait on route-level lazy chunks */}
      <Route path="/" element={<HomePage />} />
      <Route path="/auth/google/success" element={<HomePage />} />
      <Route path="/auth/google/error" element={<HomePage />} />

      <Route path="/about" element={<LazyPage><AboutPage /></LazyPage>} />
      <Route path="/terms" element={<LazyPage><TermsOfService /></LazyPage>} />
      <Route path="/privacy" element={<LazyPage><PrivacyPolicy /></LazyPage>} />
      <Route path="/admin" element={<LazyPage><AdminDashboard /></LazyPage>} />
      <Route path="/admin/surveys" element={<LazyPage><SurveySubmissionsPage /></LazyPage>} />
      <Route path="/profile" element={<LazyPage><ProfilePage /></LazyPage>} />
      <Route path="/pilot" element={<LazyPage><PilotPage /></LazyPage>} />
      <Route path="/pilot/survey/:surveyType" element={<LazyPage><SurveyForm /></LazyPage>} />
      <Route path="/settings" element={<LazyPage><SettingsPage /></LazyPage>}>
        <Route index element={<Navigate to="/settings/profile" replace />} />
        <Route path="profile" element={<LazyPage><SettingsProfile /></LazyPage>} />
        <Route path="billing" element={<LazyPage><SettingsBilling /></LazyPage>} />
        <Route path="privacy" element={<LazyPage><SettingsPrivacy /></LazyPage>} />
        <Route path="close-account" element={<LazyPage><SettingsCloseAccount /></LazyPage>} />
      </Route>
    </Routes>
  )
}
