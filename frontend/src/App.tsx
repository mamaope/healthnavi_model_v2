import { Routes, Route } from 'react-router-dom'
import HomePage from './pages/HomePage'
import TermsOfService from './pages/TermsOfService'
import PrivacyPolicy from './pages/PrivacyPolicy'
import AdminDashboard from './pages/AdminDashboard'
import ProfilePage from './pages/ProfilePage'
import PilotPage from './pages/PilotPage'
import SurveyForm from './components/surveys/SurveyForm'
import SurveySubmissionsPage from './pages/SurveySubmissionsPage'

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
    </Routes>
  )
}
