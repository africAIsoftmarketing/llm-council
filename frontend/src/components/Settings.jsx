import { useState, useEffect, useCallback, useRef } from 'react';
import { api } from '../api';
import './Settings.css';

/* ─── provider colour map ─────────────────────────────────────── */
const PROVIDER_META = {
  OpenAI:   { color: '#10a37f', bg: '#f0fdf8', icon: '⬡' },
  Anthropic:{ color: '#c96442', bg: '#fff7f4', icon: '◈' },
  Google:   { color: '#4285f4', bg: '#f0f6ff', icon: '◉' },
  xAI:      { color: '#1a1a2e', bg: '#f5f5ff', icon: '✦' },
  Meta:     { color: '#0080fb', bg: '#f0f7ff', icon: '▣' },
  Mistral:  { color: '#7c4dff', bg: '#f7f3ff', icon: '◆' },
  Cohere:   { color: '#39c5bb', bg: '#f0fffe', icon: '◎' },
  DeepSeek: { color: '#e66000', bg: '#fff8f0', icon: '◐' },
};
const providerMeta = (p) => PROVIDER_META[p] || { color: '#4a90e2', bg: '#f5f8ff', icon: '◇' };

export default function Settings({ onConfigUpdate, showToast }) {
  const [activeTab, setActiveTab] = useState('api');
  const [config, setConfig] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  // Form states
  const [apiKey, setApiKey] = useState('');
  const [isValidatingKey, setIsValidatingKey] = useState(false);
  const [keyValidation, setKeyValidation] = useState(null);
  const [selectedModels, setSelectedModels] = useState([]);
  const [chairmanModel, setChairmanModel] = useState('');
  const [customModel, setCustomModel] = useState({ id: '', name: '', provider: '' });
  const [theme, setTheme] = useState('light');

  // Model picker states
  const [modelSearch, setModelSearch] = useState('');
  const [activeProvider, setActiveProvider] = useState('All');
  const [dragIdx, setDragIdx] = useState(null);
  const [dragOverIdx, setDragOverIdx] = useState(null);
  const dragNode = useRef(null);

  const loadConfiguration = useCallback(async () => {
    try {
      setIsLoading(true);
      const cfg = await api.getConfig();
      setConfig(cfg);
      setSelectedModels(cfg.council_models || []);
      setChairmanModel(cfg.chairman_model || '');
      setTheme(cfg.theme || 'light');
    } catch {
      showToast('Failed to load configuration', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [showToast]);

  const loadAvailableModels = useCallback(async () => {
    try {
      const result = await api.getAvailableModels();
      setAvailableModels(result.models || []);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    loadConfiguration();
    loadAvailableModels();
  }, [loadConfiguration, loadAvailableModels]);

  /* ── API key handlers ── */
  const handleValidateKey = async () => {
    if (!apiKey.trim()) { showToast('Please enter an API key', 'warning'); return; }
    setIsValidatingKey(true);
    setKeyValidation(null);
    try {
      const result = await api.validateApiKey(apiKey);
      setKeyValidation(result);
      showToast(result.valid ? 'API key is valid!' : result.error || 'Invalid API key',
        result.valid ? 'success' : 'error');
    } catch { showToast('Failed to validate API key', 'error'); }
    finally { setIsValidatingKey(false); }
  };

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) { showToast('Please enter an API key', 'warning'); return; }
    setIsSaving(true);
    try {
      await api.updateConfig({ openrouter_api_key: apiKey });
      showToast('API key saved successfully!', 'success');
      setApiKey('');
      await loadConfiguration();
      onConfigUpdate();
    } catch { showToast('Failed to save API key', 'error'); }
    finally { setIsSaving(false); }
  };

  /* ── Model selection ── */
  const handleToggleModel = (modelId) => {
    setSelectedModels(prev =>
      prev.includes(modelId) ? prev.filter(id => id !== modelId) : [...prev, modelId]
    );
  };

  const handleRemoveModel = (modelId) => {
    setSelectedModels(prev => prev.filter(id => id !== modelId));
    if (chairmanModel === modelId) setChairmanModel('');
  };

  const handleSaveModels = async () => {
    if (selectedModels.length === 0) {
      showToast('Please select at least one council model', 'warning'); return;
    }
    setIsSaving(true);
    try {
      const chairman = chairmanModel || selectedModels[0];
      const updated = await api.updateConfig({ council_models: selectedModels, chairman_model: chairman });
      setSelectedModels(updated.council_models || selectedModels);
      setChairmanModel(updated.chairman_model || chairman);
      setConfig(updated);
      showToast('Council saved!', 'success');
      onConfigUpdate();
    } catch { showToast('Failed to save model configuration', 'error'); }
    finally { setIsSaving(false); }
  };

  /* ── Drag-to-reorder ── */
  const handleDragStart = (e, idx) => {
    dragNode.current = e.target;
    setDragIdx(idx);
    e.dataTransfer.effectAllowed = 'move';
  };
  const handleDragEnter = (idx) => { if (dragIdx !== idx) setDragOverIdx(idx); };
  const handleDragEnd = () => {
    if (dragIdx !== null && dragOverIdx !== null && dragIdx !== dragOverIdx) {
      setSelectedModels(prev => {
        const arr = [...prev];
        const [moved] = arr.splice(dragIdx, 1);
        arr.splice(dragOverIdx, 0, moved);
        return arr;
      });
    }
    setDragIdx(null);
    setDragOverIdx(null);
  };

  /* ── Custom model ── */
  const handleAddCustomModel = async () => {
    if (!customModel.id || !customModel.name || !customModel.provider) {
      showToast('Please fill in all custom model fields', 'warning'); return;
    }
    try {
      await api.addCustomModel(customModel.id, customModel.name, customModel.provider);
      showToast('Custom model added!', 'success');
      setCustomModel({ id: '', name: '', provider: '' });
      await loadAvailableModels();
    } catch { showToast('Failed to add custom model', 'error'); }
  };

  /* ── Theme ── */
  const handleSaveTheme = async () => {
    setIsSaving(true);
    try {
      await api.updateConfig({ theme });
      showToast('Theme saved!', 'success');
    } catch { showToast('Failed to save theme', 'error'); }
    finally { setIsSaving(false); }
  };

  /* ── Derived data ── */
  const providers = ['All', ...Array.from(new Set(availableModels.map(m => m.provider)))];

  const filteredModels = availableModels.filter(m => {
    const matchProvider = activeProvider === 'All' || m.provider === activeProvider;
    const q = modelSearch.toLowerCase();
    const matchSearch = !q || m.name.toLowerCase().includes(q) || m.id.toLowerCase().includes(q);
    return matchProvider && matchSearch;
  });

  const modelById = Object.fromEntries(availableModels.map(m => [m.id, m]));

  if (isLoading) {
    return (
      <div className="settings">
        <div className="settings-loading">
          <div className="spinner" />
          <span>Loading configuration...</span>
        </div>
      </div>
    );
  }

  return (
    <div className="settings" data-testid="settings-page">
      <div className="settings-header">
        <h1>Settings</h1>
        <p>Configure your LLM Council preferences</p>
      </div>

      <div className="settings-tabs">
        {[['api','API Settings'],['models','Council Models'],['chairman','Chairman'],['advanced','Advanced']].map(([id, label]) => (
          <button key={id} className={`settings-tab ${activeTab === id ? 'active' : ''}`}
            onClick={() => setActiveTab(id)} data-testid={`tab-${id}`}>{label}</button>
        ))}
      </div>

      <div className="settings-content">

        {/* ── API Settings ── */}
        {activeTab === 'api' && (
          <div className="settings-section" data-testid="section-api">
            <h2>OpenRouter API Key</h2>
            <p className="settings-description">
              Get your API key from{' '}
              <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer">openrouter.ai/keys</a>.
              Make sure you have credits available.
            </p>
            {config?.has_api_key && (
              <div className="current-key-status">
                <span className="status-badge success">API Key Configured</span>
                <span className="masked-key">{config.openrouter_api_key_masked}</span>
              </div>
            )}
            <div className="form-group">
              <label htmlFor="apiKey">New API Key</label>
              <div className="input-with-button">
                <input type="password" id="apiKey" value={apiKey}
                  onChange={e => setApiKey(e.target.value)} placeholder="sk-or-v1-..."
                  data-testid="input-api-key" />
                <button onClick={handleValidateKey} disabled={isValidatingKey || !apiKey.trim()}
                  className="btn-secondary" data-testid="btn-validate-key">
                  {isValidatingKey ? 'Validating…' : 'Validate'}
                </button>
              </div>
            </div>
            {keyValidation && (
              <div className={`validation-result ${keyValidation.valid ? 'valid' : 'invalid'}`}>
                <span className="validation-icon">{keyValidation.valid ? '✓' : '✗'}</span>
                <span>{keyValidation.valid ? 'API key is valid' : keyValidation.error}</span>
                {keyValidation.valid && keyValidation.data?.label && (
                  <span className="key-label">({keyValidation.data.label})</span>
                )}
              </div>
            )}
            <button onClick={handleSaveApiKey} disabled={isSaving || !apiKey.trim()}
              className="btn-primary" data-testid="btn-save-api-key">
              {isSaving ? 'Saving…' : 'Save API Key'}
            </button>
          </div>
        )}

        {/* ── Council Models ── */}
        {activeTab === 'models' && (
          <div className="settings-section models-section" data-testid="section-models">
            <div className="models-header">
              <div>
                <h2>Council Models</h2>
                <p className="settings-description" style={{ marginBottom: 0 }}>
                  Pick models from the browser, then drag to set deliberation order.
                </p>
              </div>
              <button onClick={handleSaveModels}
                disabled={isSaving || selectedModels.length === 0}
                className="btn-primary" data-testid="btn-save-models">
                {isSaving ? 'Saving…' : 'Save Council'}
              </button>
            </div>

            <div className="picker-layout">
              {/* ── Left: model browser ── */}
              <div className="picker-left">
                <div className="picker-search-row">
                  <div className="picker-search-wrap">
                    <span className="picker-search-icon">⌕</span>
                    <input className="picker-search" type="text"
                      placeholder="Search models…" value={modelSearch}
                      onChange={e => setModelSearch(e.target.value)} />
                    {modelSearch && (
                      <button className="picker-search-clear"
                        onClick={() => setModelSearch('')}>✕</button>
                    )}
                  </div>
                </div>

                <div className="picker-provider-tabs">
                  {providers.map(p => (
                    <button key={p}
                      className={`picker-provider-tab ${activeProvider === p ? 'active' : ''}`}
                      style={activeProvider === p && p !== 'All'
                        ? { borderBottomColor: providerMeta(p).color, color: providerMeta(p).color }
                        : {}}
                      onClick={() => setActiveProvider(p)}>
                      {p !== 'All' && (
                        <span className="ptab-icon">{providerMeta(p).icon}</span>
                      )}
                      {p}
                    </button>
                  ))}
                </div>

                <div className="picker-model-list">
                  {filteredModels.length === 0 && (
                    <div className="picker-empty">No models match your search.</div>
                  )}
                  {filteredModels.map(model => {
                    const meta = providerMeta(model.provider);
                    const isSelected = selectedModels.includes(model.id);
                    return (
                      <div key={model.id}
                        className={`picker-model-card ${isSelected ? 'selected' : ''}`}
                        style={isSelected
                          ? { borderColor: meta.color, background: meta.bg }
                          : {}}
                        onClick={() => handleToggleModel(model.id)}
                        data-testid={`model-${model.id}`}>
                        <div className="pmc-icon" style={{ color: meta.color }}>{meta.icon}</div>
                        <div className="pmc-body">
                          <span className="pmc-name">{model.name}</span>
                          <span className="pmc-id">{model.id}</span>
                        </div>
                        <div className={`pmc-check ${isSelected ? 'checked' : ''}`}
                          style={isSelected ? { background: meta.color } : {}}>
                          {isSelected && '✓'}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>

              {/* ── Right: your council ── */}
              <div className="picker-right">
                <div className="council-header">
                  <span className="council-title">Your Council</span>
                  <span className="council-count">
                    {selectedModels.length} model{selectedModels.length !== 1 ? 's' : ''}
                  </span>
                </div>

                {selectedModels.length === 0 ? (
                  <div className="council-empty">
                    <div className="council-empty-icon">⬡</div>
                    <p>Click models on the left to add them to your council</p>
                  </div>
                ) : (
                  <div className="council-list">
                    {selectedModels.map((modelId, idx) => {
                      const model = modelById[modelId];
                      const meta = providerMeta(model?.provider || '');
                      const isDragging = dragIdx === idx;
                      const isDragOver = dragOverIdx === idx;
                      return (
                        <div key={modelId}
                          className={`council-item ${isDragging ? 'dragging' : ''} ${isDragOver ? 'drag-over' : ''}`}
                          draggable
                          onDragStart={e => handleDragStart(e, idx)}
                          onDragEnter={() => handleDragEnter(idx)}
                          onDragOver={e => e.preventDefault()}
                          onDragEnd={handleDragEnd}>
                          <div className="ci-drag">⠿</div>
                          <div className="ci-rank" style={{ background: meta.color }}>
                            {idx + 1}
                          </div>
                          <div className="ci-body">
                            <span className="ci-name">{model?.name || modelId}</span>
                            <span className="ci-provider">{model?.provider || ''}</span>
                          </div>
                          <button className="ci-remove"
                            onClick={() => handleRemoveModel(modelId)}
                            title="Remove from council">✕</button>
                        </div>
                      );
                    })}
                  </div>
                )}

                {selectedModels.length > 0 && (
                  <div className="council-chairman-pick">
                    <label className="cc-label">
                      <span>👑</span> Chairman (synthesizes final answer)
                    </label>
                    <select className="cc-select" value={chairmanModel}
                      onChange={e => setChairmanModel(e.target.value)}>
                      <option value="">— auto (first model) —</option>
                      {selectedModels.map(id => {
                        const m = modelById[id];
                        return (
                          <option key={id} value={id}>{m?.name || id}</option>
                        );
                      })}
                    </select>
                  </div>
                )}
              </div>
            </div>

            {/* Custom model row */}
            <div className="custom-model-section">
              <h3>Add Custom Model</h3>
              <div className="custom-model-form">
                <input type="text" placeholder="Model ID (e.g., provider/model-name)"
                  value={customModel.id}
                  onChange={e => setCustomModel({ ...customModel, id: e.target.value })} />
                <input type="text" placeholder="Display Name"
                  value={customModel.name}
                  onChange={e => setCustomModel({ ...customModel, name: e.target.value })} />
                <input type="text" placeholder="Provider"
                  value={customModel.provider}
                  onChange={e => setCustomModel({ ...customModel, provider: e.target.value })} />
                <button onClick={handleAddCustomModel} className="btn-secondary">
                  Add Model
                </button>
              </div>
            </div>
          </div>
        )}

        {/* ── Chairman ── */}
        {activeTab === 'chairman' && (
          <div className="settings-section" data-testid="section-chairman">
            <h2>Chairman Model</h2>
            <p className="settings-description">
              The Chairman synthesizes the final response from all council members.
              Choose a model that excels at summarisation and analysis.
            </p>
            {config?.chairman_model && (
              <div className="current-chairman">
                <span>Current Chairman:</span>
                <strong>{config.chairman_model}</strong>
              </div>
            )}
            <div className="form-group">
              <label htmlFor="chairmanSelect">Select Chairman Model</label>
              <select id="chairmanSelect" value={chairmanModel}
                onChange={e => setChairmanModel(e.target.value)}
                data-testid="select-chairman">
                <option value="">— Select a model —</option>
                {availableModels.map(model => (
                  <option key={model.id} value={model.id}>
                    {model.name} ({model.provider})
                  </option>
                ))}
              </select>
            </div>
            <div className="chairman-tips">
              <h4>Tips for choosing a Chairman:</h4>
              <ul>
                <li>Consider a model with strong reasoning capabilities</li>
                <li>The chairman should excel at synthesising multiple viewpoints</li>
                <li>Larger models often produce better summaries</li>
                <li>The chairman can be one of the council members</li>
              </ul>
            </div>
            <button onClick={handleSaveModels} disabled={isSaving || !chairmanModel}
              className="btn-primary" data-testid="btn-save-chairman">
              {isSaving ? 'Saving…' : 'Save Chairman Selection'}
            </button>
          </div>
        )}

        {/* ── Advanced ── */}
        {activeTab === 'advanced' && (
          <div className="settings-section" data-testid="section-advanced">
            <h2>Advanced Settings</h2>
            <div className="form-group">
              <label>Theme</label>
              <div className="theme-options">
                {['light', 'dark'].map(t => (
                  <label key={t} className="theme-option">
                    <input type="radio" name="theme" value={t}
                      checked={theme === t} onChange={e => setTheme(e.target.value)} />
                    <span style={{ textTransform: 'capitalize' }}>{t}</span>
                  </label>
                ))}
              </div>
            </div>
            <div className="info-section">
              <h3>Storage Location</h3>
              <p>Conversations: <code>data/conversations/</code></p>
              <p>Documents: <code>data/documents/</code></p>
            </div>
            <div className="info-section">
              <h3>About LLM Council</h3>
              <p>
                A 3-stage deliberation system: individual responses &rarr; peer review &rarr; chairman synthesis.
              </p>
              <p>Version: 2.0.0</p>
            </div>
            <button onClick={handleSaveTheme} disabled={isSaving} className="btn-primary">
              {isSaving ? 'Saving…' : 'Save Settings'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
