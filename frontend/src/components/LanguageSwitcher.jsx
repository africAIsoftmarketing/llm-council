import { useTranslation } from 'react-i18next';
import './LanguageSwitcher.css';

export default function LanguageSwitcher() {
  const { i18n, t } = useTranslation();
  const current = i18n.resolvedLanguage || i18n.language || 'en';
  const base = current.split('-')[0];

  const setLang = (lng) => {
    i18n.changeLanguage(lng);
    try { document.documentElement.lang = lng; } catch { /* noop */ }
  };

  return (
    <div className="lang-switcher" role="group" aria-label={t('lang.switch')} data-testid="language-switcher">
      <button
        type="button"
        className={`lang-btn ${base === 'en' ? 'active' : ''}`}
        onClick={() => setLang('en')}
        data-testid="lang-en"
        aria-pressed={base === 'en'}
      >{t('lang.en')}</button>
      <span className="lang-sep">/</span>
      <button
        type="button"
        className={`lang-btn ${base === 'fr' ? 'active' : ''}`}
        onClick={() => setLang('fr')}
        data-testid="lang-fr"
        aria-pressed={base === 'fr'}
      >{t('lang.fr')}</button>
    </div>
  );
}
