import { Link, useNavigate } from 'react-router-dom'
import { Header } from '../components/layout/Header'
import './LegalPage.css'

export default function AboutPage() {
  const navigate = useNavigate()

  return (
    <div className="legal-page">
      <Header
        onSignIn={() => navigate('/')}
        onRegister={() => navigate('/')}
        onHomeClick={() => navigate('/')}
        onMenuToggle={() => {}}
        showMenuButton={false}
      />
      <div className="legal-content">
        <div className="legal-container">
          <h1>About Empirico</h1>
          <p className="about-intro">
            Empirico is an AI-powered clinical decision support system designed to help healthcare professionals
            access evidence-based medical guidance quickly and confidently.
          </p>

          <section>
            <h2>How to Use the Platform</h2>
            <h3>1. Ask Your Question</h3>
            <p>
              Type your clinical question in the chat input at the bottom of the screen. You can ask about
              differential diagnoses, treatment options, drug interactions, clinical guidelines, or any
              evidence-based medical topic.
            </p>
            <p>
              <strong>Tip:</strong> Be specific. Include relevant clinical details (e.g., patient age group,
              comorbidities, medications) while avoiding any patient-identifying information.
            </p>

            <h3>2. Use Sample Prompts</h3>
            <p>
              When you first open the app, you&apos;ll see suggested questions to get you started. Click any
              prompt to populate the input field—then edit if needed and send.
            </p>

            <h3>3. Deep Search</h3>
            <p>
              For complex questions, enable <strong>Deep Search</strong> before sending. This mode performs a
              more thorough search of medical literature and may take longer, but provides more comprehensive
              answers. You can also use the brain icon on any AI response to run a deep search on that
              question.
            </p>

            <h3>4. Follow-Up Questions</h3>
            <p>
              After each response, Empirico may suggest follow-up questions. Click any suggestion to ask it
              immediately—helpful for exploring a topic in depth.
            </p>

            <h3>5. Chat History (Signed-In Users)</h3>
            <p>
              If you sign up or log in, your conversations are saved. Use the sidebar to switch between
              sessions, start a new chat, or revisit past discussions.
            </p>
          </section>

          <section>
            <h2>Response Actions</h2>
            <p>Each AI response includes action buttons:</p>
            <ul>
              <li><strong>Deep Search</strong> — Get a more detailed answer on the same question</li>
              <li><strong>Copy</strong> — Copy the response to your clipboard</li>
              <li><strong>Share</strong> — Share via your device&apos;s share menu or copy to clipboard</li>
              <li><strong>Helpful / Not Helpful</strong> — Provide feedback to improve the service (requires sign-in)</li>
            </ul>
          </section>

          <section>
            <h2>Important Reminders</h2>
            <ul>
              <li>
                <strong>Do not include patient-identifying information.</strong> Never enter names, dates of
                birth, medical record numbers, or other Protected Health Information (PHI).
              </li>
              <li>
                <strong>For healthcare professionals only.</strong> Empirico provides informational guidance
                and is not a substitute for clinical judgment, diagnosis, or treatment.
              </li>
              <li>
                <strong>Not for emergencies.</strong> In a medical emergency, contact emergency services
                immediately.
              </li>
            </ul>
          </section>

          <section>
            <h2>Getting Help</h2>
            <p>
              Need assistance? Contact us at{' '}
              <a href="mailto:empiricoai26@gmail.com">empiricoai26@gmail.com</a> or use the Support link in
              the footer.
            </p>
          </section>

          <div className="legal-footer">
            <Link to="/" className="back-link">← Back to Home</Link>
            <Link to="/terms" className="terms-link">Terms of Service</Link>
            <Link to="/privacy" className="privacy-link">Privacy Policy →</Link>
          </div>
        </div>
      </div>
    </div>
  )
}
