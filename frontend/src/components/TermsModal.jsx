import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import LanguageSwitcher from './LanguageSwitcher';
import productLogo from '../assets/logo-product.jpg';
import './TermsModal.css';

export const TERMS_KEY = 'llm_council_terms_accepted_v1';
export const CONTACT_EMAIL = 'llmcouncilsupport@africaisoft.africa';

const SECTION_KEYS = [
  'acceptance', 'service', 'accounts', 'acceptableUse', 'providers', 'ip',
  'content', 'disclaimer', 'availability', 'termination', 'law',
];

export function hasAcceptedTerms() {
  try {
    return localStorage.getItem(TERMS_KEY) === 'true';
  } catch {
    return false;
  }
}

export default function TermsModal({ onAccept }) {
  const [checked, setChecked] = useState(false);
  const { t } = useTranslation();

  const accept = () => {
    if (!checked) return;
    try {
      localStorage.setItem(TERMS_KEY, 'true');
    } catch { /* noop */ }
    onAccept();
  };

  return (
    <div className="terms-overlay" data-testid="terms-modal">
      <div className="terms-modal" role="dialog" aria-modal="true" aria-labelledby="terms-title">
        <header className="terms-header">
          <span className="terms-logo-chip">
            <img src={productLogo} alt={t('header.logoAlt')} className="terms-logo-img" />
          </span>
          <h2 id="terms-title">{t('terms.modalTitle')}</h2>
          <div className="terms-header-lang"><LanguageSwitcher /></div>
        </header>

        <div className="terms-body">
          {SECTION_KEYS.map((key) => (
            <section key={key}>
              <h3>{t(`terms.sections.${key}.h`)}</h3>
              <p>{t(`terms.sections.${key}.p`)}</p>
            </section>
          ))}

          <section>
            <h3>{t('terms.sections.contact.h')}</h3>
            <p>
              {t('terms.sections.contact.p')}{' '}
              <a href={`mailto:${CONTACT_EMAIL}`}>{CONTACT_EMAIL}</a>.
            </p>
          </section>

          <section>
            <h3>{t('terms.dataProtection.h')}</h3>
            <p>{t('terms.dataProtection.intro')}</p>
            <ul>
              <li>{t('terms.dataProtection.item1')}</li>
              <li>{t('terms.dataProtection.item2')}</li>
              <li>{t('terms.dataProtection.item3')}</li>
            </ul>
            <p>{t('terms.dataProtection.p1')}</p>
          </section>
        </div>

        <label className="terms-checkbox">
          <input
            type="checkbox"
            checked={checked}
            onChange={(e) => setChecked(e.target.checked)}
            data-testid="terms-accept-checkbox"
          />
          <span>{t('terms.checkbox')}</span>
        </label>

        <div className="terms-actions">
          <button
            className="terms-accept-btn"
            disabled={!checked}
            onClick={accept}
            data-testid="terms-accept-btn"
          >
            {t('terms.accept')}
          </button>
        </div>
      </div>
    </div>
  );
}
