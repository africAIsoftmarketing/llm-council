import { useState, useEffect, useCallback, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import Settings from './components/Settings';
import AdvancedPanel, { getAdvancedSettings } from './components/AdvancedPanel';
import { api } from './api';
import './App.css';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [currentView, setCurrentView] = useState('chat'); // 'chat' or 'settings'
  const [isConfigured, setIsConfigured] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [toast, setToast] = useState(null);
  const [showAdvancedPanel, setShowAdvancedPanel] = useState(false);
  const [advancedSettings, setAdvancedSettings] = useState(() => getAdvancedSettings());
  const [councilModels, setCouncilModels] = useState([]);
  const [chairmanModel, setChairmanModel] = useState('');

  const checkConfiguration = useCallback(async () => {
    try {
      const health = await api.healthCheck();
      setIsConfigured(health.configured || false);
    } catch (error) {
      console.error('Failed to check configuration:', error);
      setIsConfigured(false);
    }
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
      setCouncilModels(config.council_models || []);
      setChairmanModel(config.chairman_model || '');
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

  // ===== Polling for in-progress council runs =====
  // Robust on Heroku: reads the incrementally-persisted state, so it survives
  // page refreshes AND SSE/proxy buffering. Stops when status != 'running'.
  const pollRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }, []);

  const startPolling = useCallback((id) => {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    setIsLoading(true);

    const tick = async () => {
      try {
        const conv = await api.getConversation(id);
        const l = conv.messages[conv.messages.length - 1];
        const running = l && l.role === 'assistant' && l.status === 'running';
        if (l && l.role === 'assistant') {
          l.loading = {
            stage1: running && !l.stage1,
            stage2: running && !!l.stage1 && !l.stage2,
            stage3: running && !!l.stage2 && !l.stage3,
          };
        }
        setCurrentConversation((prev) => (prev && prev.id === id ? conv : prev));
        if (!running) {
          if (pollRef.current) {
            clearInterval(pollRef.current);
            pollRef.current = null;
          }
          setIsLoading(false);
          loadConversations();
          if (l && l.status === 'error') {
            showToast(l.error || 'The council run failed', 'error');
          }
        }
      } catch (e) {
        // keep polling through transient network errors
      }
    };

    tick(); // fetch immediately, then every 2s
    pollRef.current = setInterval(tick, 2000);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadConversations]);

  const loadConversation = useCallback(async (id) => {
    try {
      const conv = await api.getConversation(id);
      const last = conv.messages[conv.messages.length - 1];
      // If the council is still running, show partial stages + start polling
      // to pick up the remaining stages as they are persisted.
      if (last && last.role === 'assistant' && last.status === 'running') {
        last.loading = {
          stage1: !last.stage1,
          stage2: !!last.stage1 && !last.stage2,
          stage3: !!last.stage2 && !last.stage3,
        };
        setCurrentConversation(conv);
        startPolling(id);
      } else {
        stopPolling();
        setCurrentConversation(conv);
      }
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  }, [startPolling, stopPolling]);

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
    if (!isConfigured) {
      showToast('Please configure your OpenRouter API key in Settings first', 'warning');
      setCurrentView('settings');
      return;
    }
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, title: newConv.title, message_count: 0 },
        ...conversations,
      ]);
      setCurrentConversationId(newConv.id);
      setCurrentView('chat');
    } catch (error) {
      console.error('Failed to create conversation:', error);
      showToast('Failed to create conversation', 'error');
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
    setCurrentView('chat');
  };

  const handleDeleteConversation = async (id) => {
    try {
      await api.deleteConversation(id);
      setConversations(conversations.filter(c => c.id !== id));
      if (currentConversationId === id) {
        stopPolling();
        setCurrentConversationId(null);
        setCurrentConversation(null);
      }
      showToast('Conversation deleted', 'success');
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      showToast('Failed to delete conversation', 'error');
    }
  };

  // Stop polling when the app unmounts
  useEffect(() => stopPolling, [stopPolling]);

  const handleSendMessage = async (content, includeDocuments = true) => {
    if (!currentConversationId) return;
    if (!isConfigured) {
      showToast('Please configure your OpenRouter API key in Settings first', 'warning');
      setCurrentView('settings');
      return;
    }

    setIsLoading(true);
    try {
      // Optimistically add user message + a running assistant placeholder.
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [
          ...prev.messages,
          { role: 'user', content },
          {
            role: 'assistant',
            status: 'running',
            stage1: null,
            stage2: null,
            stage3: null,
            metadata: null,
            loading: { stage1: true, stage2: false, stage3: false },
          },
        ],
      }));

      // Start the detached council run, then poll persisted progress.
      await api.startRun(
        currentConversationId,
        content,
        includeDocuments,
        advancedSettings
      );
      startPolling(currentConversationId);
    } catch (error) {
      console.error('Failed to send message:', error);
      showToast(error.message || 'Failed to send message', 'error');
      // Remove optimistic messages on error
      setCurrentConversation((prev) => ({
        ...prev,
        messages: prev.messages.slice(0, -2),
      }));
      setIsLoading(false);
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
      showToast(`Document "${file.name}" uploaded successfully`, 'success');
      return result;
    } catch (error) {
      showToast(error.message || 'Failed to upload document', 'error');
      throw error;
    }
  };

  const handleDocumentDelete = async (docId) => {
    try {
      await api.deleteDocument(docId);
      await loadDocuments();
      showToast('Document deleted', 'success');
    } catch (error) {
      showToast('Failed to delete document', 'error');
    }
  };

  const handleDocumentToggle = async (docId, isActive) => {
    try {
      await api.toggleDocument(docId, isActive);
      await loadDocuments();
    } catch (error) {
      showToast('Failed to toggle document', 'error');
    }
  };

  return (
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
        onOpenAdvanced={() => setShowAdvancedPanel(true)}
        advancedMode={advancedSettings.mode}
      />
      
      {currentView === 'chat' ? (
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
        />
      ) : (
        <Settings
          onConfigUpdate={handleConfigUpdate}
          showToast={showToast}
        />
      )}

      {/* Advanced Panel */}
      {showAdvancedPanel && (
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

      <footer className="app-footer" data-testid="app-footer">
        Powered by AfricAIsoft
      </footer>
    </div>
  );
}

export default App;
