import { Link, useNavigate } from 'react-router-dom'
import { Header } from '../components/layout/Header'
import './LegalPage.css'

export default function PrivacyPolicy() {
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
          <h1>Privacy Policy</h1>
          <p className="last-updated">Last Updated: {new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</p>

          <section>
            <h2>1. Introduction</h2>
            <p>
              Empirico ("we," "us," or "our") is committed to protecting your privacy and the confidentiality of 
              information you provide. This Privacy Policy explains how we collect, use, disclose, and safeguard your 
              information when you use our Service.
            </p>
            <p>
              By using Empirico, you agree to the collection and use of information in accordance with this Privacy 
              Policy. If you do not agree with our policies and practices, you should not use the Service.
            </p>
          </section>

          <section>
            <h2>2. Information We Collect</h2>
            
            <h3>2.1 Information You Provide</h3>
            <p>We collect information that you provide directly to us, including:</p>
            <ul>
              <li><strong>Account Information:</strong> Name, email address, professional credentials, and other information 
              you provide when creating an account</li>
              <li><strong>Query Information:</strong> Medical questions, clinical scenarios, and other content you submit 
              through the Service</li>
              <li><strong>Communication Data:</strong> Information you provide when contacting us for support or other 
              inquiries</li>
            </ul>

            <h3>2.2 Automatically Collected Information</h3>
            <p>We automatically collect certain information when you use the Service, including:</p>
            <ul>
              <li><strong>Usage Data:</strong> Information about how you interact with the Service, including pages visited, 
              features used, and time spent</li>
              <li><strong>Device Information:</strong> IP address, browser type, operating system, device identifiers, and 
              other technical information</li>
              <li><strong>Log Data:</strong> Server logs, error reports, and performance data</li>
              <li><strong>Cookies and Tracking Technologies:</strong> Information collected through cookies, web beacons, 
              and similar technologies</li>
            </ul>

            <h3>2.3 Information We Do NOT Collect</h3>
            <p>
              <strong>CRITICAL:</strong> We do not collect, store, or process Protected Health Information (PHI) as defined 
              by HIPAA, including:
            </p>
            <ul>
              <li>Patient names, dates of birth, or other identifying information</li>
              <li>Medical record numbers or health plan beneficiary numbers</li>
              <li>Specific patient addresses, phone numbers, or email addresses</li>
              <li>Any other information that could be used to identify a specific patient</li>
            </ul>
            <p>
              You are strictly prohibited from including any patient identifying information in your queries or interactions 
              with the Service.
            </p>
          </section>

          <section>
            <h2>3. How We Use Your Information</h2>
            <p>We use the information we collect to:</p>
            <ul>
              <li>Provide, maintain, and improve the Service</li>
              <li>Process and respond to your queries and requests</li>
              <li>Authenticate your identity and manage your account</li>
              <li>Send you service-related communications, including updates and security alerts</li>
              <li>Monitor and analyze usage patterns to improve the Service</li>
              <li>Detect, prevent, and address technical issues and security threats</li>
              <li>Comply with legal obligations and enforce our Terms of Service</li>
              <li>Conduct research and development to improve our AI models and services</li>
            </ul>
            <p>
              <strong>We do NOT use your information to:</strong>
            </p>
            <ul>
              <li>Identify or contact patients</li>
              <li>Create patient profiles or medical records</li>
              <li>Share information with third parties for marketing purposes without your consent</li>
            </ul>
          </section>

          <section>
            <h2>4. Information Sharing and Disclosure</h2>
            <p>We may share your information in the following circumstances:</p>

            <h3>4.1 Service Providers</h3>
            <p>
              We may share information with third-party service providers who perform services on our behalf, such as cloud 
              hosting, data analytics, and customer support. These providers are contractually obligated to protect your 
              information and use it only for the purposes we specify.
            </p>

            <h3>4.2 Legal Requirements</h3>
            <p>
              We may disclose information if required by law, court order, or governmental regulation, or if we believe 
              disclosure is necessary to:
            </p>
            <ul>
              <li>Comply with legal obligations</li>
              <li>Protect and defend our rights or property</li>
              <li>Prevent or investigate possible wrongdoing</li>
              <li>Protect the personal safety of users or the public</li>
            </ul>

            <h3>4.3 Business Transfers</h3>
            <p>
              In the event of a merger, acquisition, or sale of assets, your information may be transferred to the acquiring 
              entity, subject to the same privacy protections.
            </p>

            <h3>4.4 With Your Consent</h3>
            <p>
              We may share your information with third parties when you explicitly consent to such sharing.
            </p>

            <h3>4.5 Aggregated and De-identified Data</h3>
            <p>
              We may share aggregated, anonymized, or de-identified data that cannot be used to identify you or any 
              individual for research, analytics, or other purposes.
            </p>
          </section>

          <section>
            <h2>5. Data Security</h2>
            <p>
              We implement industry-standard security measures to protect your information from unauthorized access, 
              disclosure, alteration, or destruction, including:
            </p>
            <ul>
              <li><strong>Encryption:</strong> Data in transit is encrypted using TLS/SSL protocols. Data at rest is 
              encrypted using industry-standard encryption algorithms</li>
              <li><strong>Access Controls:</strong> Strict access controls and authentication mechanisms to limit access 
              to authorized personnel only</li>
              <li><strong>Regular Security Audits:</strong> Regular security assessments and vulnerability testing</li>
              <li><strong>Data Backup:</strong> Regular backups with secure storage</li>
              <li><strong>Incident Response:</strong> Procedures for detecting, responding to, and mitigating security 
              incidents</li>
            </ul>
            <p>
              However, no method of transmission over the Internet or electronic storage is 100% secure. While we strive 
              to use commercially acceptable means to protect your information, we cannot guarantee absolute security.
            </p>
          </section>

          <section>
            <h2>6. Data Retention</h2>
            <p>
              We retain your information for as long as necessary to provide the Service, comply with legal obligations, 
              resolve disputes, and enforce our agreements. Specifically:
            </p>
            <ul>
              <li><strong>Account Information:</strong> Retained while your account is active and for a reasonable period 
              after account closure</li>
              <li><strong>Query Data:</strong> Retained for service improvement purposes, typically for up to [X] years, 
              unless you request deletion</li>
              <li><strong>Legal Requirements:</strong> Some information may be retained longer as required by law or for 
              legitimate business purposes</li>
            </ul>
            <p>
              You may request deletion of your information at any time by contacting us, subject to legal and operational 
              requirements.
            </p>
          </section>

          <section>
            <h2>7. Your Rights and Choices</h2>
            <p>Depending on your location, you may have the following rights regarding your information:</p>

            <h3>7.1 Access and Portability</h3>
            <p>
              You have the right to access and receive a copy of your personal information in a structured, commonly used, 
              and machine-readable format.
            </p>

            <h3>7.2 Correction</h3>
            <p>
              You have the right to correct inaccurate or incomplete information. You can update your account information 
              through your account settings or by contacting us.
            </p>

            <h3>7.3 Deletion</h3>
            <p>
              You have the right to request deletion of your personal information, subject to legal and operational 
              requirements. We will delete your information unless we have a legitimate reason to retain it.
            </p>

            <h3>7.4 Objection and Restriction</h3>
            <p>
              You have the right to object to certain processing of your information or request restriction of processing 
              in certain circumstances.
            </p>

            <h3>7.5 Withdrawal of Consent</h3>
            <p>
              Where processing is based on consent, you have the right to withdraw consent at any time, without affecting 
              the lawfulness of processing based on consent before withdrawal.
            </p>

            <h3>7.6 Opt-Out of Communications</h3>
            <p>
              You can opt-out of receiving promotional communications from us by following the unsubscribe instructions 
              in our emails or by contacting us directly.
            </p>
          </section>

          <section>
            <h2>8. Cookies and Tracking Technologies</h2>
            <p>
              We use cookies and similar tracking technologies to collect and store information about your preferences and 
              usage patterns. You can control cookies through your browser settings, but disabling cookies may limit your 
              ability to use certain features of the Service.
            </p>
            <p>We use cookies for:</p>
            <ul>
              <li>Authentication and session management</li>
              <li>Remembering your preferences</li>
              <li>Analyzing usage patterns</li>
              <li>Improving service performance</li>
            </ul>
          </section>

          <section>
            <h2>9. Children's Privacy</h2>
            <p>
              The Service is not intended for individuals under the age of 18. We do not knowingly collect personal 
              information from children. If you believe we have collected information from a child, please contact us 
              immediately, and we will take steps to delete such information.
            </p>
          </section>

          <section>
            <h2>10. International Data Transfers</h2>
            <p>
              Your information may be transferred to and processed in countries other than your country of residence. 
              These countries may have data protection laws that differ from those in your country. We take appropriate 
              safeguards to ensure your information receives adequate protection, including:
            </p>
            <ul>
              <li>Standard contractual clauses approved by relevant data protection authorities</li>
              <li>Other appropriate safeguards as required by applicable law</li>
            </ul>
          </section>

          <section>
            <h2>11. HIPAA and Healthcare Privacy Compliance</h2>
            <p>
              <strong>11.1 Business Associate Agreement:</strong> If you are a Covered Entity under HIPAA and require a 
              Business Associate Agreement (BAA), please contact us to discuss appropriate arrangements.
            </p>
            <p>
              <strong>11.2 No PHI Collection:</strong> As stated throughout this Policy, we do not collect, store, or 
              process Protected Health Information (PHI). The Service is designed to operate without PHI to minimize 
              privacy risks and regulatory compliance requirements.
            </p>
            <p>
              <strong>11.3 Your Responsibility:</strong> You are solely responsible for ensuring compliance with HIPAA and 
              other applicable healthcare privacy laws when using the Service. This includes ensuring that no PHI is 
              included in your queries or interactions with the Service.
            </p>
          </section>

          <section>
            <h2>12. California Privacy Rights (CCPA/CPRA)</h2>
            <p>
              If you are a California resident, you have additional rights under the California Consumer Privacy Act 
              (CCPA) and California Privacy Rights Act (CPRA), including:
            </p>
            <ul>
              <li>The right to know what personal information we collect, use, and disclose</li>
              <li>The right to delete personal information</li>
              <li>The right to opt-out of the sale or sharing of personal information (we do not sell personal information)</li>
              <li>The right to non-discrimination for exercising your privacy rights</li>
            </ul>
            <p>
              To exercise these rights, please contact us using the information provided in Section 15.
            </p>
          </section>

          <section>
            <h2>13. European Privacy Rights (GDPR)</h2>
            <p>
              If you are located in the European Economic Area (EEA) or United Kingdom, you have additional rights under 
              the General Data Protection Regulation (GDPR), including the rights described in Section 7. To exercise 
              these rights, please contact us using the information provided in Section 15.
            </p>
            <p>
              <strong>Legal Basis for Processing:</strong> We process your information based on:
            </p>
            <ul>
              <li>Your consent</li>
              <li>Performance of a contract (providing the Service)</li>
              <li>Compliance with legal obligations</li>
              <li>Legitimate interests (service improvement, security, fraud prevention)</li>
            </ul>
          </section>

          <section>
            <h2>14. Changes to This Privacy Policy</h2>
            <p>
              We may update this Privacy Policy from time to time. We will notify you of material changes by:
            </p>
            <ul>
              <li>Posting the updated Privacy Policy on the Service</li>
              <li>Updating the "Last Updated" date</li>
              <li>Sending you an email notification (for significant changes)</li>
            </ul>
            <p>
              Your continued use of the Service after such changes constitutes your acceptance of the updated Privacy Policy.
            </p>
          </section>

          <section>
            <h2>15. Contact Us</h2>
            <p>
              If you have any questions, concerns, or requests regarding this Privacy Policy or our privacy practices, 
              please contact us at:
            </p>
            <p>
              <strong>Empirico</strong><br />
              Email: empiricoai26@gmail.com<br />
    
            </p>
            <p>
              For privacy-related requests, please include sufficient information to verify your identity and specify 
              the nature of your request.
            </p>
          </section>

          <div className="legal-footer">
            <Link to="/" className="back-link">← Back to Home</Link>
            <Link to="/terms" className="terms-link">Terms of Service →</Link>
          </div>
        </div>
      </div>
    </div>
  )
}

