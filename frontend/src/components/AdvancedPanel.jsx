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
    defaultModel: 'default',
    multiModel: true, // LM Studio developer mode supports multiple models
    modelMapping: {}, // Maps council model IDs to LM Studio model names
    chairmanModel: '', // Specific model for chairman (empty = use default)
  },
  hybrid: {
    councilModelSources: {},
    councilModelLmStudioNames: {}, // LM Studio model name for each council model in hybrid mode
    chairmanSource: 'openrouter',
    chairmanLmStudioModel: '', // LM Studio model name for chairman in hybrid mode
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

  // Initialize hybrid council sources and lmstudio model mappings when council models change
  useEffect(() => {
    if (councilModels.length > 0) {
      setSettings(prev => {
        const newSources = { ...prev.hybrid.councilModelSources };
        const newLmStudioNames = { ...prev.hybrid.councilModelLmStudioNames };
        const newModelMapping = { ...prev.lmstudio.modelMapping };
        
        councilModels.forEach(modelId => {
          if (!newSources[modelId]) {
            newSources[modelId] = 'openrouter';
          }
          if (!newLmStudioNames[modelId]) {
            newLmStudioNames[modelId] = '';
          }
          if (!newModelMapping[modelId]) {
            newModelMapping[modelId] = '';
          }
        });
        
        // Remove models no longer in council
        Object.keys(newSources).forEach(modelId => {
          if (!councilModels.includes(modelId)) {
            delete newSources[modelId];
            delete newLmStudioNames[modelId];
            delete newModelMapping[modelId];
          }
        });
        
        return {
          ...prev,
          lmstudio: { ...prev.lmstudio, modelMapping: newModelMapping },
          hybrid: { 
            ...prev.hybrid, 
            councilModelSources: newSources,
            councilModelLmStudioNames: newLmStudioNames,
          },
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

  const handleLmStudioModelMapping = (councilModelId, lmStudioModelName) => {
    setSettings(prev => ({
      ...prev,
      lmstudio: {
        ...prev.lmstudio,
        modelMapping: {
          ...prev.lmstudio.modelMapping,
          [councilModelId]: lmStudioModelName,
        },
      },
    }));
  };

  const handleLmStudioChairmanModel = (modelName) => {
    setSettings(prev => ({
      ...prev,
      lmstudio: { ...prev.lmstudio, chairmanModel: modelName },
    }));
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

  const handleHybridModelLmStudioName = (modelId, lmStudioName) => {
    setSettings(prev => ({
      ...prev,
      hybrid: {
        ...prev.hybrid,
        councilModelLmStudioNames: {
          ...prev.hybrid.councilModelLmStudioNames,
          [modelId]: lmStudioName,
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

  const handleHybridChairmanLmStudioModel = (modelName) => {
    setSettings(prev => ({
      ...prev,
      hybrid: { ...prev.hybrid, chairmanLmStudioModel: modelName },
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
                <label htmlFor="lmstudio-default-model">Default Model</label>
                <input
                  type="text"
                  id="lmstudio-default-model"
                  value={settings.lmstudio.defaultModel}
                  onChange={e => handleLmStudioChange('defaultModel', e.target.value)}
                  placeholder="default"
                  data-testid="input-lmstudio-default-model"
                />
                <span className="form-hint">
                  Default model when no specific model is assigned. Use "default" for auto-selection.
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
                <div className="info-box info-box-highlight">
                  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                  </svg>
                  <p>
                    <strong>Multi-model mode:</strong> LM Studio developer mode can load multiple models simultaneously.
                    Assign different models to each council member below.
                  </p>
                </div>
              )}
            </div>
          )}

          {/* LM Studio Multi-Model Assignments (only in lmstudio mode) */}
          {settings.mode === 'lmstudio' && councilModels.length > 0 && (
            <div className="config-section">
              <h3>Council Model Assignments</h3>
              <p className="config-description">
                Assign a specific LM Studio model to each council member. Leave empty to use the default model.
              </p>
              <div className="lmstudio-model-assignments">
                {councilModels.map(modelId => (
                  <div key={modelId} className="lmstudio-model-row">
                    <div className="model-info">
                      <span className="model-name" title={modelId}>
                        {getModelDisplayName(modelId)}
                      </span>
                      <span className="model-id-hint">{modelId}</span>
                    </div>
                    <input
                      type="text"
                      value={settings.lmstudio.modelMapping[modelId] || ''}
                      onChange={e => handleLmStudioModelMapping(modelId, e.target.value)}
                      placeholder="LM Studio model name"
                      className="lmstudio-model-input"
                      data-testid={`lmstudio-model-${modelId}`}
                    />
                  </div>
                ))}
              </div>

              {chairmanModel && (
                <div className="chairman-lmstudio-assignment">
                  <h4>Chairman Model</h4>
                  <div className="lmstudio-model-row">
                    <div className="model-info">
                      <span className="model-name" title={chairmanModel}>
                        {getModelDisplayName(chairmanModel)} (Chairman)
                      </span>
                    </div>
                    <input
                      type="text"
                      value={settings.lmstudio.chairmanModel || ''}
                      onChange={e => handleLmStudioChairmanModel(e.target.value)}
                      placeholder="LM Studio model name"
                      className="lmstudio-model-input"
                      data-testid="lmstudio-chairman-model"
                    />
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Hybrid Configuration */}
          {settings.mode === 'hybrid' && councilModels.length > 0 && (
            <div className="config-section">
              <h3>Hybrid Model Assignments</h3>
              <p className="config-description">
                Assign each council model to OpenRouter or LM Studio. For LM Studio models, specify the model name.
              </p>
              <div className="hybrid-assignments">
                {councilModels.map(modelId => (
                  <div key={modelId} className="hybrid-model-row-extended">
                    <div className="hybrid-model-header">
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
                    {settings.hybrid.councilModelSources[modelId] === 'lmstudio' && (
                      <div className="hybrid-lmstudio-model-input">
                        <input
                          type="text"
                          value={settings.hybrid.councilModelLmStudioNames[modelId] || ''}
                          onChange={e => handleHybridModelLmStudioName(modelId, e.target.value)}
                          placeholder="LM Studio model name (e.g., mistral-7b)"
                          data-testid={`hybrid-lmstudio-name-${modelId}`}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {chairmanModel && (
                <div className="chairman-assignment">
                  <h4>Chairman Source</h4>
                  <div className="hybrid-model-row-extended">
                    <div className="hybrid-model-header">
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
                    {settings.hybrid.chairmanSource === 'lmstudio' && (
                      <div className="hybrid-lmstudio-model-input">
                        <input
                          type="text"
                          value={settings.hybrid.chairmanLmStudioModel || ''}
                          onChange={e => handleHybridChairmanLmStudioModel(e.target.value)}
                          placeholder="LM Studio model name for Chairman"
                          data-testid="hybrid-chairman-lmstudio-name"
                        />
                      </div>
                    )}
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
