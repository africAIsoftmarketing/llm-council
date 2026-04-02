import { useState } from 'react';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onDeleteConversation,
  currentView,
  onViewChange,
  isConfigured,
  onOpenAdvanced,
  advancedMode,
}) {
  const [deleteConfirm, setDeleteConfirm] = useState(null);

  const handleDeleteClick = (e, convId) => {
    e.stopPropagation();
    if (deleteConfirm === convId) {
      onDeleteConversation(convId);
      setDeleteConfirm(null);
    } else {
      setDeleteConfirm(convId);
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  };

  const getModeLabel = (mode) => {
    switch (mode) {
      case 'openrouter': return 'OpenRouter';
      case 'lmstudio': return 'LM Studio';
      case 'hybrid': return 'Hybrid';
      default: return 'OpenRouter';
    }
  };

  const getModeColor = (mode) => {
    switch (mode) {
      case 'openrouter': return '#4a90e2';
      case 'lmstudio': return '#7c3aed';
      case 'hybrid': return '#f39c12';
      default: return '#4a90e2';
    }
  };

  return (
    <div className="sidebar" data-testid="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <div className="header-status-row">
          <div className="config-status">
            <span className={`status-dot ${isConfigured ? 'configured' : 'not-configured'}`}></span>
            <span>{isConfigured ? 'Ready' : 'Not Configured'}</span>
          </div>
          {advancedMode && (
            <button 
              className="mode-badge"
              style={{ background: getModeColor(advancedMode) }}
              onClick={onOpenAdvanced}
              title="Click to configure LLM source"
              data-testid="mode-badge"
            >
              {getModeLabel(advancedMode)}
            </button>
          )}
        </div>
      </div>

      <button 
        className="new-conversation-btn" 
        onClick={onNewConversation}
        data-testid="btn-new-conversation"
      >
        + New Conversation
      </button>

      <div className="sidebar-nav">
        <button
          className={`nav-btn ${currentView === 'chat' ? 'active' : ''}`}
          onClick={() => onViewChange('chat')}
          data-testid="nav-chat"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
          </svg>
          Chat
        </button>
        <button
          className={`nav-btn ${currentView === 'settings' ? 'active' : ''}`}
          onClick={() => onViewChange('settings')}
          data-testid="nav-settings"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <circle cx="12" cy="12" r="3"></circle>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
          </svg>
          Settings
        </button>
        <button
          className="nav-btn advanced-btn"
          onClick={onOpenAdvanced}
          data-testid="nav-advanced"
          title="Advanced LLM Configuration"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="4" y1="21" x2="4" y2="14"></line>
            <line x1="4" y1="10" x2="4" y2="3"></line>
            <line x1="12" y1="21" x2="12" y2="12"></line>
            <line x1="12" y1="8" x2="12" y2="3"></line>
            <line x1="20" y1="21" x2="20" y2="16"></line>
            <line x1="20" y1="12" x2="20" y2="3"></line>
            <line x1="1" y1="14" x2="7" y2="14"></line>
            <line x1="9" y1="8" x2="15" y2="8"></line>
            <line x1="17" y1="16" x2="23" y2="16"></line>
          </svg>
        </button>
      </div>

      <div className="conversation-list">
        <div className="list-header">Conversations</div>
        {conversations.length === 0 ? (
          <div className="no-conversations">No conversations yet</div>
        ) : (
          conversations.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${
                conv.id === currentConversationId && currentView === 'chat' ? 'active' : ''
              }`}
              onClick={() => onSelectConversation(conv.id)}
              data-testid={`conversation-${conv.id}`}
            >
              <div className="conversation-content">
                <div className="conversation-title">
                  {conv.title || 'New Conversation'}
                </div>
                <div className="conversation-meta">
                  {conv.message_count} message{conv.message_count !== 1 ? 's' : ''}
                </div>
              </div>
              <button
                className={`delete-btn ${deleteConfirm === conv.id ? 'confirm' : ''}`}
                onClick={(e) => handleDeleteClick(e, conv.id)}
                title={deleteConfirm === conv.id ? 'Click again to confirm' : 'Delete conversation'}
                data-testid={`delete-${conv.id}`}
              >
                {deleteConfirm === conv.id ? '✓' : '×'}
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
