import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
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

export default function Settings({ isAdmin = false, onConfigUpdate, showToast }) {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState(isAdmin ? 'api' : 'models');
  const [config, setConfig] = useState(null);
  const [availableModels, setAvailableModels] = useState([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);

  const [apiKey, setApiKey] = useState('');
  const [isValidatingKey, setIsValidatingKey] = useState(false);
  const [keyValidation, setKeyValidation] = useState(null);
  const [selectedModels, setSelectedModels] = useState([]);
  const [chairmanModel, setChairmanModel] = useState('');
  const [customModel, setCustomModel] = useState({ id: '', name: '', provider: '' });
  const [theme, setTheme] = useState('light');
  const [isCustomCouncil, setIsCustomCouncil] = useState(false);

  const [modelSearch, setModelSearch] = useState('');
  const [activeProvider, setActiveProvider] = useState('All');
  const [dragIdx, setDragIdx] = useState(null);
  const [dragOverIdx, setDragOverIdx] = useState(null);
  const [editingId, setEditingId] = useState(null);
  const [editValue, setEditValue] = useState('');
  const [catEditingId, setCatEditingId] = useState(null);
  const [catEditId, setCatEditId] = useState('');
  const [catEditName, setCatEditName] = useState('');
  const [catEditProvider, setCatEditProvider] = useState('');
  const dragNode = useRef(null);

  const loadConfiguration = useCallback(async () => {
    try {
      setIsLoading(true);
      const cfg = await api.getConfig();
      setConfig(cfg);
      setTheme(cfg.theme || 'light');
      if (isAdmin) {
        setSelectedModels(cfg.council_models || []);
        setChairmanModel(cfg.chairman_model || '');
      } else {
        const uc = await api.getUserCouncil();
        setSelectedModels(uc.council_models || []);
        setChairmanModel(uc.chairman_model || '');
        setIsCustomCouncil(!!uc.is_custom);
      }
    } catch {
      showToast(t('settings.loadFailed'), 'error');
    } finally {
      setIsLoading(false);
    }
  }, [showToast, isAdmin, t]);

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

  const handleValidateKey = async () => {
    if (!apiKey.trim()) { showToast(t('settings.enterKey'), 'warning'); return; }
    setIsValidatingKey(true);
    setKeyValidation(null);
    try {
      const result = await api.validateApiKey(apiKey);
      setKeyValidation(result);
      showToast(result.valid ? t('settings.keyValidExcl') : result.error || t('settings.validateFailed'),
        result.valid ? 'success' : 'error');
    } catch { showToast(t('settings.validateFailed'), 'error'); }
    finally { setIsValidatingKey(false); }
  };

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) { showToast(t('settings.enterKey'), 'warning'); return; }
    setIsSaving(true);
    try {
      await api.updateConfig({ openrouter_api_key: apiKey });
      showToast(t('settings.keySaved'), 'success');
      setApiKey('');
      await loadConfiguration();
      onConfigUpdate();
    } catch { showToast(t('settings.saveKeyFailed'), 'error'); }
    finally { setIsSaving(false); }
  };

  const handleToggleModel = (modelId) => {
    setSelectedModels(prev =>
      prev.includes(modelId) ? prev.filter(id => id !== modelId) : [...prev, modelId]
    );
  };

  const handleRemoveModel = (modelId) => {
    setSelectedModels(prev => prev.filter(id => id !== modelId));
    if (chairmanModel === modelId) setChairmanModel('');
    if (editingId === modelId) { setEditingId(null); setEditValue(''); }
  };

  const startEditModel = (modelId) => { setEditingId(modelId); setEditValue(modelId); };
  const cancelEditModel = () => { setEditingId(null); setEditValue(''); };
  const confirmEditModel = (oldId) => {
    const newId = editValue.trim();
    if (!newId) { showToast(t('settings.idEmpty'), 'warning'); return; }
    if (newId === oldId) { cancelEditModel(); return; }
    if (selectedModels.includes(newId)) { showToast(t('settings.alreadyInCouncil'), 'warning'); return; }
    setSelectedModels(prev => prev.map(id => (id === oldId ? newId : id)));
    if (chairmanModel === oldId) setChairmanModel(newId);
    setEditingId(null);
    setEditValue('');
    showToast(t('settings.idChanged'), 'info');
  };

  const startCatEdit = (e, model) => {
    e.stopPropagation();
    setCatEditingId(model.id);
    setCatEditId(model.id);
    setCatEditName(model.name || '');
    setCatEditProvider(model.provider || '');
  };
  const cancelCatEdit = (e) => { if (e) e.stopPropagation(); setCatEditingId(null); };
  const saveCatEdit = async (e, oldId) => {
    e.stopPropagation();
    const newId = catEditId.trim();
    if (!newId) { showToast(t('settings.idEmpty'), 'warning'); return; }
    try {
      await api.updateCatalogModel(oldId, {
        new_id: newId,
        model_name: catEditName.trim() || undefined,
        provider: catEditProvider.trim() || undefined,
      });
      setCatEditingId(null);
      await loadAvailableModels();
      await loadConfiguration();
      showToast(t('settings.catUpdated'), 'success');
    } catch (err) {
      showToast(err.message || t('settings.catUpdateFailed'), 'error');
    }
  };
  const deleteCatModel = async (e, model) => {
    e.stopPropagation();
    if (!window.confirm(t('settings.deleteCatConfirm', { name: model.name || model.id }))) return;
    try {
      await api.deleteCatalogModel(model.id);
      await loadAvailableModels();
      await loadConfiguration();
      showToast(t('settings.catDeleted'), 'success');
    } catch (err) {
      showToast(err.message || t('settings.catDeleteFailed'), 'error');
    }
  };

  const handleSaveModels = async () => {
    if (selectedModels.length < 2) {
      showToast(t('settings.minTwo'), 'warning'); return;
    }
    setIsSaving(true);
    try {
      const chairman = chairmanModel || selectedModels[0];
      if (isAdmin) {
        const updated = await api.updateConfig({ council_models: selectedModels, chairman_model: chairman });
        setSelectedModels(updated.council_models || selectedModels);
        setChairmanModel(updated.chairman_model || chairman);
        setConfig(updated);
      } else {
        const updated = await api.updateUserCouncil(selectedModels, chairman);
        setSelectedModels(updated.council_models || selectedModels);
        setChairmanModel(updated.chairman_model || chairman);
        setIsCustomCouncil(true);
      }
      showToast(t('settings.councilSaved'), 'success');
      onConfigUpdate();
    } catch (err) { showToast(err.message || t('settings.saveFailed'), 'error'); }
    finally { setIsSaving(false); }
  };

  const handleResetCouncil = async () => {
    setIsSaving(true);
    try {
      const reset = await api.resetUserCouncil();
      setSelectedModels(reset.council_models || []);
      setChairmanModel(reset.chairman_model || '');
      setIsCustomCouncil(false);
      showToast(t('settings.councilReset'), 'success');
      onConfigUpdate();
    } catch (err) { showToast(err.message || t('settings.resetFailed'), 'error'); }
    finally { setIsSaving(false); }
  };

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

  const handleAddCustomModel = async () => {
    if (!customModel.id || !customModel.name || !customModel.provider) {
      showToast(t('settings.fillCustom'), 'warning'); return;
    }
    try {
      await api.addCustomModel(customModel.id, customModel.name, customModel.provider);
      showToast(t('settings.customAdded'), 'success');
      setCustomModel({ id: '', name: '', provider: '' });
      await loadAvailableModels();
    } catch { showToast(t('settings.customFailed'), 'error'); }
  };

  const handleSaveTheme = async () => {
    setIsSaving(true);
    try {
      await api.updateConfig({ theme });
      showToast(t('settings.themeSaved'), 'success');
    } catch { showToast(t('settings.themeSaveFailed'), 'error'); }
    finally { setIsSaving(false); }
  };

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
          <span>{t('settings.loading')}</span>
        </div>
      </div>
    );
  }

  return (
    <div className="settings" data-testid="settings-page">
      <div className="settings-header">
        <h1>{t('settings.title')}</h1>
        <p>{t('settings.subtitle')}</p>
      </div>

      <div className="settings-tabs">
        {[
          ...(isAdmin ? [['api', t('settings.apiTab')]] : []),
          ['models', t('settings.modelsTab')],
          ['chairman', t('settings.chairmanTab')],
          ['advanced', t('settings.advancedTab')],
        ].map(([id, label]) => (
          <button key={id} className={`settings-tab ${activeTab === id ? 'active' : ''}`}
            onClick={() => setActiveTab(id)} data-testid={`tab-${id}`}>{label}</button>
        ))}
      </div>

      <div className="settings-content">

        {activeTab === 'api' && isAdmin && (
          <div className="settings-section" data-testid="section-api">
            <h2>{t('settings.apiTitle')}</h2>
            <p className="settings-description">
              {t('settings.apiDescPre')}{' '}
              <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer">openrouter.ai/keys</a>{t('settings.apiDescPost')}
            </p>
            {config?.has_api_key && (
              <div className="current-key-status">
                <span className="status-badge success">{t('settings.keyConfigured')}</span>
                <span className="masked-key">{config.openrouter_api_key_masked}</span>
              </div>
            )}
            <div className="form-group">
              <label htmlFor="apiKey">{t('settings.newKey')}</label>
              <div className="input-with-button">
                <input type="password" id="apiKey" value={apiKey}
                  onChange={e => setApiKey(e.target.value)} placeholder="sk-or-v1-..."
                  data-testid="input-api-key" />
                <button onClick={handleValidateKey} disabled={isValidatingKey || !apiKey.trim()}
                  className="btn-secondary" data-testid="btn-validate-key">
                  {isValidatingKey ? t('settings.validating') : t('settings.validate')}
                </button>
              </div>
            </div>
            {keyValidation && (
              <div className={`validation-result ${keyValidation.valid ? 'valid' : 'invalid'}`}>
                <span className="validation-icon">{keyValidation.valid ? '✓' : '✗'}</span>
                <span>{keyValidation.valid ? t('settings.keyValid') : keyValidation.error}</span>
                {keyValidation.valid && keyValidation.data?.label && (
                  <span className="key-label">({keyValidation.data.label})</span>
                )}
              </div>
            )}
            <button onClick={handleSaveApiKey} disabled={isSaving || !apiKey.trim()}
              className="btn-primary" data-testid="btn-save-api-key">
              {isSaving ? t('settings.saving') : t('settings.saveKey')}
            </button>
          </div>
        )}

        {activeTab === 'models' && (
          <div className="settings-section models-section" data-testid="section-models">
            <div className="models-header">
              <div>
                <h2>{t('settings.councilTitle')}</h2>
                <p className="settings-description" style={{ marginBottom: 0 }}>
                  {t('settings.pickOrder')}
                </p>
              </div>
              <div className="models-header-actions" style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                {!isAdmin && isCustomCouncil && (
                  <button onClick={handleResetCouncil} disabled={isSaving}
                    className="btn-secondary" data-testid="btn-reset-council">
                    {t('settings.resetDefault')}
                  </button>
                )}
                <button onClick={handleSaveModels}
                  disabled={isSaving || selectedModels.length < 2}
                  className="btn-primary" data-testid="btn-save-models">
                  {isSaving ? t('settings.saving') : t('settings.saveCouncil')}
                </button>
              </div>
            </div>

            <div className="picker-layout">
              <div className="picker-left">
                <div className="picker-search-row">
                  <div className="picker-search-wrap">
                    <span className="picker-search-icon">⌕</span>
                    <input className="picker-search" type="text"
                      placeholder={t('settings.searchModels')} value={modelSearch}
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
                    <div className="picker-empty">{t('settings.noMatch')}</div>
                  )}
                  {filteredModels.map(model => {
                    const meta = providerMeta(model.provider);
                    const isSelected = selectedModels.includes(model.id);
                    const isEditing = catEditingId === model.id;
                    return (
                      <div key={model.id}
                        className={`picker-model-card ${isSelected ? 'selected' : ''} ${isEditing ? 'editing' : ''}`}
                        style={isSelected && !isEditing
                          ? { borderColor: meta.color, background: meta.bg }
                          : {}}
                        onClick={() => { if (!isEditing) handleToggleModel(model.id); }}
                        data-testid={`model-${model.id}`}>
                        <div className="pmc-icon" style={{ color: meta.color }}>{meta.icon}</div>
                        {isEditing ? (
                          <div className="pmc-edit" onClick={e => e.stopPropagation()}>
                            <input className="pmc-edit-input" value={catEditId}
                              onChange={e => setCatEditId(e.target.value)}
                              onKeyDown={e => { if (e.key === 'Enter') saveCatEdit(e, model.id); if (e.key === 'Escape') cancelCatEdit(e); }}
                              placeholder={t('settings.idPlaceholder')} autoFocus
                              data-testid="catalog-edit-id-input" />
                            <div className="pmc-edit-meta">
                              <input className="pmc-edit-input sm" value={catEditName}
                                onChange={e => setCatEditName(e.target.value)} placeholder={t('settings.name')}
                                data-testid="catalog-edit-name-input" />
                              <input className="pmc-edit-input sm" value={catEditProvider}
                                onChange={e => setCatEditProvider(e.target.value)} placeholder={t('settings.provider')}
                                data-testid="catalog-edit-provider-input" />
                            </div>
                            <div className="pmc-edit-actions">
                              <button className="pmc-save" onClick={e => saveCatEdit(e, model.id)}
                                data-testid={`catalog-save-${model.id}`}>{t('settings.save')}</button>
                              <button className="pmc-cancel" onClick={cancelCatEdit}
                                data-testid={`catalog-cancel-${model.id}`}>{t('settings.cancel')}</button>
                            </div>
                          </div>
                        ) : (
                          <>
                            <div className="pmc-body">
                              <span className="pmc-name">{model.name}</span>
                              <span className="pmc-id">{model.id}</span>
                            </div>
                            <div className="pmc-actions">
                              {isAdmin && (
                                <>
                                  <button className="pmc-edit-btn"
                                    onClick={e => startCatEdit(e, model)}
                                    title={t('settings.editIdTitle')}
                                    data-testid={`catalog-edit-btn-${model.id}`}>✎</button>
                                  <button className="pmc-delete-btn"
                                    onClick={e => deleteCatModel(e, model)}
                                    title={t('settings.deleteCatTitle')}
                                    data-testid={`catalog-delete-btn-${model.id}`}>🗑</button>
                                </>
                              )}
                            </div>
                            <div className={`pmc-check ${isSelected ? 'checked' : ''}`}
                              style={isSelected ? { background: meta.color } : {}}>
                              {isSelected && '✓'}
                            </div>
                          </>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>

              <div className="picker-right">
                <div className="council-header">
                  <span className="council-title">{t('settings.yourCouncil')}</span>
                  <span className="council-count">
                    {t('settings.modelsCount', { count: selectedModels.length })}
                  </span>
                </div>

                {selectedModels.length === 0 ? (
                  <div className="council-empty">
                    <div className="council-empty-icon">⬡</div>
                    <p>{t('settings.councilEmptyHint')}</p>
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
                          draggable={editingId !== modelId}
                          onDragStart={e => handleDragStart(e, idx)}
                          onDragEnter={() => handleDragEnter(idx)}
                          onDragOver={e => e.preventDefault()}
                          onDragEnd={handleDragEnd}>
                          <div className="ci-drag">⠿</div>
                          <div className="ci-rank" style={{ background: meta.color }}>
                            {idx + 1}
                          </div>
                          {editingId === modelId ? (
                            <div className="ci-edit" data-testid={`edit-model-${modelId}`}>
                              <input
                                className="ci-edit-input"
                                value={editValue}
                                onChange={e => setEditValue(e.target.value)}
                                onKeyDown={e => {
                                  if (e.key === 'Enter') confirmEditModel(modelId);
                                  if (e.key === 'Escape') cancelEditModel();
                                }}
                                placeholder={t('settings.idPlaceholder')}
                                autoFocus
                                data-testid="edit-model-input"
                              />
                              <button className="ci-edit-save" title={t('settings.saveIdTitle')}
                                onClick={() => confirmEditModel(modelId)}
                                data-testid={`confirm-edit-${modelId}`}>✓</button>
                              <button className="ci-edit-cancel" title={t('settings.cancelTitle')}
                                onClick={cancelEditModel}
                                data-testid={`cancel-edit-${modelId}`}>✕</button>
                            </div>
                          ) : (
                            <>
                              <div className="ci-body">
                                <span className="ci-name">{model?.name || modelId}</span>
                                <span className="ci-provider">{modelId}</span>
                              </div>
                              {isAdmin && (
                                <button className="ci-edit-btn"
                                  onClick={() => startEditModel(modelId)}
                                  title={t('settings.editIdTitle')}
                                  data-testid={`edit-model-btn-${modelId}`}>✎</button>
                              )}
                              <button className="ci-remove"
                                onClick={() => handleRemoveModel(modelId)}
                                title={t('settings.deleteModelTitle')}
                                data-testid={`remove-model-btn-${modelId}`}>🗑</button>
                            </>
                          )}
                        </div>
                      );
                    })}
                  </div>
                )}

                {selectedModels.length > 0 && (
                  <div className="council-chairman-pick">
                    <label className="cc-label">
                      <span>👑</span> {t('settings.chairmanPick')}
                    </label>
                    <select className="cc-select" value={chairmanModel}
                      onChange={e => setChairmanModel(e.target.value)}>
                      <option value="">{t('settings.autoFirst')}</option>
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

            {isAdmin && (
            <div className="custom-model-section">
              <h3>{t('settings.addCustom')}</h3>
              <div className="custom-model-form">
                <input type="text" placeholder={t('settings.modelId')}
                  value={customModel.id}
                  onChange={e => setCustomModel({ ...customModel, id: e.target.value })} />
                <input type="text" placeholder={t('settings.displayName')}
                  value={customModel.name}
                  onChange={e => setCustomModel({ ...customModel, name: e.target.value })} />
                <input type="text" placeholder={t('settings.provider')}
                  value={customModel.provider}
                  onChange={e => setCustomModel({ ...customModel, provider: e.target.value })} />
                <button onClick={handleAddCustomModel} className="btn-secondary">
                  {t('settings.addModel')}
                </button>
              </div>
            </div>
            )}
          </div>
        )}

        {activeTab === 'chairman' && (
          <div className="settings-section" data-testid="section-chairman">
            <h2>{t('settings.chairmanTitle')}</h2>
            <p className="settings-description">{t('settings.chairmanDesc')}</p>
            {config?.chairman_model && (
              <div className="current-chairman">
                <span>{t('settings.currentChairman')}</span>
                <strong>{config.chairman_model}</strong>
              </div>
            )}
            <div className="form-group">
              <label htmlFor="chairmanSelect">{t('settings.selectChairman')}</label>
              <select id="chairmanSelect" value={chairmanModel}
                onChange={e => setChairmanModel(e.target.value)}
                data-testid="select-chairman">
                <option value="">{t('settings.selectModel')}</option>
                {availableModels.map(model => (
                  <option key={model.id} value={model.id}>
                    {model.name} ({model.provider})
                  </option>
                ))}
              </select>
            </div>
            <div className="chairman-tips">
              <h4>{t('settings.tipsTitle')}</h4>
              <ul>
                <li>{t('settings.tip1')}</li>
                <li>{t('settings.tip2')}</li>
                <li>{t('settings.tip3')}</li>
                <li>{t('settings.tip4')}</li>
              </ul>
            </div>
            <button onClick={handleSaveModels} disabled={isSaving || !chairmanModel}
              className="btn-primary" data-testid="btn-save-chairman">
              {isSaving ? t('settings.saving') : t('settings.saveChairman')}
            </button>
          </div>
        )}

        {activeTab === 'advanced' && (
          <div className="settings-section" data-testid="section-advanced">
            <h2>{t('settings.advancedTitle')}</h2>
            <div className="form-group">
              <label>{t('settings.theme')}</label>
              <div className="theme-options">
                {[['light', t('settings.light')], ['dark', t('settings.dark')]].map(([val, label]) => (
                  <label key={val} className="theme-option">
                    <input type="radio" name="theme" value={val}
                      checked={theme === val} onChange={e => setTheme(e.target.value)} />
                    <span>{label}</span>
                  </label>
                ))}
              </div>
            </div>
            {isAdmin && (
            <div className="info-section" data-testid="section-storage-location">
              <h3>{t('settings.storageTitle')}</h3>
              {config?.storage_paths ? (
                <div className="storage-paths">
                  <div className="storage-path-row">
                    <span className="path-label">{t('settings.configFile')}</span>
                    <code className="path-value">{config.storage_paths.config_file}</code>
                  </div>
                  <div className="storage-path-row">
                    <span className="path-label">{t('settings.conversationsLabel')}</span>
                    <code className="path-value">{config.storage_paths.conversations_dir}</code>
                  </div>
                  <div className="storage-path-row">
                    <span className="path-label">{t('settings.documentsLabel')}</span>
                    <code className="path-value">{config.storage_paths.documents_dir}</code>
                  </div>
                </div>
              ) : (
                <>
                  <p>{t('settings.conversationsLabel')} <code>data/conversations/</code></p>
                  <p>{t('settings.documentsLabel')} <code>data/documents/</code></p>
                </>
              )}
            </div>
            )}
            <div className="info-section">
              <h3>{t('settings.aboutTitle')}</h3>
              <p>{t('settings.aboutDesc')}</p>
              <p>{t('settings.version', { version: '2.0.0' })}</p>
            </div>
            <button onClick={handleSaveTheme} disabled={isSaving} className="btn-primary">
              {isSaving ? t('settings.saving') : t('settings.saveSettings')}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
