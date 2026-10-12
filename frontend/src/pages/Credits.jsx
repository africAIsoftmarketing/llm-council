import { useState, useEffect, useCallback } from 'react';
import { PayPalScriptProvider, PayPalButtons } from '@paypal/react-paypal-js';
import { useTranslation } from 'react-i18next';
import AppHeader from '../components/AppHeader';
import { paymentsApi } from '../api';
import { useAuth } from '../auth/AuthContext';
import './Credits.css';

function TxKindBadge({ kind }) {
  const { t } = useTranslation();
  return <span className={`tx-badge tx-${kind}`}>{t(`credits.kind.${kind}`, kind)}</span>;
}

export default function Credits() {
  const { refresh } = useAuth();
  const { t, i18n } = useTranslation();
  const [config, setConfig] = useState(null);
  const [packs, setPacks] = useState([]);
  const [freeInfo, setFreeInfo] = useState(null);
  const [claiming, setClaiming] = useState(false);
  const [transactions, setTransactions] = useState([]);
  const [toast, setToast] = useState(null);
  const [loading, setLoading] = useState(true);

  const showToast = (message, type = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };

  const loadAll = useCallback(async () => {
    try {
      const [cfg, p, tx] = await Promise.all([
        paymentsApi.config(), paymentsApi.packs(), paymentsApi.transactions(),
      ]);
      setConfig(cfg);
      setPacks(p.packs || []);
      setFreeInfo(p.free_discovery || null);
      setTransactions(tx.transactions || []);
    } catch {
      showToast(t('credits.loadFailed'), 'error');
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => { loadAll(); }, [loadAll]);

  // Free discovery pack (enabled by an admin): credited without PayPal.
  const claimFree = async (pack) => {
    if (claiming) return;
    setClaiming(true);
    try {
      const res = await paymentsApi.claimFreePack(pack.id);
      await refresh();
      await loadAll();
      showToast(t('credits.freeClaimed', { granted: res.granted, credits: res.credits }), 'success');
    } catch (err) {
      showToast(err.message === 'free_quota_reached' ? t('credits.freeQuotaReached') : (err.message || t('credits.freeClaimFailed')), 'error');
      await loadAll();
    } finally {
      setClaiming(false);
    }
  };

  const freeCard = (pack) => (
    <div className="pack-card pack-card-free" key={pack.id} data-testid={`pack-card-${pack.id}`}>
      <div className="pack-free-badge">{t('credits.freeBadge')}</div>
      <div className="pack-name">{pack.name}</div>
      <div className="pack-credits"><span>{pack.free_credits}</span> {t('credits.creditsWord')}</div>
      <div className="pack-price"><s>{pack.price_cad} {config?.currency || 'CAD'}</s> {t('credits.freePrice')}</div>
      {freeInfo && (
        <div className="pack-free-note">{t('credits.freeRemaining', { remaining: freeInfo.remaining, max: freeInfo.max_credits })}</div>
      )}
      <button type="button" className="pack-free-btn" onClick={() => claimFree(pack)}
        disabled={claiming} data-testid={`free-claim-${pack.id}`}>
        {claiming ? t('credits.freeClaiming') : t('credits.freeClaim', { credits: pack.free_credits })}
      </button>
    </div>
  );

  const paypalOptions = config?.client_id
    ? { clientId: config.client_id, currency: config.currency || 'CAD', intent: 'capture' }
    : null;

  const locale = (i18n.resolvedLanguage || 'en').startsWith('fr') ? 'fr-CA' : 'en-CA';

  return (
    <div className="page-shell">
      <AppHeader />
      <main className="credits-main" data-testid="credits-page">
        <div className="credits-header">
          <h1>{t('credits.title')}</h1>
          <p>{t('credits.subtitle')}</p>
        </div>

        {loading ? (
          <div className="credits-loading">{t('credits.loading')}</div>
        ) : !paypalOptions ? (
          <>
            <div className="credits-warning" data-testid="paypal-not-configured">
              {t('credits.paypalNotConfigured')}
            </div>
            {packs.some((pack) => pack.free) && (
              <div className="packs-grid">{packs.filter((pack) => pack.free).map(freeCard)}</div>
            )}
          </>
        ) : (
          <PayPalScriptProvider options={paypalOptions}>
            <div className="packs-grid">
              {packs.map((pack) => pack.free ? freeCard(pack) : (
                <div className="pack-card" key={pack.id} data-testid={`pack-card-${pack.id}`}>
                  <div className="pack-name">{pack.name}</div>
                  <div className="pack-credits"><span>{pack.credits}</span> {t('credits.creditsWord')}</div>
                  <div className="pack-price">{pack.price_cad} {config.currency}</div>
                  <div className="pack-paypal">
                    <PayPalButtons
                      style={{ layout: 'vertical', color: 'blue', shape: 'pill', label: 'pay' }}
                      createOrder={async () => {
                        const { order_id } = await paymentsApi.createOrder(pack.id);
                        return order_id;
                      }}
                      onApprove={async (data) => {
                        try {
                          const res = await paymentsApi.captureOrder(data.orderID);
                          await refresh();
                          await loadAll();
                          showToast(t('credits.paymentConfirmed', { credits: res.credits }), 'success');
                        } catch (err) {
                          showToast(err.message || t('credits.captureFailed'), 'error');
                        }
                      }}
                      onError={() => showToast(t('credits.paypalError'), 'error')}
                    />
                  </div>
                </div>
              ))}
            </div>
          </PayPalScriptProvider>
        )}

        <div className="tx-section">
          <h2>{t('credits.txHistory')}</h2>
          {transactions.length === 0 ? (
            <div className="tx-empty" data-testid="tx-empty">{t('credits.txEmpty')}</div>
          ) : (
            <table className="tx-table" data-testid="transactions-table">
              <thead>
                <tr><th>{t('credits.colDate')}</th><th>{t('credits.colType')}</th><th>{t('credits.colAmount')}</th><th>{t('credits.colBalance')}</th></tr>
              </thead>
              <tbody>
                {transactions.map((tx) => (
                  <tr key={tx.id}>
                    <td>{new Date(tx.created_at).toLocaleString(locale)}</td>
                    <td><TxKindBadge kind={tx.kind} /></td>
                    <td className={tx.amount >= 0 ? 'amt-pos' : 'amt-neg'}>{tx.amount >= 0 ? '+' : ''}{tx.amount}</td>
                    <td>{tx.balance_after}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </main>

      {toast && <div className={`toast toast-${toast.type}`} data-testid="toast-notification">{toast.message}</div>}
    </div>
  );
}
