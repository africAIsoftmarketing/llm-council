import { useState, useEffect, useCallback } from 'react';
import AppHeader from '../components/AppHeader';
import { adminApi } from '../api';
import './Admin.css';

function useToast() {
  const [toast, setToast] = useState(null);
  const show = (message, type = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  };
  return [toast, show];
}

/* ===================== Models tab ===================== */
function ModelsTab({ showToast }) {
  const [data, setData] = useState({ council_models: [], chairman_model: '' });
  const [newModel, setNewModel] = useState('');
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => setData(await adminApi.getModels()), []);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!newModel.trim()) return;
    setBusy(true);
    try {
      await adminApi.addModel(newModel.trim());
      setNewModel('');
      await load();
      showToast('Modèle ajouté et validé', 'success');
    } catch (err) {
      showToast(err.message || 'Modèle invalide', 'error');
    } finally { setBusy(false); }
  };

  const remove = async (m) => {
    if (!window.confirm(`Supprimer le modèle ${m} ?`)) return;
    try { await adminApi.deleteModel(m); await load(); showToast('Modèle supprimé', 'success'); }
    catch (err) { showToast(err.message, 'error'); }
  };

  const setChairman = async (m) => {
    try { await adminApi.setChairman(m); await load(); showToast('Chairman mis à jour', 'success'); }
    catch (err) { showToast(err.message, 'error'); }
  };

  return (
    <div className="tab-content" data-testid="admin-models-tab">
      <h2>Modèles du Council</h2>
      <div className="add-model-row">
        <input
          placeholder="ex. anthropic/claude-sonnet-4.5"
          value={newModel}
          onChange={(e) => setNewModel(e.target.value)}
          data-testid="add-model-input"
        />
        <button onClick={add} disabled={busy} data-testid="add-model-button">
          {busy ? 'Validation…' : 'Valider & ajouter'}
        </button>
      </div>
      <table className="admin-table">
        <thead><tr><th>Modèle</th><th>Chairman</th><th></th></tr></thead>
        <tbody>
          {data.council_models.map((m) => (
            <tr key={m} data-testid={`model-row-${m}`}>
              <td className="mono">{m}</td>
              <td>
                <input
                  type="radio"
                  name="chairman"
                  checked={data.chairman_model === m}
                  onChange={() => setChairman(m)}
                  data-testid={`chairman-radio-${m}`}
                />
              </td>
              <td>
                <button className="icon-btn danger" onClick={() => remove(m)} data-testid={`delete-model-${m}`}>🗑</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="hint">Les changements prennent effet immédiatement. Minimum 2 modèles requis.</p>
    </div>
  );
}

/* ===================== Users tab ===================== */
function UsersTab({ showToast }) {
  const [users, setUsers] = useState([]);
  const [search, setSearch] = useState('');

  const load = useCallback(async (q = '') => {
    const res = await adminApi.listUsers(q);
    setUsers(res.users || []);
  }, []);
  useEffect(() => { load(); }, [load]);

  const toggleActive = async (u) => {
    try { await adminApi.updateUser(u.id, { is_active: !u.is_active }); await load(search); }
    catch (err) { showToast(err.message, 'error'); }
  };
  const toggleRole = async (u) => {
    try { await adminApi.updateUser(u.id, { role: u.role === 'admin' ? 'user' : 'admin' }); await load(search); }
    catch (err) { showToast(err.message, 'error'); }
  };
  const adjust = async (u) => {
    const amountStr = window.prompt('Ajustement de crédits (nombre, négatif pour retirer) :', '');
    if (amountStr === null) return;
    const amount = parseInt(amountStr, 10);
    if (!amount) return;
    const reason = window.prompt('Motif :', 'Ajustement admin') || 'Ajustement admin';
    try { await adminApi.adjustCredits(u.id, amount, reason); await load(search); showToast('Crédits ajustés', 'success'); }
    catch (err) { showToast(err.message, 'error'); }
  };

  return (
    <div className="tab-content" data-testid="admin-users-tab">
      <h2>Utilisateurs</h2>
      <div className="search-row">
        <input
          placeholder="Rechercher par email…"
          value={search}
          onChange={(e) => { setSearch(e.target.value); load(e.target.value); }}
          data-testid="user-search-input"
        />
      </div>
      <table className="admin-table">
        <thead>
          <tr><th>Email</th><th>Nom</th><th>Rôle</th><th>Crédits</th><th>Requêtes</th><th>Dernière connexion</th><th>Statut</th><th>Actions</th></tr>
        </thead>
        <tbody>
          {users.map((u) => (
            <tr key={u.id} data-testid={`user-row-${u.email}`}>
              <td>{u.email}</td>
              <td>{u.display_name || '—'}</td>
              <td><span className={`role-badge role-${u.role}`}>{u.role}</span></td>
              <td>{u.credits}</td>
              <td>{u.request_count}</td>
              <td>{u.last_login_at ? new Date(u.last_login_at).toLocaleDateString('fr-CA') : '—'}</td>
              <td>{u.is_active ? <span className="status-ok">Actif</span> : <span className="status-off">Désactivé</span>}</td>
              <td className="actions-cell">
                <button className="mini-btn" onClick={() => adjust(u)} data-testid={`adjust-credits-${u.email}`}>± Crédits</button>
                <button className="mini-btn" onClick={() => toggleActive(u)} data-testid={`toggle-active-${u.email}`}>{u.is_active ? 'Désactiver' : 'Activer'}</button>
                <button className="mini-btn" onClick={() => toggleRole(u)} data-testid={`toggle-role-${u.email}`}>{u.role === 'admin' ? 'Rétrograder' : 'Promouvoir'}</button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ===================== Pricing tab ===================== */
function PricingTab({ showToast }) {
  const [packs, setPacks] = useState([]);
  const [cost, setCost] = useState({ standard: 10, vision: 15 });

  const load = useCallback(async () => {
    const s = await adminApi.getSettings();
    setPacks(s.credit_packs || []);
    setCost(s.request_cost || { standard: 10, vision: 15 });
  }, []);
  useEffect(() => { load(); }, [load]);

  const updatePack = (idx, field, value) => {
    setPacks((prev) => prev.map((p, i) => i === idx ? { ...p, [field]: field === 'name' ? value : Number(value) } : p));
  };

  const savePacks = async () => {
    try { await adminApi.updateSetting('credit_packs', packs); showToast('Packs enregistrés', 'success'); }
    catch (err) { showToast(err.message, 'error'); }
  };
  const saveCost = async () => {
    try { await adminApi.updateSetting('request_cost', { standard: Number(cost.standard), vision: Number(cost.vision) }); showToast('Coûts enregistrés', 'success'); }
    catch (err) { showToast(err.message, 'error'); }
  };

  return (
    <div className="tab-content" data-testid="admin-pricing-tab">
      <h2>Tarification</h2>
      <h3>Packs de crédits</h3>
      <table className="admin-table">
        <thead><tr><th>ID</th><th>Nom</th><th>Prix (CAD)</th><th>Crédits</th></tr></thead>
        <tbody>
          {packs.map((p, i) => (
            <tr key={p.id}>
              <td className="mono">{p.id}</td>
              <td><input value={p.name} onChange={(e) => updatePack(i, 'name', e.target.value)} data-testid={`pack-name-${p.id}`} /></td>
              <td><input type="number" value={p.price_cad} onChange={(e) => updatePack(i, 'price_cad', e.target.value)} data-testid={`pack-price-${p.id}`} /></td>
              <td><input type="number" value={p.credits} onChange={(e) => updatePack(i, 'credits', e.target.value)} data-testid={`pack-credits-${p.id}`} /></td>
            </tr>
          ))}
        </tbody>
      </table>
      <button className="save-btn" onClick={savePacks} data-testid="save-packs-button">Enregistrer les packs</button>

      <h3 style={{ marginTop: 32 }}>Coût par requête</h3>
      <div className="cost-row">
        <label>Standard <input type="number" value={cost.standard} onChange={(e) => setCost({ ...cost, standard: e.target.value })} data-testid="cost-standard-input" /></label>
        <label>Vision (images) <input type="number" value={cost.vision} onChange={(e) => setCost({ ...cost, vision: e.target.value })} data-testid="cost-vision-input" /></label>
      </div>
      <button className="save-btn" onClick={saveCost} data-testid="save-cost-button">Enregistrer les coûts</button>
    </div>
  );
}

/* ===================== Stats tab ===================== */
function StatsTab() {
  const [stats, setStats] = useState(null);
  useEffect(() => { adminApi.stats().then(setStats); }, []);
  if (!stats) return <div className="tab-content">Chargement…</div>;
  const cards = [
    { label: 'Revenus totaux', value: `${stats.total_revenue_cad} CAD` },
    { label: 'Crédits achetés', value: stats.credits_purchased },
    { label: 'Crédits consommés', value: stats.credits_consumed },
    { label: 'Utilisateurs actifs', value: stats.active_users },
    { label: 'Requêtes (7j)', value: stats.requests_7d },
    { label: 'Requêtes (30j)', value: stats.requests_30d },
  ];
  return (
    <div className="tab-content" data-testid="admin-stats-tab">
      <h2>Statistiques</h2>
      <div className="stats-grid">
        {cards.map((c) => (
          <div className="stat-card" key={c.label} data-testid={`stat-${c.label}`}>
            <div className="stat-value">{c.value}</div>
            <div className="stat-label">{c.label}</div>
          </div>
        ))}
      </div>
      <h3>50 dernières transactions</h3>
      <table className="admin-table">
        <thead><tr><th>Date</th><th>Utilisateur</th><th>Type</th><th>Montant</th><th>Solde</th></tr></thead>
        <tbody>
          {stats.recent_transactions.map((t) => (
            <tr key={t.id}>
              <td>{new Date(t.created_at).toLocaleString('fr-CA')}</td>
              <td>{t.email || '—'}</td>
              <td>{t.kind}</td>
              <td className={t.amount >= 0 ? 'amt-pos' : 'amt-neg'}>{t.amount >= 0 ? '+' : ''}{t.amount}</td>
              <td>{t.balance_after}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/* ===================== OpenRouter tab ===================== */
function fmtUsd(v) {
  if (v === null || v === undefined) return '—';
  const n = Number(v);
  if (Number.isNaN(n)) return '—';
  if (n === 0) return '$0.00';
  if (n < 0.01) return `$${n.toFixed(6)}`;
  return `$${n.toFixed(4)}`;
}

function OpenRouterTab({ showToast }) {
  const [status, setStatus] = useState(null);
  const [cost, setCost] = useState(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async (refresh = false) => {
    try {
      const [s, c] = await Promise.all([
        adminApi.openrouterKeyStatus(refresh),
        adminApi.openrouterCostSummary(),
      ]);
      setStatus(s);
      setCost(c);
    } catch (err) {
      showToast(err.message || 'Failed to load OpenRouter status', 'error');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, [showToast]);

  useEffect(() => { load(false); }, [load]);

  const onRefresh = () => { setRefreshing(true); load(true); };

  if (loading) return <div className="tab-content" data-testid="admin-openrouter-tab">Chargement…</div>;

  const notConfigured = status && status.configured === false;
  const invalid = status && status.configured && status.valid === false;
  const valid = status && status.valid === true;

  const keyCards = valid ? [
    { label: 'Key usage (spent)', value: fmtUsd(status.usage), testid: 'or-usage' },
    { label: 'Key limit', value: status.limit === null || status.limit === undefined ? 'Unlimited' : fmtUsd(status.limit), testid: 'or-limit' },
    { label: 'Remaining on key', value: status.limit_remaining === null || status.limit_remaining === undefined ? '—' : fmtUsd(status.limit_remaining), testid: 'or-remaining' },
    { label: 'Free tier?', value: status.is_free_tier ? 'Yes' : 'No', testid: 'or-free-tier' },
  ] : [];

  const costCards = cost ? [
    { label: 'Total cost (this app)', value: fmtUsd(cost.total_cost), testid: 'cost-total' },
    { label: 'Last council run', value: cost.last_run ? fmtUsd(cost.last_run.total_cost) : '—', testid: 'cost-last-run' },
    { label: 'Council runs recorded', value: cost.total_runs ?? 0, testid: 'cost-runs' },
  ] : [];

  return (
    <div className="tab-content" data-testid="admin-openrouter-tab">
      <div className="or-header">
        <h2>OpenRouter — Clé & coûts</h2>
        <button className="mini-btn" onClick={onRefresh} disabled={refreshing} data-testid="or-refresh-button">
          {refreshing ? 'Refreshing…' : '↻ Refresh'}
        </button>
      </div>

      <h3>Statut de la clé configurée</h3>
      {notConfigured && (
        <div className="or-empty" data-testid="or-not-configured">
          Aucune clé OpenRouter configurée. Ajoutez-en une dans <strong>Settings → API Settings</strong>.
        </div>
      )}
      {invalid && (
        <div className="or-empty or-invalid" data-testid="or-invalid">
          La clé configurée est invalide ou révoquée ({status.error || 'invalid_key'}). Mettez-la à jour dans Settings.
        </div>
      )}
      {valid && (
        <>
          <div className="stats-grid">
            {keyCards.map((c) => (
              <div className="stat-card" key={c.label} data-testid={`stat-${c.testid}`}>
                <div className="stat-value">{c.value}</div>
                <div className="stat-label">{c.label}</div>
              </div>
            ))}
          </div>
          {status.limit !== null && status.limit !== undefined && status.usage_percent !== null && status.usage_percent !== undefined && (
            <div className="or-usage-bar-wrap" data-testid="or-usage-bar">
              <div className="or-usage-bar-track">
                <div
                  className="or-usage-bar-fill"
                  style={{ width: `${Math.min(100, status.usage_percent)}%` }}
                />
              </div>
              <span className="or-usage-bar-label">{status.usage_percent}% utilisé</span>
            </div>
          )}
        </>
      )}

      <h3 style={{ marginTop: 28 }}>Coûts de l'application (usage accounting réel)</h3>
      <div className="stats-grid">
        {costCards.map((c) => (
          <div className="stat-card" key={c.label} data-testid={`stat-${c.testid}`}>
            <div className="stat-value">{c.value}</div>
            <div className="stat-label">{c.label}</div>
          </div>
        ))}
      </div>

      <h3 style={{ marginTop: 24 }}>Coût par modèle</h3>
      {cost && cost.per_model && cost.per_model.length > 0 ? (
        <table className="admin-table" data-testid="or-cost-per-model">
          <thead><tr><th>Modèle</th><th>Coût total</th><th>Tokens</th></tr></thead>
          <tbody>
            {cost.per_model.map((m) => (
              <tr key={m.model} data-testid={`or-model-row-${m.model}`}>
                <td className="mono">{m.model}</td>
                <td>{fmtUsd(m.cost)}</td>
                <td>{m.tokens?.toLocaleString?.() ?? m.tokens}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <div className="or-empty" data-testid="or-no-cost">
          Aucun coût enregistré pour l'instant. Les coûts apparaissent après chaque débat du council.
        </div>
      )}
    </div>
  );
}

/* ===================== Shell ===================== */
export default function Admin() {
  const [tab, setTab] = useState('models');
  const [toast, showToast] = useToast();
  const tabs = [
    { id: 'models', label: 'Modèles' },
    { id: 'users', label: 'Utilisateurs' },
    { id: 'pricing', label: 'Tarification' },
    { id: 'openrouter', label: 'OpenRouter' },
    { id: 'stats', label: 'Statistiques' },
  ];
  return (
    <div className="page-shell">
      <AppHeader />
      <main className="admin-main" data-testid="admin-page">
        <div className="admin-tabs">
          {tabs.map((t) => (
            <button
              key={t.id}
              className={`admin-tab ${tab === t.id ? 'active' : ''}`}
              onClick={() => setTab(t.id)}
              data-testid={`admin-tab-${t.id}`}
            >{t.label}</button>
          ))}
        </div>
        {tab === 'models' && <ModelsTab showToast={showToast} />}
        {tab === 'users' && <UsersTab showToast={showToast} />}
        {tab === 'pricing' && <PricingTab showToast={showToast} />}
        {tab === 'openrouter' && <OpenRouterTab showToast={showToast} />}
        {tab === 'stats' && <StatsTab />}
      </main>
      {toast && <div className={`toast toast-${toast.type}`} data-testid="toast-notification">{toast.message}</div>}
    </div>
  );
}
