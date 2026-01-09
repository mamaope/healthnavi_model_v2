import { Link, useNavigate } from 'react-router-dom'
import { Header } from '../components/layout/Header'
import './LegalPage.css'

export default function TermsOfService() {
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
          <h1>Terms of Service</h1>
          <p className="last-updated">Last Updated: {new Date().toLocaleDateString('en-US', { year: 'numeric', month: 'long', day: 'numeric' })}</p>

          <section>
            <h2>1. Acceptance of Terms</h2>
            <p>
              By accessing or using Empirico ("the Service"), you agree to be bound by these Terms of Service ("Terms"). 
              If you do not agree to these Terms, you may not access or use the Service. These Terms constitute a legally 
              binding agreement between you and Empirico.
            </p>
          </section>

          <section>
            <h2>2. Description of Service</h2>
            <p>
              Empirico is an artificial intelligence-powered clinical information support tool designed to assist healthcare 
              professionals in making informed medical decisions. The Service provides informational guidance based on medical 
              literature, clinical guidelines, and evidence-based practices.
            </p>
            <p>
              <strong>IMPORTANT:</strong> The Service is intended for use by qualified healthcare professionals only. It is 
              not a substitute for professional medical judgment, diagnosis, or treatment. The Service does not provide medical 
              advice, diagnosis, or treatment recommendations for specific patients.
            </p>
          </section>

          <section>
            <h2>3. Medical Disclaimer</h2>
            <p>
              <strong>3.1 No Medical Advice:</strong> The information provided by Empirico is for informational and 
              educational purposes only. It is not intended to be, and should not be construed as, medical advice, diagnosis, 
              or treatment recommendations for any specific individual or condition.
            </p>
            <p>
              <strong>3.2 Professional Judgment Required:</strong> Healthcare professionals must exercise their independent 
              professional judgment when using information from the Service. All clinical decisions must be based on a 
              comprehensive evaluation of the patient, including physical examination, medical history, and appropriate 
              diagnostic testing.
            </p>
            <p>
              <strong>3.3 No Patient-Provider Relationship:</strong> Use of the Service does not create a patient-provider 
              relationship. Empirico is not a healthcare provider and does not provide medical services.
            </p>
            <p>
              <strong>3.4 Emergency Situations:</strong> The Service is not intended for use in emergency situations. In 
              case of a medical emergency, contact emergency services immediately.
            </p>
          </section>

          <section>
            <h2>4. User Responsibilities</h2>
            <p>
              <strong>4.1 Professional Qualifications:</strong> You represent and warrant that you are a qualified healthcare 
              professional licensed to practice in your jurisdiction. You agree to use the Service only in accordance with 
              applicable laws, regulations, and professional standards.
            </p>
            <p>
              <strong>4.2 Patient Privacy:</strong> You agree not to include any patient identifying information (including 
              but not limited to names, dates of birth, medical record numbers, addresses, or any other Protected Health 
              Information as defined by HIPAA) when using the Service. You are solely responsible for maintaining patient 
              confidentiality and complying with all applicable privacy laws, including HIPAA, GDPR, and other relevant 
              regulations.
            </p>
            <p>
              <strong>4.3 Accurate Information:</strong> You agree to provide accurate and complete information when using 
              the Service. You are responsible for verifying the accuracy of any information you input.
            </p>
            <p>
              <strong>4.4 Account Security:</strong> You are responsible for maintaining the confidentiality of your account 
              credentials and for all activities that occur under your account.
            </p>
          </section>

          <section>
            <h2>5. Prohibited Uses</h2>
            <p>You agree not to:</p>
            <ul>
              <li>Use the Service for any illegal or unauthorized purpose</li>
              <li>Include any patient identifying information in queries or interactions with the Service</li>
              <li>Violate any applicable laws, regulations, or professional standards</li>
              <li>Attempt to reverse engineer, decompile, or disassemble the Service</li>
              <li>Interfere with or disrupt the Service or servers connected to the Service</li>
              <li>Use the Service to create competing products or services</li>
              <li>Transmit any viruses, malware, or other harmful code</li>
              <li>Use automated systems to access the Service without authorization</li>
            </ul>
          </section>

          <section>
            <h2>6. Intellectual Property</h2>
            <p>
              The Service, including its software, algorithms, content, and design, is protected by copyright, trademark, 
              and other intellectual property laws. You may not copy, modify, distribute, or create derivative works based 
              on the Service without express written permission from Empirico.
            </p>
            <p>
              You retain ownership of any content you submit to the Service. By submitting content, you grant Empirico 
              a non-exclusive, worldwide, royalty-free license to use, store, and process such content solely for the 
              purpose of providing and improving the Service.
            </p>
          </section>

          <section>
            <h2>7. Limitation of Liability</h2>
            <p>
              <strong>7.1 Disclaimer of Warranties:</strong> THE SERVICE IS PROVIDED "AS IS" AND "AS AVAILABLE" WITHOUT 
              WARRANTIES OF ANY KIND, EITHER EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO WARRANTIES OF MERCHANTABILITY, 
              FITNESS FOR A PARTICULAR PURPOSE, OR NON-INFRINGEMENT.
            </p>
            <p>
              <strong>7.2 Limitation of Liability:</strong> TO THE MAXIMUM EXTENT PERMITTED BY LAW, EMPIRICO SHALL NOT 
              BE LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES, INCLUDING BUT NOT LIMITED 
              TO LOSS OF PROFITS, DATA, OR USE, ARISING OUT OF OR IN CONNECTION WITH YOUR USE OF THE SERVICE, REGARDLESS OF 
              THE THEORY OF LIABILITY.
            </p>
            <p>
              <strong>7.3 Medical Decisions:</strong> EMPIRICO SHALL NOT BE LIABLE FOR ANY MEDICAL DECISIONS, 
              DIAGNOSES, TREATMENTS, OR OUTCOMES RESULTING FROM THE USE OR MISUSE OF THE SERVICE. YOU ASSUME FULL 
              RESPONSIBILITY FOR ALL CLINICAL DECISIONS MADE BASED ON INFORMATION FROM THE SERVICE.
            </p>
            <p>
              <strong>7.4 Maximum Liability:</strong> IN NO EVENT SHALL EMPIRICO'S TOTAL LIABILITY TO YOU EXCEED THE 
              AMOUNT YOU PAID TO EMPIRICO IN THE TWELVE (12) MONTHS PRECEDING THE CLAIM, OR $100, WHICHEVER IS GREATER.
            </p>
          </section>

          <section>
            <h2>8. Indemnification</h2>
            <p>
              You agree to indemnify, defend, and hold harmless Empirico, its officers, directors, employees, agents, 
              and affiliates from and against any and all claims, damages, losses, liabilities, costs, and expenses (including 
              reasonable attorneys' fees) arising out of or relating to:
            </p>
            <ul>
              <li>Your use or misuse of the Service</li>
              <li>Your violation of these Terms</li>
              <li>Your violation of any applicable laws or regulations</li>
              <li>Your breach of patient confidentiality or privacy laws</li>
              <li>Any medical decisions or outcomes resulting from your use of the Service</li>
            </ul>
          </section>

          <section>
            <h2>9. Privacy and Data Protection</h2>
            <p>
              Your use of the Service is also governed by our Privacy Policy, which is incorporated into these Terms by 
              reference. By using the Service, you consent to the collection, use, and disclosure of information as described 
              in the Privacy Policy.
            </p>
          </section>

          <section>
            <h2>10. Modifications to Terms</h2>
            <p>
              Empirico reserves the right to modify these Terms at any time. We will notify users of material changes 
              by posting the updated Terms on the Service and updating the "Last Updated" date. Your continued use of the 
              Service after such modifications constitutes your acceptance of the modified Terms.
            </p>
          </section>

          <section>
            <h2>11. Termination</h2>
            <p>
              Empirico may terminate or suspend your access to the Service at any time, with or without cause or notice, 
              for any reason, including but not limited to violation of these Terms. Upon termination, your right to use the 
              Service will immediately cease.
            </p>
            <p>
              You may terminate your account at any time by contacting us or through your account settings. Upon termination, 
              your data may be deleted in accordance with our Privacy Policy.
            </p>
          </section>

          <section>
            <h2>12. Governing Law and Dispute Resolution</h2>
            <p>
              <strong>12.1 Governing Law:</strong> These Terms shall be governed by and construed in accordance with the 
              laws of Uganda, without regard to its conflict of law provisions.
            </p>
            <p>
              <strong>12.2 Dispute Resolution:</strong> Any disputes arising out of or relating to these Terms or the Service 
              shall be resolved through binding arbitration in accordance with the rules of Empirico, 
              except where prohibited by law. The arbitration shall take place in Uganda.
            </p>
            <p>
              <strong>12.3 Class Action Waiver:</strong> You agree that any disputes will be resolved on an individual basis 
              and waive any right to participate in a class action lawsuit or class-wide arbitration.
            </p>
          </section>

          <section>
            <h2>13. Severability</h2>
            <p>
              If any provision of these Terms is found to be unenforceable or invalid, that provision shall be limited or 
              eliminated to the minimum extent necessary, and the remaining provisions shall remain in full force and effect.
            </p>
          </section>

          <section>
            <h2>14. Entire Agreement</h2>
            <p>
              These Terms, together with the Privacy Policy, constitute the entire agreement between you and Empirico 
              regarding the use of the Service and supersede all prior agreements and understandings.
            </p>
          </section>

          <section>
            <h2>15. Contact Information</h2>
            <p>
              If you have any questions about these Terms, please contact us at:
            </p>
            <p>
              <strong>Empirico</strong><br />
              Email: empiricoai26@gmail.com<br />
        
            </p>
          </section>

          <div className="legal-footer">
            <Link to="/" className="back-link">← Back to Home</Link>
            <Link to="/privacy" className="privacy-link">Privacy Policy →</Link>
          </div>
        </div>
      </div>
    </div>
  )
}

