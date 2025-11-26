import { useState, useEffect, useCallback } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import Settings from './components/Settings';
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
    // eslint-disable-next-line react-hooks/set-state-in-effect
    loadDocuments();
  }, [checkConfiguration, loadDocuments]);

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

      // Send message with streaming
      await api.sendMessageStream(currentConversationId, content, (eventType, event) => {
        switch (eventType) {
          case 'stage1_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage1 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage1_complete':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.stage1 = event.data;
              lastMsg.loading.stage1 = false;
              return { ...prev, messages };
            });
            break;

          case 'stage2_start':
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage2 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage2_complete':
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
            setCurrentConversation((prev) => {
              const messages = [...prev.messages];
              const lastMsg = messages[messages.length - 1];
              lastMsg.loading.stage3 = true;
              return { ...prev, messages };
            });
            break;

          case 'stage3_complete':
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
            // Stream complete, reload conversations list
            loadConversations();
            setIsLoading(false);
            break;

          case 'error':
            console.error('Stream error:', event.message);
            showToast(event.message || 'An error occurred', 'error');
            setIsLoading(false);
            break;

          default:
            console.log('Unknown event type:', eventType);
        }
      }, includeDocuments);
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

      {/* Toast Notifications */}
      {toast && (
        <div className={`toast toast-${toast.type}`} data-testid="toast-notification">
          {toast.message}
        </div>
      )}
    </div>
  );
}

export default App;
