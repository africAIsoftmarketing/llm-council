import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useAuth } from '../auth/AuthContext';
import LanguageSwitcher from './LanguageSwitcher';
import productLogo from '../assets/logo-product.jpg';
import './AppHeader.css';

export default function AppHeader() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();

  if (!user) return null;

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const initials = (user.display_name || user.email || '?').slice(0, 1).toUpperCase();

  return (
    <header className="app-header" data-testid="app-header">
      <div className="app-header-left" onClick={() => navigate('/')} role="button" tabIndex={0}>
        <span className="app-header-logo-chip">
          <img src={productLogo} alt={t('header.logoAlt')} className="app-header-logo-img" />
        </span>
        <span className="app-header-title">{t('brand')}</span>
      </div>

      <nav className="app-header-nav">
        <button
          className={`hnav-link ${location.pathname === '/' ? 'active' : ''}`}
          onClick={() => navigate('/')}
          data-testid="nav-council"
        >{t('nav.council')}</button>
        {user.role === 'admin' && (
          <button
            className={`hnav-link ${location.pathname.startsWith('/admin') ? 'active' : ''}`}
            onClick={() => navigate('/admin')}
            data-testid="nav-admin"
          >{t('nav.admin')}</button>
        )}
      </nav>

      <div className="app-header-right">
        <LanguageSwitcher />
        <div className="credits-badge" data-testid="credits-balance" title={t('header.balanceTitle')}>
          <span className="credits-value">{user.credits}</span>
          <span className="credits-label">{t('header.creditsLabel')}</span>
        </div>
        <button className="buy-credits-btn" onClick={() => navigate('/credits')} data-testid="buy-credits-button">
          {t('header.buyCredits')}
        </button>
        <div className="user-chip" data-testid="user-chip">
          {user.avatar_url
            ? <img src={user.avatar_url} alt="" className="user-avatar" />
            : <span className="user-avatar user-avatar-fallback">{initials}</span>}
          <span className="user-name">{user.display_name || user.email}</span>
          <button className="logout-btn" onClick={handleLogout} data-testid="logout-button" title={t('header.logoutTitle')}>⎋</button>
        </div>
      </div>
    </header>
  );
}
