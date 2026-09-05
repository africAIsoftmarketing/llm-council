import { useState, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import DocumentPanel from './DocumentPanel';
import CouncilProgress from './CouncilProgress';
import HowItWorks from './HowItWorks';
import productLogo from '../assets/logo-product.jpg';
import './ChatInterface.css';

export default function ChatInterface({
  conversation,
  onSendMessage,
  isLoading,
  isConfigured,
  onGoToSettings,
  documents,
  onDocumentUpload,
  onDocumentDelete,
  onDocumentToggle,
  councilProgress,
}) {
  const [input, setInput] = useState('');
  const [showDocuments, setShowDocuments] = useState(false);
  const [includeDocuments, setIncludeDocuments] = useState(true);
  const [isDragging, setIsDragging] = useState(false);
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const { t } = useTranslation();

  const activeDocuments = documents?.filter(d => d.is_active) || [];

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input, includeDocuments);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleDragOver = (e) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = async (e) => {
    e.preventDefault();
    setIsDragging(false);
    
    const files = Array.from(e.dataTransfer.files);
    for (const file of files) {
      try {
        await onDocumentUpload(file);
      } catch (error) {
        console.error('Failed to upload:', file.name);
      }
    }
  };

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files);
    for (const file of files) {
      try {
        await onDocumentUpload(file);
      } catch (error) {
        console.error('Failed to upload:', file.name);
      }
    }
    // Reset input
    e.target.value = '';
  };

  // Not configured state
  if (!isConfigured) {
    return (
      <div className="chat-interface">
        <div className="not-configured-state">
          <div className="not-configured-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="3"></circle>
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
            </svg>
          </div>
          <h2>{t('chat.configRequired')}</h2>
          <p>{t('chat.configRequiredDesc')}</p>
          <button onClick={onGoToSettings} className="go-to-settings-btn" data-testid="btn-go-to-settings">
            {t('chat.goToSettings')}
          </button>
        </div>
      </div>
    );
  }

  // No conversation selected
  if (!conversation) {
    return (
      <div 
        className="chat-interface"
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {isDragging && (
          <div className="drop-overlay">
            <div className="drop-content">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                <polyline points="17 8 12 3 7 8"></polyline>
                <line x1="12" y1="3" x2="12" y2="15"></line>
              </svg>
              <span>{t('chat.dropFiles')}</span>
            </div>
          </div>
        )}
        <div className="empty-state welcome-state" data-testid="welcome-screen">
          <img src={productLogo} alt={t('header.logoAlt')} className="welcome-logo" />
          <h2>{t('chat.welcomeTitle')}</h2>
          <p>{t('chat.welcomeSubtitle')}</p>
          {documents?.length > 0 && (
            <div className="documents-hint">
              <span>{t('chat.docsReady', { count: activeDocuments.length })}</span>
            </div>
          )}
          <HowItWorks />
        </div>
      </div>
    );
  }

  return (
    <div 
      className="chat-interface"
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
      data-testid="chat-interface"
    >
      {isDragging && (
        <div className="drop-overlay">
          <div className="drop-content">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="17 8 12 3 7 8"></polyline>
              <line x1="12" y1="3" x2="12" y2="15"></line>
            </svg>
            <span>{t('chat.dropFiles')}</span>
          </div>
        </div>
      )}

      {/* Document Panel Toggle */}
      {documents?.length > 0 && (
        <button 
          className={`documents-toggle ${showDocuments ? 'active' : ''}`}
          onClick={() => setShowDocuments(!showDocuments)}
          data-testid="btn-toggle-documents"
        >
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
          </svg>
          <span>{t('chat.activeCount', { count: activeDocuments.length })}</span>
        </button>
      )}

      {/* Document Panel */}
      {showDocuments && (
        <DocumentPanel
          documents={documents}
          onUpload={onDocumentUpload}
          onDelete={onDocumentDelete}
          onToggle={onDocumentToggle}
          onClose={() => setShowDocuments(false)}
        />
      )}

      <div className="messages-container">
        {/* Live per-stage council progress (driven by SSE events) */}
        {councilProgress && <CouncilProgress progress={councilProgress} />}
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>{t('chat.startConversation')}</h2>
            <p>{t('chat.askQuestion')}</p>
            {activeDocuments.length > 0 && (
              <div className="documents-context-hint">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                  <polyline points="14 2 14 8 20 8"></polyline>
                </svg>
                <span>{t('chat.docsInQuery', { count: activeDocuments.length })}</span>
              </div>
            )}
          </div>
        ) : (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">{t('chat.you')}</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">{t('chat.assistantLabel')}</div>

                  {/* Stage 1 */}
                  {msg.loading?.stage1 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>{t('chat.running1')}</span>
                    </div>
                  )}
                  {msg.stage1 && <Stage1 responses={msg.stage1} />}

                  {/* Stage 2 */}
                  {msg.loading?.stage2 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>{t('chat.running2')}</span>
                    </div>
                  )}
                  {msg.stage2 && (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                    />
                  )}

                  {/* Stage 3 */}
                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>{t('chat.running3')}</span>
                    </div>
                  )}
                  {msg.stage3 && (
                    <Stage3
                      finalResponse={msg.stage3}
                      stage1Responses={msg.stage1}
                      stage2Rankings={msg.stage2}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                      labelToModel={msg.metadata?.label_to_model}
                    />
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && conversation.messages.length === 0 && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>{t('chat.consulting')}</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input Form - Only show when conversation is empty */}
      {conversation.messages.length === 0 && (
        <div className="input-area">
          {/* Document Context Indicator */}
          {activeDocuments.length > 0 && (
            <div className="document-context-bar">
              <label className="include-docs-toggle">
                <input
                  type="checkbox"
                  checked={includeDocuments}
                  onChange={(e) => setIncludeDocuments(e.target.checked)}
                  data-testid="checkbox-include-docs"
                />
                <span>{t('chat.includeDocs', { count: activeDocuments.length })}</span>
              </label>
              <button 
                className="manage-docs-btn"
                onClick={() => setShowDocuments(true)}
              >
                {t('chat.manage')}
              </button>
            </div>
          )}

          <form className="input-form" onSubmit={handleSubmit}>
            <div className="input-row">
              <button
                type="button"
                className="upload-btn"
                onClick={() => fileInputRef.current?.click()}
                title={t('chat.uploadTitle')}
                data-testid="btn-upload-document"
              >
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="17 8 12 3 7 8"></polyline>
                  <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
              </button>
              <textarea
                className="message-input"
                placeholder={t('chat.placeholder')}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                disabled={isLoading}
                rows={3}
                data-testid="input-message"
              />
              <button
                type="submit"
                className="send-button"
                disabled={!input.trim() || isLoading}
                data-testid="btn-send"
              >
                {t('chat.send')}
              </button>
            </div>
          </form>

          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            multiple
            accept=".pdf,.docx,.doc,.txt,.rtf,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.webp,.md"
            style={{ display: 'none' }}
          />
        </div>
      )}
    </div>
  );
}
