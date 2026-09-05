import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { CONTACT_EMAIL } from './TermsModal';
import africaisoftLogo from '../assets/logo-africaisoft.jpg';
import './AppFooter.css';

const AFRICAISOFT_URL = '#';

export default function AppFooter() {
  const year = new Date().getFullYear();
  const { t } = useTranslation();
  return (
    <footer className="app-footer" data-testid="app-footer">
      <div className="app-footer-inner">
        <div className="footer-brand">
          <span className="footer-copy">{t('footer.copy', { year })}</span>
          <a
            className="footer-by"
            href={AFRICAISOFT_URL}
            target={AFRICAISOFT_URL === '#' ? undefined : '_blank'}
            rel="noreferrer"
            data-testid="footer-africaisoft"
          >
            <img src={africaisoftLogo} alt={t('footer.africaisoftAlt')} className="footer-africaisoft-logo" />
            <span className="footer-by-text">{t('footer.by')}</span>
          </a>
        </div>
        <nav className="footer-links">
          <a href={`mailto:${CONTACT_EMAIL}`} data-testid="footer-contact-email">
            {CONTACT_EMAIL}
          </a>
          <span className="footer-sep">•</span>
          <Link to="/legal" data-testid="footer-legal-link">{t('footer.legal')}</Link>
          <span className="footer-sep">•</span>
          <Link to="/legal#privacy" data-testid="footer-privacy-link">{t('footer.privacy')}</Link>
        </nav>
      </div>
    </footer>
  );
}
