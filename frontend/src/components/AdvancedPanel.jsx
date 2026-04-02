import { useState, useEffect } from 'react';
import { api } from '../api';
import './AdvancedPanel.css';

const STORAGE_KEY = 'llm_council_advanced_settings';

const DEFAULT_SETTINGS = {
  mode: 'openrouter',
  openrouter: {
    apiKey: '',
  },
  lmstudio: {
    baseUrl: 'http://localhost:1234/v1',
    model: 'mistral-7b-instruct',
  },
  hybrid: {
    councilModelSources: {},
    chairmanSource: 'openrouter',
  },
};

export default function AdvancedPanel({
  onClose,
  onSettingsChange,
  councilModels = [],
  chairmanModel = '',
  showToast,
}) {
  const [settings, setSettings] = useState(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        const parsed = JSON.parse(stored);
        return { ...DEFAULT_SETTINGS, ...parsed };
      }
    } catch (e) {
      console.error('Failed to load advanced settings:', e);
    }
    return DEFAULT_SETTINGS;
  });

  const [testingConnection, setTestingConnection] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState(null);

  // Save to localStorage whenever settings change
  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    onSettingsChange?.(settings);
  }, [settings, onSettingsChange]);

  // Initialize hybrid council sources when council models change
  useEffect(() => {
    if (councilModels.length > 0) {
      setSettings(prev => {
        const newSources = { ...prev.hybrid.councilModelSources };
        councilModels.forEach(modelId => {
          if (!newSources[modelId]) {
            newSources[modelId] = 'openrouter';
          }
        });
        // Remove models no longer in council
        Object.keys(newSources).forEach(modelId => {
          if (!councilModels.includes(modelId)) {
            delete newSources[modelId];
          }
        });
        return {
          ...prev,
          hybrid: { ...prev.hybrid, councilModelSources: newSources },
        };
      });
    }
  }, [councilModels]);

  const handleModeChange = (mode) => {
    setSettings(prev => ({ ...prev, mode }));
    setConnectionStatus(null);
  };

  const handleOpenRouterKeyChange = (apiKey) => {
    setSettings(prev => ({
      ...prev,
      openrouter: { ...prev.openrouter, apiKey },
    }));
  };

  const handleLmStudioChange = (field, value) => {
    setSettings(prev => ({
      ...prev,
      lmstudio: { ...prev.lmstudio, [field]: value },
    }));
    setConnectionStatus(null);
  };

  const handleHybridModelSourceChange = (modelId, source) => {
    setSettings(prev => ({
      ...prev,
      hybrid: {
        ...prev.hybrid,
        councilModelSources: {
          ...prev.hybrid.councilModelSources,
          [modelId]: source,
        },
      },
    }));
  };

  const handleHybridChairmanSourceChange = (source) => {
    setSettings(prev => ({
      ...prev,
      hybrid: { ...prev.hybrid, chairmanSource: source },
    }));
  };

  const testLmStudioConnection = async () => {
    const baseUrl = settings.lmstudio.baseUrl;
    if (!baseUrl?.trim()) {
      showToast?.('Please enter a LM Studio URL first', 'warning');
      return;
    }

    setTestingConnection(true);
    setConnectionStatus(null);

    try {
      const result = await api.testLmStudioConnection(baseUrl, settings.lmstudio.model);
      setConnectionStatus(result);
      if (result.success) {
        showToast?.(`Connected! Found ${result.models_available?.length || 0} model(s)`, 'success');
      } else {
        showToast?.(result.error || 'Connection failed', 'error');
      }
    } catch (error) {
      setConnectionStatus({ success: false, error: error.message });
      showToast?.('Connection test failed', 'error');
    } finally {
      setTestingConnection(false);
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
    // Extract a shorter display name from model ID
    const parts = modelId.split('/');
    return parts.length > 1 ? parts[1] : modelId;
  };

  return (
    <div className="advanced-panel-overlay" onClick={onClose} data-testid="advanced-panel-overlay">
      <div className="advanced-panel" onClick={e => e.stopPropagation()} data-testid="advanced-panel">
        <div className="advanced-panel-header">
          <h2>Advanced Configuration</h2>
          <button className="close-btn" onClick={onClose} data-testid="btn-close-advanced">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
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
                    {mode === 'lmstudio' && 'Local LM Studio server'}
                    {mode === 'hybrid' && 'Mix cloud & local models'}
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

          {/* LM Studio Configuration */}
          {(settings.mode === 'lmstudio' || settings.mode === 'hybrid') && (
            <div className="config-section">
              <h3>LM Studio Settings</h3>
              <div className="form-group">
                <label htmlFor="lmstudio-url">Server URL</label>
                <div className="input-with-test">
                  <input
                    type="text"
                    id="lmstudio-url"
                    value={settings.lmstudio.baseUrl}
                    onChange={e => handleLmStudioChange('baseUrl', e.target.value)}
                    placeholder="http://localhost:1234/v1"
                    data-testid="input-lmstudio-url"
                  />
                  <button
                    className="btn-test"
                    onClick={testLmStudioConnection}
                    disabled={testingConnection}
                    data-testid="btn-test-connection"
                  >
                    {testingConnection ? 'Testing...' : 'Test'}
                  </button>
                </div>
              </div>

              <div className="form-group">
                <label htmlFor="lmstudio-model">Model Name</label>
                <input
                  type="text"
                  id="lmstudio-model"
                  value={settings.lmstudio.model}
                  onChange={e => handleLmStudioChange('model', e.target.value)}
                  placeholder="mistral-7b-instruct"
                  data-testid="input-lmstudio-model"
                />
                <span className="form-hint">
                  The model name loaded in LM Studio.
                </span>
              </div>

              {connectionStatus && (
                <div className={`connection-status ${connectionStatus.success ? 'success' : 'error'}`}>
                  <span className="status-icon">{connectionStatus.success ? '✓' : '✗'}</span>
                  <span>{connectionStatus.success ? connectionStatus.message || 'Connected!' : connectionStatus.error}</span>
                  {connectionStatus.models_available?.length > 0 && (
                    <div className="models-found">
                      Available models: {connectionStatus.models_available.join(', ')}
                    </div>
                  )}
                </div>
              )}

              {settings.mode === 'lmstudio' && (
                <div className="info-box">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="16" x2="12" y2="12"></line>
                    <line x1="12" y1="8" x2="12.01" y2="8"></line>
                  </svg>
                  <p>
                    In LM Studio mode, all council members and the Chairman will use the same local model.
                    LM Studio can only load one model at a time.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Hybrid Configuration */}
          {settings.mode === 'hybrid' && councilModels.length > 0 && (
            <div className="config-section">
              <h3>Hybrid Model Assignments</h3>
              <p className="config-description">
                Assign each council model to OpenRouter or LM Studio.
              </p>
              <div className="hybrid-assignments">
                {councilModels.map(modelId => (
                  <div key={modelId} className="hybrid-model-row">
                    <span className="model-name" title={modelId}>
                      {getModelDisplayName(modelId)}
                    </span>
                    <div className="source-toggle">
                      <button
                        className={`toggle-btn ${settings.hybrid.councilModelSources[modelId] === 'openrouter' ? 'active' : ''}`}
                        onClick={() => handleHybridModelSourceChange(modelId, 'openrouter')}
                        data-testid={`hybrid-${modelId}-openrouter`}
                      >
                        OpenRouter
                      </button>
                      <button
                        className={`toggle-btn ${settings.hybrid.councilModelSources[modelId] === 'lmstudio' ? 'active' : ''}`}
                        onClick={() => handleHybridModelSourceChange(modelId, 'lmstudio')}
                        data-testid={`hybrid-${modelId}-lmstudio`}
                      >
                        LM Studio
                      </button>
                    </div>
                  </div>
                ))}
              </div>

              {chairmanModel && (
                <div className="chairman-assignment">
                  <h4>Chairman Source</h4>
                  <div className="hybrid-model-row">
                    <span className="model-name" title={chairmanModel}>
                      {getModelDisplayName(chairmanModel)} (Chairman)
                    </span>
                    <div className="source-toggle">
                      <button
                        className={`toggle-btn ${settings.hybrid.chairmanSource === 'openrouter' ? 'active' : ''}`}
                        onClick={() => handleHybridChairmanSourceChange('openrouter')}
                        data-testid="hybrid-chairman-openrouter"
                      >
                        OpenRouter
                      </button>
                      <button
                        className={`toggle-btn ${settings.hybrid.chairmanSource === 'lmstudio' ? 'active' : ''}`}
                        onClick={() => handleHybridChairmanSourceChange('lmstudio')}
                        data-testid="hybrid-chairman-lmstudio"
                      >
                        LM Studio
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Warning for incomplete config */}
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
      return JSON.parse(stored);
    }
  } catch (e) {
    console.error('Failed to load advanced settings:', e);
  }
  return DEFAULT_SETTINGS;
}

// Export storage key for external use
export { STORAGE_KEY };
