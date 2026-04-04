import { useState, useEffect, useCallback } from 'react';
import { api } from '../api';
import './AdvancedPanel.css';

const STORAGE_KEY = 'llm_council_advanced_settings';

const DEFAULT_SETTINGS = {
  mode: 'openrouter',
  openrouter: {
    apiKey: '',
  },
  models: {},
  chairman: {
    source: 'openrouter',
    endpointUrl: 'http://localhost:1234/v1',
    localModelName: '',
  },
  throttle: {
    maxConcurrent: 1,
    delayBetweenRequests: 1.0,
    requestTimeout: 300,
  },
};

// Default model config
const DEFAULT_MODEL_CONFIG = {
  source: 'openrouter',
  endpointUrl: 'http://localhost:1234/v1',
  localModelName: '',
};

// Deep merge helper for nested objects
const deepMerge = (target, source) => {
  const result = { ...target };
  for (const key of Object.keys(source)) {
    if (source[key] && typeof source[key] === 'object' && !Array.isArray(source[key])) {
      result[key] = deepMerge(target[key] || {}, source[key]);
    } else {
      result[key] = source[key];
    }
  }
  return result;
};

export default function AdvancedPanel({
  onClose,
  onSettingsChange,
  councilModels = [],
  chairmanModel = '',
  showToast,
}) {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [testingUrls, setTestingUrls] = useState({});
  const [testResults, setTestResults] = useState({});

  // Load settings from backend on mount
  useEffect(() => {
    const loadSettings = async () => {
      try {
        // Try backend first
        const backendConfig = await api.getAdvancedConfig();
        if (backendConfig && Object.keys(backendConfig).length > 0) {
          const merged = deepMerge(DEFAULT_SETTINGS, backendConfig);
          setSettings(merged);
          onSettingsChange?.(merged);
        } else {
          // Fallback to localStorage
          const stored = localStorage.getItem(STORAGE_KEY);
          if (stored) {
            const parsed = JSON.parse(stored);
            const merged = deepMerge(DEFAULT_SETTINGS, parsed);
            setSettings(merged);
            onSettingsChange?.(merged);
          }
        }
      } catch (e) {
        console.error('Failed to load advanced settings:', e);
        // Fallback to localStorage
        try {
          const stored = localStorage.getItem(STORAGE_KEY);
          if (stored) {
            const parsed = JSON.parse(stored);
            const merged = deepMerge(DEFAULT_SETTINGS, parsed);
            setSettings(merged);
          }
        } catch (e2) {
          console.error('Failed to load from localStorage:', e2);
        }
      } finally {
        setIsLoading(false);
      }
    };
    
    loadSettings();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Initialize model configs when council models change
  useEffect(() => {
    if (councilModels.length > 0 && !isLoading) {
      setSettings(prev => {
        const newModels = { ...prev.models };
        
        // Add default config for new models
        councilModels.forEach(modelId => {
          if (!newModels[modelId]) {
            newModels[modelId] = { ...DEFAULT_MODEL_CONFIG };
          }
        });
        
        return { ...prev, models: newModels };
      });
    }
  }, [councilModels, isLoading]);

  // Save settings (to both backend and localStorage)
  const saveSettings = useCallback(async (newSettings) => {
    // Always update localStorage for quick access
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newSettings));
    
    // Save to backend
    setIsSaving(true);
    try {
      await api.saveAdvancedConfig(newSettings);
    } catch (e) {
      console.error('Failed to save to backend:', e);
    } finally {
      setIsSaving(false);
    }
    
    onSettingsChange?.(newSettings);
  }, [onSettingsChange]);

  // Debounced auto-save
  useEffect(() => {
    if (!isLoading) {
      const timer = setTimeout(() => {
        saveSettings(settings);
      }, 500);
      return () => clearTimeout(timer);
    }
  }, [settings, isLoading, saveSettings]);

  const handleModeChange = (mode) => {
    setSettings(prev => ({ ...prev, mode }));
    setTestResults({});
  };

  const handleOpenRouterKeyChange = (apiKey) => {
    setSettings(prev => ({
      ...prev,
      openrouter: { ...prev.openrouter, apiKey },
    }));
  };

  const handleModelConfigChange = (modelId, field, value) => {
    setSettings(prev => ({
      ...prev,
      models: {
        ...prev.models,
        [modelId]: {
          ...(prev.models[modelId] || DEFAULT_MODEL_CONFIG),
          [field]: value,
        },
      },
    }));
    // Clear test result when config changes
    if (field === 'endpointUrl') {
      setTestResults(prev => {
        const newResults = { ...prev };
        delete newResults[modelId];
        return newResults;
      });
    }
  };

  const handleChairmanConfigChange = (field, value) => {
    setSettings(prev => ({
      ...prev,
      chairman: {
        ...prev.chairman,
        [field]: value,
      },
    }));
    if (field === 'endpointUrl') {
      setTestResults(prev => {
        const newResults = { ...prev };
        delete newResults['chairman'];
        return newResults;
      });
    }
  };

  // Throttle handlers
  const handleThrottleChange = (field, value) => {
    setSettings(prev => ({
      ...prev,
      throttle: { ...prev.throttle, [field]: value },
    }));
  };

  const THROTTLE_PRESETS = {
    safe:     { maxConcurrent: 1, delayBetweenRequests: 2.0, requestTimeout: 300 },
    balanced: { maxConcurrent: 2, delayBetweenRequests: 0.5, requestTimeout: 180 },
    fast:     { maxConcurrent: 4, delayBetweenRequests: 0.0, requestTimeout: 120 },
  };

  const applyThrottlePreset = (name) => {
    setSettings(prev => ({ ...prev, throttle: { ...THROTTLE_PRESETS[name] } }));
  };

  const isThrottlePreset = (name) => {
    const p = THROTTLE_PRESETS[name];
    const t = settings.throttle || {};
    return t.maxConcurrent === p.maxConcurrent
      && t.delayBetweenRequests === p.delayBetweenRequests
      && t.requestTimeout === p.requestTimeout;
  };

  const testConnection = async (key, url, modelName) => {
    if (!url?.trim()) {
      showToast?.('Please enter a URL first', 'warning');
      return;
    }

    setTestingUrls(prev => ({ ...prev, [key]: true }));
    setTestResults(prev => ({ ...prev, [key]: null }));

    try {
      const result = await api.testLmStudioConnection(url, modelName);
      setTestResults(prev => ({ ...prev, [key]: result }));
      if (result.success) {
        showToast?.(`Connected! Found ${result.models_available?.length || 0} model(s)`, 'success');
      } else {
        showToast?.(result.error || 'Connection failed', 'error');
      }
    } catch (error) {
      setTestResults(prev => ({ ...prev, [key]: { success: false, error: error.message } }));
      showToast?.('Connection test failed', 'error');
    } finally {
      setTestingUrls(prev => ({ ...prev, [key]: false }));
    }
  };

  const getModeLabel = (mode) => {
    switch (mode) {
      case 'openrouter': return 'OpenRouter';
      case 'lmstudio': return 'LM Studio';
      case 'hybrid': return 'Hybrid';
      default: return mode;
    }
  };

  const getModelDisplayName = (modelId) => {
    const parts = modelId.split('/');
    return parts.length > 1 ? parts[1] : modelId;
  };

  const getModelConfig = (modelId) => {
    return settings.models[modelId] || DEFAULT_MODEL_CONFIG;
  };

  if (isLoading) {
    return (
      <div className="advanced-panel-overlay" data-testid="advanced-panel-overlay">
        <div className="advanced-panel" data-testid="advanced-panel">
          <div className="advanced-panel-loading">
            <div className="spinner" />
            <span>Loading configuration...</span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="advanced-panel-overlay" onClick={onClose} data-testid="advanced-panel-overlay">
      <div className="advanced-panel" onClick={e => e.stopPropagation()} data-testid="advanced-panel">
        <div className="advanced-panel-header">
          <h2>Advanced Configuration</h2>
          <div className="header-actions">
            {isSaving && <span className="saving-indicator">Saving...</span>}
            <button className="close-btn" onClick={onClose} data-testid="btn-close-advanced">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </div>

        <div className="advanced-panel-content">
          {/* Mode Selection */}
          <div className="config-section">
            <h3>LLM Source Mode</h3>
            <p className="config-description">
              Choose how the council queries LLM models.
            </p>
            <div className="mode-selector">
              {['openrouter', 'lmstudio', 'hybrid'].map(mode => (
                <label key={mode} className={`mode-option ${settings.mode === mode ? 'active' : ''}`}>
                  <input
                    type="radio"
                    name="llm-mode"
                    value={mode}
                    checked={settings.mode === mode}
                    onChange={() => handleModeChange(mode)}
                    data-testid={`mode-${mode}`}
                  />
                  <span className="mode-label">{getModeLabel(mode)}</span>
                  <span className="mode-desc">
                    {mode === 'openrouter' && 'Cloud API via OpenRouter'}
                    {mode === 'lmstudio' && 'Local LM Studio server(s)'}
                    {mode === 'hybrid' && 'Mix cloud & local per model'}
                  </span>
                </label>
              ))}
            </div>
          </div>

          {/* OpenRouter Configuration */}
          {(settings.mode === 'openrouter' || settings.mode === 'hybrid') && (
            <div className="config-section">
              <h3>OpenRouter Settings</h3>
              <div className="form-group">
                <label htmlFor="openrouter-key">API Key (optional override)</label>
                <input
                  type="password"
                  id="openrouter-key"
                  value={settings.openrouter.apiKey}
                  onChange={e => handleOpenRouterKeyChange(e.target.value)}
                  placeholder="sk-or-v1-... (leave empty to use .env key)"
                  data-testid="input-openrouter-key"
                />
                <span className="form-hint">
                  Leave empty to use the API key from Settings or .env file.
                </span>
              </div>
            </div>
          )}

          {/* LM Studio Mode - Model Configurations */}
          {settings.mode === 'lmstudio' && councilModels.length > 0 && (
            <div className="config-section">
              <h3>LM Studio Model Configurations</h3>
              <p className="config-description">
                Configure the LM Studio endpoint and model name for each council member.
                Each model can point to a different LM Studio server.
              </p>
              <div className="model-configs">
                {councilModels.map(modelId => {
                  const cfg = getModelConfig(modelId);
                  const testResult = testResults[modelId];
                  const isTesting = testingUrls[modelId];
                  return (
                    <div key={modelId} className="model-config-card">
                      <div className="model-config-header">
                        <span className="model-name">{getModelDisplayName(modelId)}</span>
                        <span className="model-id">{modelId}</span>
                      </div>
                      <div className="model-config-fields">
                        <div className="field-row">
                          <label>Endpoint URL</label>
                          <div className="input-with-test">
                            <input
                              type="text"
                              value={cfg.endpointUrl || ''}
                              onChange={e => handleModelConfigChange(modelId, 'endpointUrl', e.target.value)}
                              placeholder="http://localhost:1234/v1"
                              data-testid={`url-${modelId}`}
                            />
                            <button
                              className="btn-test"
                              onClick={() => testConnection(modelId, cfg.endpointUrl, cfg.localModelName)}
                              disabled={isTesting}
                              data-testid={`test-${modelId}`}
                            >
                              {isTesting ? '...' : 'Test'}
                            </button>
                          </div>
                          {testResult && (
                            <span className={`test-status ${testResult.success ? 'success' : 'error'}`}>
                              {testResult.success ? '✓ Connected' : `✗ ${testResult.error}`}
                            </span>
                          )}
                        </div>
                        <div className="field-row">
                          <label>Model Name</label>
                          <input
                            type="text"
                            value={cfg.localModelName || ''}
                            onChange={e => handleModelConfigChange(modelId, 'localModelName', e.target.value)}
                            placeholder="default (auto-select)"
                            data-testid={`model-name-${modelId}`}
                          />
                        </div>
                      </div>
                    </div>
                  );
                })}

                {/* Chairman */}
                {chairmanModel && (
                  <div className="model-config-card chairman-card">
                    <div className="model-config-header">
                      <span className="model-name">{getModelDisplayName(chairmanModel)}</span>
                      <span className="chairman-badge">Chairman</span>
                    </div>
                    <div className="model-config-fields">
                      <div className="field-row">
                        <label>Endpoint URL</label>
                        <div className="input-with-test">
                          <input
                            type="text"
                            value={settings.chairman.endpointUrl || ''}
                            onChange={e => handleChairmanConfigChange('endpointUrl', e.target.value)}
                            placeholder="http://localhost:1234/v1"
                            data-testid="url-chairman"
                          />
                          <button
                            className="btn-test"
                            onClick={() => testConnection('chairman', settings.chairman.endpointUrl, settings.chairman.localModelName)}
                            disabled={testingUrls['chairman']}
                            data-testid="test-chairman"
                          >
                            {testingUrls['chairman'] ? '...' : 'Test'}
                          </button>
                        </div>
                        {testResults['chairman'] && (
                          <span className={`test-status ${testResults['chairman'].success ? 'success' : 'error'}`}>
                            {testResults['chairman'].success ? '✓ Connected' : `✗ ${testResults['chairman'].error}`}
                          </span>
                        )}
                      </div>
                      <div className="field-row">
                        <label>Model Name</label>
                        <input
                          type="text"
                          value={settings.chairman.localModelName || ''}
                          onChange={e => handleChairmanConfigChange('localModelName', e.target.value)}
                          placeholder="default (auto-select)"
                          data-testid="model-name-chairman"
                        />
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Hybrid Mode - Per-Model Source Selection */}
          {settings.mode === 'hybrid' && councilModels.length > 0 && (
            <div className="config-section">
              <h3>Hybrid Model Configurations</h3>
              <p className="config-description">
                Choose OpenRouter or LM Studio for each model. LM Studio models can have custom endpoints.
              </p>
              <div className="model-configs">
                {councilModels.map(modelId => {
                  const cfg = getModelConfig(modelId);
                  const isLmStudio = cfg.source === 'lmstudio';
                  const testResult = testResults[modelId];
                  const isTesting = testingUrls[modelId];
                  return (
                    <div key={modelId} className={`model-config-card ${isLmStudio ? 'lmstudio-selected' : ''}`}>
                      <div className="model-config-header">
                        <span className="model-name">{getModelDisplayName(modelId)}</span>
                        <div className="source-toggle">
                          <button
                            className={`toggle-btn ${cfg.source !== 'lmstudio' ? 'active' : ''}`}
                            onClick={() => handleModelConfigChange(modelId, 'source', 'openrouter')}
                            data-testid={`source-${modelId}-openrouter`}
                          >
                            OpenRouter
                          </button>
                          <button
                            className={`toggle-btn ${cfg.source === 'lmstudio' ? 'active' : ''}`}
                            onClick={() => handleModelConfigChange(modelId, 'source', 'lmstudio')}
                            data-testid={`source-${modelId}-lmstudio`}
                          >
                            LM Studio
                          </button>
                        </div>
                      </div>
                      {isLmStudio && (
                        <div className="model-config-fields">
                          <div className="field-row">
                            <label>Endpoint URL</label>
                            <div className="input-with-test">
                              <input
                                type="text"
                                value={cfg.endpointUrl || ''}
                                onChange={e => handleModelConfigChange(modelId, 'endpointUrl', e.target.value)}
                                placeholder="http://localhost:1234/v1"
                                data-testid={`url-${modelId}`}
                              />
                              <button
                                className="btn-test"
                                onClick={() => testConnection(modelId, cfg.endpointUrl, cfg.localModelName)}
                                disabled={isTesting}
                                data-testid={`test-${modelId}`}
                              >
                                {isTesting ? '...' : 'Test'}
                              </button>
                            </div>
                            {testResult && (
                              <span className={`test-status ${testResult.success ? 'success' : 'error'}`}>
                                {testResult.success ? '✓ Connected' : `✗ ${testResult.error}`}
                              </span>
                            )}
                          </div>
                          <div className="field-row">
                            <label>Model Name</label>
                            <input
                              type="text"
                              value={cfg.localModelName || ''}
                              onChange={e => handleModelConfigChange(modelId, 'localModelName', e.target.value)}
                              placeholder="default (auto-select)"
                              data-testid={`model-name-${modelId}`}
                            />
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}

                {/* Chairman in Hybrid Mode */}
                {chairmanModel && (
                  <div className={`model-config-card chairman-card ${settings.chairman.source === 'lmstudio' ? 'lmstudio-selected' : ''}`}>
                    <div className="model-config-header">
                      <span className="model-name">{getModelDisplayName(chairmanModel)}</span>
                      <span className="chairman-badge">Chairman</span>
                      <div className="source-toggle">
                        <button
                          className={`toggle-btn ${settings.chairman.source !== 'lmstudio' ? 'active' : ''}`}
                          onClick={() => handleChairmanConfigChange('source', 'openrouter')}
                          data-testid="source-chairman-openrouter"
                        >
                          OpenRouter
                        </button>
                        <button
                          className={`toggle-btn ${settings.chairman.source === 'lmstudio' ? 'active' : ''}`}
                          onClick={() => handleChairmanConfigChange('source', 'lmstudio')}
                          data-testid="source-chairman-lmstudio"
                        >
                          LM Studio
                        </button>
                      </div>
                    </div>
                    {settings.chairman.source === 'lmstudio' && (
                      <div className="model-config-fields">
                        <div className="field-row">
                          <label>Endpoint URL</label>
                          <div className="input-with-test">
                            <input
                              type="text"
                              value={settings.chairman.endpointUrl || ''}
                              onChange={e => handleChairmanConfigChange('endpointUrl', e.target.value)}
                              placeholder="http://localhost:1234/v1"
                              data-testid="url-chairman"
                            />
                            <button
                              className="btn-test"
                              onClick={() => testConnection('chairman', settings.chairman.endpointUrl, settings.chairman.localModelName)}
                              disabled={testingUrls['chairman']}
                              data-testid="test-chairman"
                            >
                              {testingUrls['chairman'] ? '...' : 'Test'}
                            </button>
                          </div>
                          {testResults['chairman'] && (
                            <span className={`test-status ${testResults['chairman'].success ? 'success' : 'error'}`}>
                              {testResults['chairman'].success ? '✓ Connected' : `✗ ${testResults['chairman'].error}`}
                            </span>
                          )}
                        </div>
                        <div className="field-row">
                          <label>Model Name</label>
                          <input
                            type="text"
                            value={settings.chairman.localModelName || ''}
                            onChange={e => handleChairmanConfigChange('localModelName', e.target.value)}
                            placeholder="default (auto-select)"
                            data-testid="model-name-chairman"
                          />
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Performance & Throttling (LM Studio / Hybrid only) */}
          {(settings.mode === 'lmstudio' || settings.mode === 'hybrid') && (
            <div className="config-section">
              <h3>Performance & Throttling</h3>
              <p className="config-description">
                Control CPU/RAM load on your laptop during local inference.
                Local models are slow and resource-heavy — avoid freezing by limiting concurrent requests.
              </p>

              {/* Preset buttons */}
              <div className="throttle-presets">
                <span className="presets-label">Presets:</span>
                <button
                  className={`preset-btn ${isThrottlePreset('safe') ? 'active' : ''}`}
                  onClick={() => applyThrottlePreset('safe')}
                  title="1 request at a time, 2s between each — recommended for laptops"
                  data-testid="preset-safe"
                >
                  Safe
                </button>
                <button
                  className={`preset-btn ${isThrottlePreset('balanced') ? 'active' : ''}`}
                  onClick={() => applyThrottlePreset('balanced')}
                  title="2 concurrent requests, 0.5s between each"
                  data-testid="preset-balanced"
                >
                  Balanced
                </button>
                <button
                  className={`preset-btn ${isThrottlePreset('fast') ? 'active' : ''}`}
                  onClick={() => applyThrottlePreset('fast')}
                  title="All parallel — risk of freeze"
                  data-testid="preset-fast"
                >
                  Fast
                </button>
              </div>

              {/* Max concurrent slider */}
              <div className="form-group">
                <label>
                  Concurrent requests: <strong>{settings.throttle?.maxConcurrent || 1}</strong>
                  {(settings.throttle?.maxConcurrent || 1) === 1 && (
                    <span className="badge-sequential">Sequential</span>
                  )}
                </label>
                <input
                  type="range"
                  min="1"
                  max="4"
                  step="1"
                  value={settings.throttle?.maxConcurrent || 1}
                  onChange={e => handleThrottleChange('maxConcurrent', parseInt(e.target.value))}
                  className="throttle-slider"
                  data-testid="slider-max-concurrent"
                />
                <div className="slider-labels">
                  <span>1 (sequential)</span>
                  <span>2</span>
                  <span>3</span>
                  <span>4 (parallel)</span>
                </div>
                <span className="form-hint">
                  {(settings.throttle?.maxConcurrent || 1) === 1
                    ? "✅ Recommended — requests execute one by one. Slower but stable."
                    : (settings.throttle?.maxConcurrent || 1) <= 2
                    ? "⚠️ Moderate — monitor CPU temperature."
                    : "⛔ Risk of freeze on laptops with large models."}
                </span>
              </div>

              {/* Delay between requests */}
              <div className="form-group">
                <label>
                  Delay between requests: <strong>{settings.throttle?.delayBetweenRequests || 1}s</strong>
                </label>
                <input
                  type="range"
                  min="0"
                  max="5"
                  step="0.5"
                  value={settings.throttle?.delayBetweenRequests || 1}
                  onChange={e => handleThrottleChange('delayBetweenRequests', parseFloat(e.target.value))}
                  className="throttle-slider"
                  data-testid="slider-delay"
                />
                <div className="slider-labels">
                  <span>0s</span>
                  <span>2.5s</span>
                  <span>5s</span>
                </div>
                <span className="form-hint">
                  Pause time between starting each request.
                  Gives CPU time to breathe between inferences.
                </span>
              </div>

              {/* Request timeout */}
              <div className="form-group">
                <label>
                  Request timeout: <strong>{Math.floor((settings.throttle?.requestTimeout || 300) / 60)}min {(settings.throttle?.requestTimeout || 300) % 60}s</strong>
                </label>
                <input
                  type="range"
                  min="30"
                  max="600"
                  step="30"
                  value={settings.throttle?.requestTimeout || 300}
                  onChange={e => handleThrottleChange('requestTimeout', parseInt(e.target.value))}
                  className="throttle-slider"
                  data-testid="slider-timeout"
                />
                <div className="slider-labels">
                  <span>30s</span>
                  <span>5 min</span>
                  <span>10 min</span>
                </div>
                <span className="form-hint">
                  Max duration per model before giving up.
                  Large models (7B+) can take 2-5 min on CPU.
                </span>
              </div>
            </div>
          )}

          {/* Warning for OpenRouter mode without key */}
          {settings.mode === 'openrouter' && !settings.openrouter.apiKey && (
            <div className="warning-box">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path>
                <line x1="12" y1="9" x2="12" y2="13"></line>
                <line x1="12" y1="17" x2="12.01" y2="17"></line>
              </svg>
              <p>
                No override API key set. The API key from Settings or .env will be used.
              </p>
            </div>
          )}
        </div>

        <div className="advanced-panel-footer">
          <button className="btn-secondary" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}

// Export helper function to get settings
export function getAdvancedSettings() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      const parsed = JSON.parse(stored);
      return deepMerge(DEFAULT_SETTINGS, parsed);
    }
  } catch (e) {
    console.error('Failed to load advanced settings:', e);
  }
  return DEFAULT_SETTINGS;
}

// Export storage key for external use
export { STORAGE_KEY };
