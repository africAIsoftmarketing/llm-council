import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { authApi } from '../api';
import { useAuth } from '../auth/AuthContext';
import LanguageSwitcher from '../components/LanguageSwitcher';
import AppFooter from '../components/AppFooter';
import productLogo from '../assets/logo-product.jpg';
import './Login.css';

export default function Login() {
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const [devEmail, setDevEmail] = useState('');
  const [devOpen, setDevOpen] = useState(false);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  const handleGoogle = () => {
    // REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH
    window.location.href = authApi.loginUrl();
  };

  const handleDevLogin = async (e) => {
    e.preventDefault();
    setError('');
    setBusy(true);
    try {
      await authApi.devLogin(devEmail.trim(), devEmail.split('@')[0]);
      await refresh();
      navigate('/');
    } catch (err) {
      setError(err.status === 404 ? t('login.devDisabled') : (err.message || t('login.failed')));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="login-page" data-testid="login-page">
      <div className="login-lang"><LanguageSwitcher /></div>
      <div className="login-card">
        <div className="login-brand">
          <span className="login-logo-chip">
            <img src={productLogo} alt={t('header.logoAlt')} className="login-logo-img" />
          </span>
          <h1>{t('brand')}</h1>
        </div>
        <p className="login-tagline">{t('tagline')}</p>

        <button className="google-btn" onClick={handleGoogle} data-testid="google-login-button">
          <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
            <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
            <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
            <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
          </svg>
          {t('login.google')}
        </button>

        <button className="dev-toggle" onClick={() => setDevOpen((v) => !v)} data-testid="dev-toggle">
          {t('login.devToggle')}
        </button>

        {devOpen && (
          <form className="dev-form" onSubmit={handleDevLogin} data-testid="dev-login-form">
            <input
              type="email"
              placeholder={t('login.devPlaceholder')}
              value={devEmail}
              onChange={(e) => setDevEmail(e.target.value)}
              required
              data-testid="dev-email-input"
            />
            <button type="submit" disabled={busy} data-testid="dev-login-button">
              {busy ? t('login.connecting') : t('login.enter')}
            </button>
          </form>
        )}

        {error && <div className="login-error" data-testid="login-error">{error}</div>}
      </div>
      <AppFooter />
    </div>
  );
}
