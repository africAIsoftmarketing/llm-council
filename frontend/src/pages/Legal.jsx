import { useNavigate } from 'react-router-dom';
import { CONTACT_EMAIL } from '../components/TermsModal';
import './Legal.css';

export default function Legal() {
  const navigate = useNavigate();
  return (
    <div className="legal-page" data-testid="legal-page">
      <div className="legal-container">
        <button className="legal-back" onClick={() => navigate('/')} data-testid="legal-back-btn">
          ← Back to Council
        </button>

        <h1>Legal Notice &amp; Privacy</h1>

        <section>
          <h2>Legal notice (Mentions légales)</h2>
          <p>
            <strong>LLM Council</strong> is a multi-model AI deliberation platform operated by
            Africaisoft. This service is provided “as is”, without warranty of any kind. The AI-generated
            content is produced by third-party language model providers and may be inaccurate or incomplete.
          </p>
          <p>
            <strong>Publisher / Contact:</strong>{' '}
            <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>
          </p>
        </section>

        <section id="privacy">
          <h2>Privacy &amp; Data Protection</h2>
          <p>
            We process only the data required to operate the service:
          </p>
          <ul>
            <li>Account identity: email address and display name.</li>
            <li>Conversations, prompts and documents you submit, used to generate responses.</li>
            <li>Credit and transaction records related to your usage.</li>
          </ul>
          <p>
            Prompts and documents are transmitted to the configured AI providers (e.g. OpenRouter model
            endpoints) solely to produce responses. We do not sell your personal data. Data is retained
            while your account is active and may be deleted upon request.
          </p>
          <p>
            To exercise your rights (access, rectification, deletion) or for any privacy question, contact{' '}
            <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
          </p>
        </section>

        <section>
          <h2>Terms of Use</h2>
          <p>
            By using the platform you agree to use it lawfully, not to submit harmful or infringing content,
            and not to disrupt the service. Credits are consumed per council request according to the pricing
            displayed in your account. Continued use constitutes acceptance of these terms.
          </p>
        </section>

        <section>
          <h2>Contact</h2>
          <p>
            Support &amp; legal enquiries:{' '}
            <a href={`mailto:${CONTACT_EMAIL}`} data-testid="legal-contact-email">{CONTACT_EMAIL}</a>
          </p>
        </section>
      </div>
    </div>
  );
}
