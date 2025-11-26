import { useState, useEffect } from 'react';
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

  useEffect(() => {
    loadConfiguration();
    loadAvailableModels();
  }, []);

  const loadConfiguration = async () => {
    try {
      setIsLoading(true);
      const cfg = await api.getConfig();
      setConfig(cfg);
      setSelectedModels(cfg.council_models || []);
      setChairmanModel(cfg.chairman_model || '');
      setTheme(cfg.theme || 'light');
    } catch (error) {
      console.error('Failed to load configuration:', error);
      showToast('Failed to load configuration', 'error');
    } finally {
      setIsLoading(false);
    }
  };

  const loadAvailableModels = async () => {
    try {
      const result = await api.getAvailableModels();
      setAvailableModels(result.models || []);
    } catch (error) {
      console.error('Failed to load models:', error);
    }
  };

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
