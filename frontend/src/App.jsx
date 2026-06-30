import { useState, useEffect, useCallback } from 'react';
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

  const loadConversation = useCallback(async (id) => {
    try {
      const conv = await api.getConversation(id);
      const last = conv.messages[conv.messages.length - 1];
      // If the council is still running for this conversation, reconstruct the
      // loading flags from the persisted partial stages and resume the live stream.
      if (last && last.role === 'assistant' && last.status === 'running') {
        last.loading = {
          stage1: !last.stage1,
          stage2: !!last.stage1 && !last.stage2,
          stage3: !!last.stage2 && !last.stage3,
        };
        setCurrentConversation(conv);
        setIsLoading(true);
        // Resume in the background (don't block the load).
        api.resumeStream(id, makeEventHandler(id)).catch((err) => {
          console.error('Resume stream failed:', err);
          setIsLoading(false);
        });
      } else {
        setCurrentConversation(conv);
      }
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
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
        setCurrentConversationId(null);
        setCurrentConversation(null);
      }
      showToast('Conversation deleted', 'success');
    } catch (error) {
      console.error('Failed to delete conversation:', error);
      showToast('Failed to delete conversation', 'error');
    }
  };

  // Builds an SSE event handler bound to a conversation id. Used both for the
  // initial send and for resuming a running council after a page refresh.
  function makeEventHandler(convId) {
    const updateLast = (updater) => {
      setCurrentConversation((prev) => {
        if (!prev || prev.id !== convId) return prev;
        const messages = [...prev.messages];
        const lastMsg = messages[messages.length - 1];
        if (!lastMsg || lastMsg.role !== 'assistant') return prev;
        if (!lastMsg.loading) {
          lastMsg.loading = { stage1: false, stage2: false, stage3: false };
        }
        updater(lastMsg);
        return { ...prev, messages };
      });
    };

    return (eventType, event) => {
      switch (eventType) {
        case 'stage1_start':
          updateLast((m) => { m.loading.stage1 = true; });
          break;
        case 'stage1_complete':
          updateLast((m) => { m.stage1 = event.data; m.loading.stage1 = false; });
          break;
        case 'stage2_start':
          updateLast((m) => { m.loading.stage2 = true; });
          break;
        case 'stage2_complete':
          updateLast((m) => {
            m.stage2 = event.data;
            m.metadata = event.metadata;
            m.loading.stage2 = false;
          });
          break;
        case 'stage3_start':
          updateLast((m) => { m.loading.stage3 = true; });
          break;
        case 'stage3_complete':
          updateLast((m) => { m.stage3 = event.data; m.loading.stage3 = false; });
          break;
        case 'title_complete':
          loadConversations();
          break;
        case 'complete':
          loadConversations();
          setIsLoading(false);
          // Sync the final persisted state (covers resume-after-finish races).
          api.getConversation(convId)
            .then((conv) => {
              setCurrentConversation((prev) =>
                prev && prev.id === convId ? conv : prev
              );
            })
            .catch(() => {});
          break;
        case 'error':
          console.error('Stream error:', event.message);
          showToast(event.message || 'An error occurred', 'error');
          setIsLoading(false);
          break;
        default:
          break;
      }
    };
  }

  const handleSendMessage = async (content, includeDocuments = true) => {
    if (!currentConversationId) return;
    if (!isConfigured) {
      showToast('Please configure your OpenRouter API key in Settings first', 'warning');
      setCurrentView('settings');
      return;
    }

    setIsLoading(true);
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
      await api.sendMessageStream(
        currentConversationId,
        content,
        makeEventHandler(currentConversationId),
        includeDocuments,
        advancedSettings
      );
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
