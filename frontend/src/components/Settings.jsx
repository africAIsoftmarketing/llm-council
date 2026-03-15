import { useState, useEffect, useCallback } from 'react';
import { api } from '../api';
import './Settings.css';

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
  
  // LM Studio states
  const [lmStudioUrls, setLmStudioUrls] = useState({});
  const [testingUrl, setTestingUrl] = useState(null);
  const [urlTestResults, setUrlTestResults] = useState({});

  const loadConfiguration = useCallback(async () => {
    try {
      setIsLoading(true);
      const cfg = await api.getConfig();
      setConfig(cfg);
      setSelectedModels(cfg.council_models || []);
      setChairmanModel(cfg.chairman_model || '');
      setTheme(cfg.theme || 'light');
      setLmStudioUrls(cfg.lm_studio_urls || {});
    } catch (error) {
      console.error('Failed to load configuration:', error);
      showToast('Failed to load configuration', 'error');
    } finally {
      setIsLoading(false);
    }
  }, [showToast]);

  const loadAvailableModels = useCallback(async () => {
    try {
      const result = await api.getAvailableModels();
      setAvailableModels(result.models || []);
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  }, []);

  useEffect(() => {
    loadConfiguration();
    loadAvailableModels();
  }, [loadConfiguration, loadAvailableModels]);

  const handleValidateKey = async () => {
    if (!apiKey.trim()) {
      showToast('Please enter an API key', 'warning');
      return;
    }
    
    setIsValidatingKey(true);
    setKeyValidation(null);
    
    try {
      const result = await api.validateApiKey(apiKey);
      setKeyValidation(result);
      
      if (result.valid) {
        showToast('API key is valid!', 'success');
      } else {
        showToast(result.error || 'Invalid API key', 'error');
      }
    } catch (error) {
      showToast('Failed to validate API key', 'error');
    } finally {
      setIsValidatingKey(false);
    }
  };

  const handleSaveApiKey = async () => {
    if (!apiKey.trim()) {
      showToast('Please enter an API key', 'warning');
      return;
    }
    
    setIsSaving(true);
    try {
      await api.updateConfig({ openrouter_api_key: apiKey });
      showToast('API key saved successfully!', 'success');
      setApiKey('');
      await loadConfiguration();
      onConfigUpdate();
    } catch (error) {
      showToast('Failed to save API key', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  const handleToggleModel = (modelId) => {
    setSelectedModels(prev => {
      if (prev.includes(modelId)) {
        return prev.filter(id => id !== modelId);
      } else {
        return [...prev, modelId];
      }
    });
  };

  const handleSaveModels = async () => {
    if (selectedModels.length === 0) {
      showToast('Please select at least one council model', 'warning');
      return;
    }
    
    setIsSaving(true);
    try {
      await api.updateConfig({
        council_models: selectedModels,
        chairman_model: chairmanModel || selectedModels[0]
      });
      showToast('Model configuration saved!', 'success');
      await loadConfiguration();
      onConfigUpdate();
    } catch (error) {
      showToast('Failed to save model configuration', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  const handleAddCustomModel = async () => {
    if (!customModel.id || !customModel.name || !customModel.provider) {
      showToast('Please fill in all custom model fields', 'warning');
      return;
    }
    
    try {
      await api.addCustomModel(customModel.id, customModel.name, customModel.provider);
      showToast('Custom model added!', 'success');
      setCustomModel({ id: '', name: '', provider: '' });
      await loadAvailableModels();
    } catch (error) {
      showToast('Failed to add custom model', 'error');
    }
  };

  const handleSaveTheme = async () => {
    setIsSaving(true);
    try {
      await api.updateConfig({ theme });
      showToast('Theme saved!', 'success');
    } catch (error) {
      showToast('Failed to save theme', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  // LM Studio handlers
  const handleLmStudioUrlChange = (modelId, url) => {
    setLmStudioUrls(prev => ({
      ...prev,
      [modelId]: url
    }));
  };

  const handleTestLmStudioUrl = async (modelId) => {
    const url = lmStudioUrls[modelId];
    if (!url || !url.trim()) {
      showToast('Please enter a URL first', 'warning');
      return;
    }
    
    setTestingUrl(modelId);
    setUrlTestResults(prev => ({ ...prev, [modelId]: null }));
    
    try {
      const result = await api.testLmStudioConnection(url, modelId);
      setUrlTestResults(prev => ({ ...prev, [modelId]: result }));
      
      if (result.success) {
        showToast(`Connected! Found ${result.models_available?.length || 0} model(s)`, 'success');
      } else {
        showToast(result.error || 'Connection failed', 'error');
      }
    } catch (error) {
      setUrlTestResults(prev => ({ 
        ...prev, 
        [modelId]: { success: false, error: error.message }
      }));
      showToast('Failed to test connection', 'error');
    } finally {
      setTestingUrl(null);
    }
  };

  const handleClearLmStudioUrl = (modelId) => {
    setLmStudioUrls(prev => {
      const updated = { ...prev };
      delete updated[modelId];
      return updated;
    });
    setUrlTestResults(prev => {
      const updated = { ...prev };
      delete updated[modelId];
      return updated;
    });
  };

  const handleSaveLmStudioUrls = async () => {
    setIsSaving(true);
    try {
      // Filter out empty URLs
      const cleanUrls = Object.fromEntries(
        Object.entries(lmStudioUrls).filter(([, url]) => url && url.trim())
      );
      await api.updateConfig({ lm_studio_urls: cleanUrls });
      showToast('LM Studio URLs saved!', 'success');
      await loadConfiguration();
      onConfigUpdate();
    } catch (error) {
      showToast('Failed to save LM Studio URLs', 'error');
    } finally {
      setIsSaving(false);
    }
  };

  // Group models by provider
  const modelsByProvider = availableModels.reduce((acc, model) => {
    if (!acc[model.provider]) {
      acc[model.provider] = [];
    }
    acc[model.provider].push(model);
    return acc;
  }, {});

  if (isLoading) {
    return (
      <div className="settings">
        <div className="settings-loading">
          <div className="spinner"></div>
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
        <button
          className={`settings-tab ${activeTab === 'api' ? 'active' : ''}`}
          onClick={() => setActiveTab('api')}
          data-testid="tab-api"
        >
          API Settings
        </button>
        <button
          className={`settings-tab ${activeTab === 'lmstudio' ? 'active' : ''}`}
          onClick={() => setActiveTab('lmstudio')}
          data-testid="tab-lmstudio"
        >
          LM Studio
        </button>
        <button
          className={`settings-tab ${activeTab === 'models' ? 'active' : ''}`}
          onClick={() => setActiveTab('models')}
          data-testid="tab-models"
        >
          Council Models
        </button>
        <button
          className={`settings-tab ${activeTab === 'chairman' ? 'active' : ''}`}
          onClick={() => setActiveTab('chairman')}
          data-testid="tab-chairman"
        >
          Chairman Model
        </button>
        <button
          className={`settings-tab ${activeTab === 'advanced' ? 'active' : ''}`}
          onClick={() => setActiveTab('advanced')}
          data-testid="tab-advanced"
        >
          Advanced
        </button>
      </div>

      <div className="settings-content">
        {/* API Settings Tab */}
        {activeTab === 'api' && (
          <div className="settings-section" data-testid="section-api">
            <h2>OpenRouter API Key</h2>
            <p className="settings-description">
              Get your API key from{' '}
              <a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer">
                openrouter.ai/keys
              </a>. Make sure you have credits available.
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
                <input
                  type="password"
                  id="apiKey"
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-or-v1-..."
                  data-testid="input-api-key"
                />
                <button
                  onClick={handleValidateKey}
                  disabled={isValidatingKey || !apiKey.trim()}
                  className="btn-secondary"
                  data-testid="btn-validate-key"
                >
                  {isValidatingKey ? 'Validating...' : 'Validate'}
                </button>
              </div>
            </div>

            {keyValidation && (
              <div className={`validation-result ${keyValidation.valid ? 'valid' : 'invalid'}`}>
                {keyValidation.valid ? (
                  <>
                    <span className="validation-icon">✓</span>
                    <span>API key is valid</span>
                    {keyValidation.data?.label && (
                      <span className="key-label">({keyValidation.data.label})</span>
                    )}
                  </>
                ) : (
                  <>
                    <span className="validation-icon">✗</span>
                    <span>{keyValidation.error}</span>
                  </>
                )}
              </div>
            )}

            <button
              onClick={handleSaveApiKey}
              disabled={isSaving || !apiKey.trim()}
              className="btn-primary"
              data-testid="btn-save-api-key"
            >
              {isSaving ? 'Saving...' : 'Save API Key'}
            </button>
          </div>
        )}

        {/* LM Studio Tab */}
        {activeTab === 'lmstudio' && (
          <div className="settings-section" data-testid="section-lmstudio">
            <h2>LM Studio Configuration</h2>
            <p className="settings-description">
              Configure LM Studio server URLs for your council models. When a model has an LM Studio URL configured, 
              it will query your local LM Studio server instead of OpenRouter.
            </p>

            <div className="lm-studio-info">
              <h4>How to use:</h4>
              <ol>
                <li>Start LM Studio and load a model</li>
                <li>Enable the local server in LM Studio (usually at <code>http://localhost:1234/v1</code>)</li>
                <li>Make sure CORS is enabled in LM Studio settings</li>
                <li>Enter the server URL below for the model you want to use locally</li>
                <li>Test the connection to verify it works</li>
              </ol>
            </div>

            <div className="lm-studio-models">
              <h3>Configure URLs for Selected Models</h3>
              {selectedModels.length === 0 ? (
                <p className="no-models-message">
                  No models selected. Go to &quot;Council Models&quot; tab to select models first.
                </p>
              ) : (
                <div className="lm-studio-url-list">
                  {selectedModels.map((modelId) => {
                    const model = availableModels.find(m => m.id === modelId);
                    const testResult = urlTestResults[modelId];
                    const isCurrentlyTesting = testingUrl === modelId;
                    
                    return (
                      <div key={modelId} className="lm-studio-url-item">
                        <div className="lm-studio-model-info">
                          <span className="model-name">{model?.name || modelId}</span>
                          <span className="model-id">{modelId}</span>
                          {lmStudioUrls[modelId] && (
                            <span className="status-badge lm-studio">LM Studio</span>
                          )}
                        </div>
                        
                        <div className="lm-studio-url-input">
                          <input
                            type="text"
                            value={lmStudioUrls[modelId] || ''}
                            onChange={(e) => handleLmStudioUrlChange(modelId, e.target.value)}
                            placeholder="http://localhost:1234/v1"
                            data-testid={`lmstudio-url-${modelId}`}
                          />
                          <button
                            onClick={() => handleTestLmStudioUrl(modelId)}
                            disabled={isCurrentlyTesting || !lmStudioUrls[modelId]?.trim()}
                            className="btn-secondary btn-test"
                            data-testid={`lmstudio-test-${modelId}`}
                          >
                            {isCurrentlyTesting ? 'Testing...' : 'Test'}
                          </button>
                          {lmStudioUrls[modelId] && (
                            <button
                              onClick={() => handleClearLmStudioUrl(modelId)}
                              className="btn-secondary btn-clear"
                              title="Clear URL (use OpenRouter)"
                            >
                              ✕
                            </button>
                          )}
                        </div>
                        
                        {testResult && (
                          <div className={`test-result ${testResult.success ? 'success' : 'error'}`}>
                            {testResult.success ? (
                              <>
                                <span className="test-icon">✓</span>
                                <span>{testResult.message}</span>
                                {testResult.models_available?.length > 0 && (
                                  <span className="models-list">
                                    Models: {testResult.models_available.join(', ')}
                                  </span>
                                )}
                              </>
                            ) : (
                              <>
                                <span className="test-icon">✗</span>
                                <span>{testResult.error}</span>
                              </>
                            )}
                          </div>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <button
              onClick={handleSaveLmStudioUrls}
              disabled={isSaving}
              className="btn-primary"
              data-testid="btn-save-lmstudio"
            >
              {isSaving ? 'Saving...' : 'Save LM Studio Configuration'}
            </button>
          </div>
        )}

        {/* Council Models Tab */}
        {activeTab === 'models' && (
          <div className="settings-section" data-testid="section-models">
            <h2>Council Models</h2>
            <p className="settings-description">
              Select the models that will participate in your LLM Council.
              Each model will provide its own response, and they will rank each other&apos;s answers.
            </p>

            <div className="selected-count">
              {selectedModels.length} model{selectedModels.length !== 1 ? 's' : ''} selected
            </div>

            <div className="models-grid">
              {Object.entries(modelsByProvider).map(([provider, models]) => (
                <div key={provider} className="provider-group">
                  <h3 className="provider-name">{provider}</h3>
                  <div className="provider-models">
                    {models.map((model) => (
                      <label key={model.id} className="model-checkbox">
                        <input
                          type="checkbox"
                          checked={selectedModels.includes(model.id)}
                          onChange={() => handleToggleModel(model.id)}
                          data-testid={`model-${model.id}`}
                        />
                        <span className="model-name">{model.name}</span>
                        <span className="model-id">{model.id}</span>
                      </label>
                    ))}
                  </div>
                </div>
              ))}
            </div>

            <div className="custom-model-section">
              <h3>Add Custom Model</h3>
              <div className="custom-model-form">
                <input
                  type="text"
                  placeholder="Model ID (e.g., provider/model-name)"
                  value={customModel.id}
                  onChange={(e) => setCustomModel({ ...customModel, id: e.target.value })}
                />
                <input
                  type="text"
                  placeholder="Display Name"
                  value={customModel.name}
                  onChange={(e) => setCustomModel({ ...customModel, name: e.target.value })}
                />
                <input
                  type="text"
                  placeholder="Provider"
                  value={customModel.provider}
                  onChange={(e) => setCustomModel({ ...customModel, provider: e.target.value })}
                />
                <button onClick={handleAddCustomModel} className="btn-secondary">
                  Add Model
                </button>
              </div>
            </div>

            <button
              onClick={handleSaveModels}
              disabled={isSaving || selectedModels.length === 0}
              className="btn-primary"
              data-testid="btn-save-models"
            >
              {isSaving ? 'Saving...' : 'Save Model Selection'}
            </button>
          </div>
        )}

        {/* Chairman Model Tab */}
        {activeTab === 'chairman' && (
          <div className="settings-section" data-testid="section-chairman">
            <h2>Chairman Model</h2>
            <p className="settings-description">
              The Chairman model synthesizes the final response from all council members.
              Choose a model that&apos;s good at summarization and analysis.
            </p>

            {config?.chairman_model && (
              <div className="current-chairman">
                <span>Current Chairman:</span>
                <strong>{config.chairman_model}</strong>
              </div>
            )}

            <div className="form-group">
              <label htmlFor="chairmanSelect">Select Chairman Model</label>
              <select
                id="chairmanSelect"
                value={chairmanModel}
                onChange={(e) => setChairmanModel(e.target.value)}
                data-testid="select-chairman"
              >
                <option value="">-- Select a model --</option>
                {availableModels.map((model) => (
                  <option key={model.id} value={model.id}>
                    {model.name} ({model.provider})
                  </option>
                ))}
              </select>
            </div>

            <div className="chairman-tips">
              <h4>Tips for choosing a Chairman:</h4>
              <ul>
                <li>Consider using a model with strong reasoning capabilities</li>
                <li>The chairman should be good at synthesizing multiple viewpoints</li>
                <li>Larger models often produce better summaries</li>
                <li>The chairman can be the same as one of the council members</li>
              </ul>
            </div>

            <button
              onClick={handleSaveModels}
              disabled={isSaving || !chairmanModel}
              className="btn-primary"
              data-testid="btn-save-chairman"
            >
              {isSaving ? 'Saving...' : 'Save Chairman Selection'}
            </button>
          </div>
        )}

        {/* Advanced Settings Tab */}
        {activeTab === 'advanced' && (
          <div className="settings-section" data-testid="section-advanced">
            <h2>Advanced Settings</h2>

            <div className="form-group">
              <label>Theme</label>
              <div className="theme-options">
                <label className="theme-option">
                  <input
                    type="radio"
                    name="theme"
                    value="light"
                    checked={theme === 'light'}
                    onChange={(e) => setTheme(e.target.value)}
                  />
                  <span>Light</span>
                </label>
                <label className="theme-option">
                  <input
                    type="radio"
                    name="theme"
                    value="dark"
                    checked={theme === 'dark'}
                    onChange={(e) => setTheme(e.target.value)}
                  />
                  <span>Dark</span>
                </label>
              </div>
            </div>

            <div className="info-section">
              <h3>Storage Location</h3>
              <p>Conversations are stored in: <code>data/conversations/</code></p>
              <p>Documents are stored in: <code>data/documents/</code></p>
            </div>

            <div className="info-section">
              <h3>About LLM Council</h3>
              <p>
                LLM Council is a 3-stage deliberation system where multiple LLMs
                collaboratively answer your questions through individual responses,
                peer review, and chairman synthesis.
              </p>
              <p>
                Version: 2.0.0 (with Configuration Dashboard & Document Upload)
              </p>
            </div>

            <button
              onClick={handleSaveTheme}
              disabled={isSaving}
              className="btn-primary"
            >
              {isSaving ? 'Saving...' : 'Save Settings'}
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
