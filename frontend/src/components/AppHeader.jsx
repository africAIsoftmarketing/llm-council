import { useNavigate, useLocation } from 'react-router-dom';
import { useAuth } from '../auth/AuthContext';
import './AppHeader.css';

export default function AppHeader() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  if (!user) return null;

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  const initials = (user.display_name || user.email || '?').slice(0, 1).toUpperCase();

  return (
    <header className="app-header" data-testid="app-header">
      <div className="app-header-left" onClick={() => navigate('/')} role="button" tabIndex={0}>
        <span className="app-header-logo">⚖︎</span>
        <span className="app-header-title">LLM Council</span>
      </div>

      <nav className="app-header-nav">
        <button
          className={`hnav-link ${location.pathname === '/' ? 'active' : ''}`}
          onClick={() => navigate('/')}
          data-testid="nav-council"
        >Council</button>
        {user.role === 'admin' && (
          <button
            className={`hnav-link ${location.pathname.startsWith('/admin') ? 'active' : ''}`}
            onClick={() => navigate('/admin')}
            data-testid="nav-admin"
          >Administration</button>
        )}
      </nav>

      <div className="app-header-right">
        <div className="credits-badge" data-testid="credits-balance" title="Solde de crédits">
          <span className="credits-value">{user.credits}</span>
          <span className="credits-label">crédits</span>
        </div>
        <button className="buy-credits-btn" onClick={() => navigate('/credits')} data-testid="buy-credits-button">
          Acheter des crédits
        </button>
        <div className="user-chip" data-testid="user-chip">
          {user.avatar_url
            ? <img src={user.avatar_url} alt="" className="user-avatar" />
            : <span className="user-avatar user-avatar-fallback">{initials}</span>}
          <span className="user-name">{user.display_name || user.email}</span>
          <button className="logout-btn" onClick={handleLogout} data-testid="logout-button" title="Se déconnecter">⎋</button>
        </div>
      </div>
    </header>
  );
}
