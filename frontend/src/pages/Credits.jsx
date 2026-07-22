import { useState, useEffect, useCallback } from 'react';
import { PayPalScriptProvider, PayPalButtons } from '@paypal/react-paypal-js';
import AppHeader from '../components/AppHeader';
import { paymentsApi } from '../api';
import { useAuth } from '../auth/AuthContext';
import './Credits.css';

function TxKindBadge({ kind }) {
  const labels = { purchase: 'Achat', usage: 'Utilisation', admin_grant: 'Octroi admin', refund: 'Remboursement' };
  return <span className={`tx-badge tx-${kind}`}>{labels[kind] || kind}</span>;
}

export default function Credits() {
  const { refresh } = useAuth();
  const [config, setConfig] = useState(null);
  const [packs, setPacks] = useState([]);
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
      setTransactions(tx.transactions || []);
    } catch {
      showToast('Échec du chargement des packs', 'error');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const paypalOptions = config?.client_id
    ? { clientId: config.client_id, currency: config.currency || 'CAD', intent: 'capture' }
    : null;

  return (
    <div className="page-shell">
      <AppHeader />
      <main className="credits-main" data-testid="credits-page">
        <div className="credits-header">
          <h1>Acheter des crédits</h1>
          <p>Chaque requête au council consomme des crédits. Rechargez votre compte ci-dessous.</p>
        </div>

        {loading ? (
          <div className="credits-loading">Chargement…</div>
        ) : !paypalOptions ? (
          <div className="credits-warning" data-testid="paypal-not-configured">
            PayPal n'est pas configuré (PAYPAL_CLIENT_ID manquant).
          </div>
        ) : (
          <PayPalScriptProvider options={paypalOptions}>
            <div className="packs-grid">
              {packs.map((pack) => (
                <div className="pack-card" key={pack.id} data-testid={`pack-card-${pack.id}`}>
                  <div className="pack-name">{pack.name}</div>
                  <div className="pack-credits"><span>{pack.credits}</span> crédits</div>
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
                          showToast(`Paiement confirmé — solde: ${res.credits} crédits`, 'success');
                        } catch (err) {
                          showToast(err.message || 'Échec de la capture du paiement', 'error');
                        }
                      }}
                      onError={() => showToast('Erreur PayPal', 'error')}
                    />
                  </div>
                </div>
              ))}
            </div>
          </PayPalScriptProvider>
        )}

        <div className="tx-section">
          <h2>Historique des transactions</h2>
          {transactions.length === 0 ? (
            <div className="tx-empty" data-testid="tx-empty">Aucune transaction pour le moment.</div>
          ) : (
            <table className="tx-table" data-testid="transactions-table">
              <thead>
                <tr><th>Date</th><th>Type</th><th>Montant</th><th>Solde</th></tr>
              </thead>
              <tbody>
                {transactions.map((t) => (
                  <tr key={t.id}>
                    <td>{new Date(t.created_at).toLocaleString('fr-CA')}</td>
                    <td><TxKindBadge kind={t.kind} /></td>
                    <td className={t.amount >= 0 ? 'amt-pos' : 'amt-neg'}>{t.amount >= 0 ? '+' : ''}{t.amount}</td>
                    <td>{t.balance_after}</td>
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
