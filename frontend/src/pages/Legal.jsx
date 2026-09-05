import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { CONTACT_EMAIL } from '../components/TermsModal';
import LanguageSwitcher from '../components/LanguageSwitcher';
import './Legal.css';

const SECTION_KEYS = [
  'acceptance', 'service', 'accounts', 'acceptableUse', 'providers', 'ip',
  'content', 'disclaimer', 'availability', 'termination', 'law',
];

export default function Legal() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  const email = <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>;

  return (
    <div className="legal-page" data-testid="legal-page">
      <div className="legal-container">
        <div className="legal-topbar">
          <button className="legal-back" onClick={() => navigate('/')} data-testid="legal-back-btn">
            {t('terms.back')}
          </button>
          <LanguageSwitcher />
        </div>

        <h1>{t('terms.pageTitle')}</h1>

        <section>
          <h2>{t('terms.legalNotice.h')}</h2>
          <p>{t('terms.legalNotice.p')}</p>
          <p>
            <strong>{t('terms.legalNotice.publisher')}</strong>{' '}{email}
          </p>
        </section>

        <section id="privacy">
          <h2>{t('terms.dataProtection.h')}</h2>
          <p>{t('terms.dataProtection.intro')}</p>
          <ul>
            <li>{t('terms.dataProtection.item1')}</li>
            <li>{t('terms.dataProtection.item2')}</li>
            <li>{t('terms.dataProtection.item3')}</li>
          </ul>
          <p>{t('terms.dataProtection.p1')}</p>
          <p>{t('terms.dataProtection.p2')}{' '}{email}.</p>
        </section>

        <section>
          <h2>{t('terms.pageTitle')}</h2>
          {SECTION_KEYS.map((key) => (
            <div key={key} className="legal-subsection">
              <h3>{t(`terms.sections.${key}.h`)}</h3>
              <p>{t(`terms.sections.${key}.p`)}</p>
            </div>
          ))}
        </section>

        <section>
          <h2>{t('terms.contactHeading')}</h2>
          <p>
            {t('terms.sections.contact.p')}{' '}
            <a href={`mailto:${CONTACT_EMAIL}`} data-testid="legal-contact-email">{CONTACT_EMAIL}</a>.
          </p>
        </section>
      </div>
    </div>
  );
}
