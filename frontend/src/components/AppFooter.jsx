import { Link } from 'react-router-dom';
import { CONTACT_EMAIL } from './TermsModal';
import './AppFooter.css';

export default function AppFooter() {
  const year = new Date().getFullYear();
  return (
    <footer className="app-footer" data-testid="app-footer">
      <div className="app-footer-inner">
        <span className="footer-copy">© {year} LLM Council</span>
        <nav className="footer-links">
          <a href={`mailto:${CONTACT_EMAIL}`} data-testid="footer-contact-email">
            {CONTACT_EMAIL}
          </a>
          <span className="footer-sep">•</span>
          <Link to="/legal" data-testid="footer-legal-link">Legal notice</Link>
          <span className="footer-sep">•</span>
          <Link to="/legal#privacy" data-testid="footer-privacy-link">Privacy</Link>
        </nav>
      </div>
    </footer>
  );
}
