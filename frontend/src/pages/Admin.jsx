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

/* ===================== Shell ===================== */
export default function Admin() {
  const [tab, setTab] = useState('models');
  const [toast, showToast] = useToast();
  const tabs = [
    { id: 'models', label: 'Modèles' },
    { id: 'users', label: 'Utilisateurs' },
    { id: 'pricing', label: 'Tarification' },
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
        {tab === 'stats' && <StatsTab />}
      </main>
      {toast && <div className={`toast toast-${toast.type}`} data-testid="toast-notification">{toast.message}</div>}
    </div>
  );
}
