import { useTranslation } from 'react-i18next';
import './HowItWorks.css';

const ICONS = {
  input: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
    </svg>
  ),
  enrich: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 3l1.9 4.8L18.7 9l-4.8 1.2L12 15l-1.9-4.8L5.3 9l4.8-1.2z" />
      <path d="M19 15l.9 2.1L22 18l-2.1.9L19 21l-.9-2.1L16 18l2.1-.9z" />
    </svg>
  ),
  process: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <circle cx="9" cy="7" r="3" />
      <circle cx="17" cy="17" r="3" />
      <path d="M9 10v4a2 2 0 0 0 2 2h3" />
    </svg>
  ),
  output: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <path d="M9 15l2 2 4-4" />
    </svg>
  ),
};

const STAGES = ['input', 'enrich', 'process', 'output'];

export default function HowItWorks() {
  const { t } = useTranslation();
  return (
    <section className="how-it-works" data-testid="how-it-works">
      <div className="hiw-head">
        <h3 className="hiw-title">{t('how.title')}</h3>
        <p className="hiw-subtitle">{t('how.subtitle')}</p>
      </div>
      <div className="hiw-grid">
        {STAGES.map((key, i) => (
          <div className="hiw-card" data-testid={`hiw-card-${key}`} key={key}>
            <div className="hiw-card-top">
              <span className="hiw-icon">{ICONS[key]}</span>
              <span className="hiw-step-num">{i + 1}</span>
            </div>
            <span className="hiw-tag">{t(`how.${key}.tag`)}</span>
            <h4 className="hiw-card-title">{t(`how.${key}.title`)}</h4>
            <p className="hiw-card-desc">{t(`how.${key}.desc`)}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
