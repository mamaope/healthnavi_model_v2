import { Routes, Route, Navigate } from 'react-router-dom'
import HomePage from './pages/HomePage'
import TermsOfService from './pages/TermsOfService'
import PrivacyPolicy from './pages/PrivacyPolicy'
import AdminDashboard from './pages/AdminDashboard'
import ProfilePage from './pages/ProfilePage'
import PilotPage from './pages/PilotPage'
import SurveyForm from './components/surveys/SurveyForm'
import SurveySubmissionsPage from './pages/SurveySubmissionsPage'
import SettingsPage from './pages/settings/SettingsPage'
import SettingsProfile from './pages/settings/SettingsProfile'
import SettingsBilling from './pages/settings/SettingsBilling'
import SettingsPrivacy from './pages/settings/SettingsPrivacy'
import SettingsCloseAccount from './pages/settings/SettingsCloseAccount'

export default function App() {
  return (
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
  )
}
