import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import Settings from './components/Settings';
import AdvancedPanel, { getAdvancedSettings } from './components/AdvancedPanel';
import AppHeader from './components/AppHeader';
import AppFooter from './components/AppFooter';
import TermsModal, { hasAcceptedTerms } from './components/TermsModal';
import { useAuth } from './auth/AuthContext';
import { api } from './api';
import './App.css';
import './components/AppHeader.css';

const COUNCIL_CACHE_KEY = 'llm_council_last_selection';

function App() {
  const { user, refresh } = useAuth();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const isAdmin = user?.role === 'admin';
  const [termsAccepted, setTermsAccepted] = useState(() => hasAcceptedTerms());
  const [creditsModal, setCreditsModal] = useState(null);
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [currentView, setCurrentView] = useState('chat'); // 'chat' or 'settings'
  const [isConfigured, setIsConfigured] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [toast, setToast] = useState(null);
  const [showAdvancedPanel, setShowAdvancedPanel] = useState(false);
  const [councilProgress, setCouncilProgress] = useState(null);
  const [advancedSettings, setAdvancedSettings] = useState(() => getAdvancedSettings());
  // Restore the last council selection instantly from localStorage (persists across
  // refresh); the authoritative values are then overlaid from the backend (DB).
  const [councilModels, setCouncilModels] = useState(() => {
    try { return JSON.parse(localStorage.getItem(COUNCIL_CACHE_KEY))?.council_models || []; }
    catch { return []; }
  });
  const [chairmanModel, setChairmanModel] = useState(() => {
    try { return JSON.parse(localStorage.getItem(COUNCIL_CACHE_KEY))?.chairman_model || ''; }
    catch { return ''; }
  });

  const checkConfiguration = useCallback(async () => {
    // The OpenRouter key is a deployment/admin concern; the end-user gate is now
    // the credit balance. Keep the chat UI available so credits/402 flow works.
    try {
      await api.healthCheck();
    } catch (error) {
      console.error('Failed to check configuration:', error);
    }
    setIsConfigured(true);
  }, []);

  const loadDocuments = useCallback(async () => {
    try {
      const result = await api.getDocuments();
      setDocuments(result.documents || []);
    } catch (error) {
      console.error('Failed to load documents:', error);
    }
  }, []);

  const loadCouncilConfig = useCallback(async () => {
    try {
      const config = await api.getConfig();
      const models = config.council_models || [];
      const chairman = config.chairman_model || '';
      setCouncilModels(models);
      setChairmanModel(chairman);
      // Cache for instant restore on next refresh.
      try {
        localStorage.setItem(COUNCIL_CACHE_KEY, JSON.stringify({ council_models: models, chairman_model: chairman }));
      } catch { /* noop */ }
    } catch (error) {
      console.error('Failed to load council config:', error);
    }
  }, []);

  const loadConversations = useCallback(async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  }, []);

  const loadConversation = useCallback(async (id) => {
    try {
      const conv = await api.getConversation(id);
      setCurrentConversation(conv);
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  }, []);

  const showToast = useCallback((message, type = 'info') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 4000);
  }, []);

  // Check configuration status on mount
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    checkConfiguration();
     
    loadDocuments();
    loadCouncilConfig();
  }, [checkConfiguration, loadDocuments, loadCouncilConfig]);

  // Load conversations on mount
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadConversations();
  }, [loadConversations]);

  // Load conversation details when selected
  useEffect(() => {
    if (currentConversationId) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      loadConversation(currentConversationId);
    }
  }, [currentConversationId, loadConversation]);

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, title: newConv.title, message_count: 0 },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
      setCouncilProgress(null);
      setCurrentView('chat');
    } catch (error) {
      console.error('Failed to create conversation:', error);
      showToast(t('toast.createConversationFailed'), 'error');
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
    setCouncilProgress(null);
    setCurrentView('chat');
  };

  const handleDeleteConversation = async (id) => {
    try {
      await api.deleteConversation(id);
      setConversations(conversations.filter(c => c.id !== id));
      if (currentConversationId === id) {
        setCurrentConversationId(null);
        setCurrentConversation(null);
      }
      showToast(t('toast.conversationDeleted'), 'success');
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      showToast(t('toast.deleteConversationFailed'), 'error');
    }
  };

  const handleSendMessage = async (content, includeDocuments = true) => {
    if (!currentConversationId) return;

    setIsLoading(true);
    // Reset the per-stage progress bar for this new run.
    setCouncilProgress({ steps: ['pending', 'pending', 'pending'], done: false, errorStep: null });
    const setStep = (idx, state) => setCouncilProgress((prev) => {
      if (!prev) return prev;
      const steps = [...prev.steps];
      steps[idx] = state;
      return { ...prev, steps };
    });
    try {
      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
      }));

      // Create a partial assistant message that will be updated progressively
      const assistantMessage = {
        role: 'assistant',
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        loading: {
          stage1: false,
          stage2: false,
          stage3: false,
        },
      };

      // Add the partial assistant message
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      // Send message with streaming (include advanced settings)
      await api.sendMessageStream(currentConversationId, content, (eventType, event) => {
        switch (eventType) {
          case 'stage1_start':
            setStep(0, 'active');
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage1 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage1_complete':
            setStep(0, 'done');
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage1 = event.data;
              lastMsg.loading.stage1 = false;
              return { ...prev, messages };
            });
            break;

          case 'stage2_start':
            setStep(1, 'active');
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage2 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage2_complete':
            setStep(1, 'done');
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage2 = event.data;
              lastMsg.metadata = event.metadata;
              lastMsg.loading.stage2 = false;
              return { ...prev, messages };
            });
            break;

          case 'stage3_start':
            setStep(2, 'active');
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage3 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage3_complete':
            setStep(2, 'done');
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage3 = event.data;
              lastMsg.loading.stage3 = false;
              return { ...prev, messages };
            });
            break;

          case 'title_complete':
            // Reload conversations to get updated title
            loadConversations();
            break;

          case 'complete':
            // Stream complete, reload conversations list + refresh credit balance
            setCouncilProgress((prev) => (prev ? { ...prev, steps: ['done', 'done', 'done'], done: true } : prev));
            loadConversations();
            refresh();
            setIsLoading(false);
            break;

          case 'error':
            console.error('Stream error:', event.message);
            setCouncilProgress((prev) => {
              if (!prev) return prev;
              const steps = [...prev.steps];
              const i = steps.findIndex((s) => s !== 'done');
              if (i >= 0) steps[i] = 'error';
              return { ...prev, steps, errorStep: i };
            });
            showToast(event.message || t('toast.genericError'), 'error');
            if (event.refunded) refresh();
            setIsLoading(false);
            break;

          default:
            console.log('Unknown event type:', eventType);
        }
      }, includeDocuments, advancedSettings);
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove optimistic messages on error
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      // Clear the progress bar on a hard failure (request rejected, 402, network).
      setCouncilProgress(null);
      setIsLoading(false);
      if (error.status === 402) {
        const d = error.detail || {};
        setCreditsModal({ required: d.required, balance: d.balance });
      } else {
        showToast(error.message || t('toast.sendFailed'), 'error');
      }
    }
  };

  const handleConfigUpdate = () => {
    checkConfiguration();
    loadCouncilConfig();
  };

  const handleAdvancedSettingsChange = (newSettings) => {
    setAdvancedSettings(newSettings);
  };

  const handleDocumentUpload = async (file) => {
    try {
      const result = await api.uploadDocument(file);
      await loadDocuments();
      showToast(t('toast.uploadSuccess', { name: file.name }), 'success');
      return result;
    } catch (error) {
      showToast(error.message || t('toast.uploadFailed'), 'error');
      throw error;
    }
  };

  const handleDocumentDelete = async (docId) => {
    try {
      await api.deleteDocument(docId);
      await loadDocuments();
      showToast(t('toast.documentDeleted'), 'success');
    } catch (error) {
      showToast(t('toast.deleteDocumentFailed'), 'error');
    }
  };

  const handleDocumentToggle = async (docId, isActive) => {
    try {
      await api.toggleDocument(docId, isActive);
      await loadDocuments();
    } catch (error) {
      showToast(t('toast.toggleDocumentFailed'), 'error');
    }
  };

  return (
    <div className="app-shell">
      <AppHeader />
      <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
        currentView={currentView}
        onViewChange={setCurrentView}
        isConfigured={isConfigured}
        isAdmin={isAdmin}
        onOpenAdvanced={() => setShowAdvancedPanel(true)}
        advancedMode={advancedSettings.mode}
      />
      
      {currentView === 'settings' ? (
        <Settings
          isAdmin={isAdmin}
          onConfigUpdate={handleConfigUpdate}
          showToast={showToast}
        />
      ) : (
        <ChatInterface
          conversation={currentConversation}
          onSendMessage={handleSendMessage}
          isLoading={isLoading}
          isConfigured={isConfigured}
          onGoToSettings={() => setCurrentView('settings')}
          documents={documents}
          onDocumentUpload={handleDocumentUpload}
          onDocumentDelete={handleDocumentDelete}
          onDocumentToggle={handleDocumentToggle}
          councilProgress={councilProgress}
        />
      )}

      {/* Advanced Panel (admin only) */}
      {showAdvancedPanel && isAdmin && (
        <AdvancedPanel
          onClose={() => setShowAdvancedPanel(false)}
          onSettingsChange={handleAdvancedSettingsChange}
          councilModels={councilModels}
          chairmanModel={chairmanModel}
          showToast={showToast}
        />
      )}

      {/* Toast Notifications */}
      {toast && (
        <div className={`toast toast-${toast.type}`} data-testid="toast-notification">
          {toast.message}
        </div>
      )}

      {/* Insufficient credits modal */}
      {creditsModal && (
        <div className="credits-modal-overlay" data-testid="insufficient-credits-modal">
          <div className="credits-modal">
            <h3>{t('creditsModal.title')}</h3>
            <p>
              <span dangerouslySetInnerHTML={{ __html: t('creditsModal.body', { required: `<strong>${creditsModal.required}</strong>`, balance: `<strong>${creditsModal.balance}</strong>` }) }} />
            </p>
            <div className="credits-modal-actions">
              <button className="cm-secondary" onClick={() => setCreditsModal(null)} data-testid="credits-modal-cancel">{t('creditsModal.cancel')}</button>
              <button className="cm-primary" onClick={() => navigate('/credits')} data-testid="credits-modal-buy">{t('creditsModal.buy')}</button>
            </div>
          </div>
        </div>
      )}
      </div>
      <AppFooter />

      {/* Startup Terms & Conditions gate */}
      {!termsAccepted && <TermsModal onAccept={() => setTermsAccepted(true)} />}
    </div>
  );
}

export default App;
