import { useState, useRef } from 'react';
import './DocumentPanel.css';

export default function DocumentPanel({
  documents,
  onUpload,
  onDelete,
  onToggle,
  onClose,
}) {
  const [isUploading, setIsUploading] = useState(false);
  const [expandedDoc, setExpandedDoc] = useState(null);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const fileInputRef = useRef(null);

  const handleFileSelect = async (e) => {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;

    setIsUploading(true);
    try {
      for (const file of files) {
        await onUpload(file);
      }
    } catch (error) {
      console.error('Upload failed:', error);
    } finally {
      setIsUploading(false);
      e.target.value = '';
    }
  };

  const handleDelete = (docId) => {
    if (deleteConfirm === docId) {
      onDelete(docId);
      setDeleteConfirm(null);
    } else {
      setDeleteConfirm(docId);
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  };

  const formatFileSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  const getFileIcon = (extension) => {
    switch (extension) {
      case '.pdf':
        return (
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M13,9V3.5L18.5,9H13M10.92,12.31C10.68,11.54 10.15,9.08 11.55,9.04C12.95,9 12.03,12.16 12.03,12.16C12.42,13.65 14.05,14.72 14.05,14.72C14.55,14.57 17.4,14.24 17,15.72C16.57,17.2 13.5,15.81 13.5,15.81C11.55,15.95 10.09,16.47 10.09,16.47C8.96,18.58 7.64,19.5 7.1,18.61C6.43,17.5 9.23,16.07 9.23,16.07C10.68,13.72 10.9,12.35 10.92,12.31Z" />
          </svg>
        );
      case '.docx':
      case '.doc':
        return (
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M6,2H14L20,8V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V4A2,2 0 0,1 6,2M13,3.5V9H18.5L13,3.5M7,13L8.5,18H9.5L11,14.33L12.5,18H13.5L15,13H14L13,16.5L11.67,13H10.33L9,16.5L8,13H7Z" />
          </svg>
        );
      case '.txt':
      case '.md':
        return (
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M13,9V3.5L18.5,9H13M7,12H17V14H7V12M7,16H14V18H7V16Z" />
          </svg>
        );
      case '.pptx':
      case '.ppt':
        return (
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M6,2H14L20,8V20A2,2 0 0,1 18,22H6A2,2 0 0,1 4,20V4A2,2 0 0,1 6,2M13,3.5V9H18.5L13,3.5M8,11V13H9V19H8V20H11V19H10V17H11A3,3 0 0,0 14,14A3,3 0 0,0 11,11H8M11,13A1,1 0 0,1 12,14A1,1 0 0,1 11,15H10V13H11Z" />
          </svg>
        );
      case '.png':
      case '.jpg':
      case '.jpeg':
      case '.gif':
      case '.webp':
        return (
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M8.5,13.5L11,16.5L14.5,12L19,18H5M21,19V5A2,2 0 0,0 19,3H5A2,2 0 0,0 3,5V19A2,2 0 0,0 5,21H19A2,2 0 0,0 21,19Z" />
          </svg>
        );
      default:
        return (
          <svg viewBox="0 0 24 24" fill="currentColor">
            <path d="M14,2H6A2,2 0 0,0 4,4V20A2,2 0 0,0 6,22H18A2,2 0 0,0 20,20V8L14,2M13,9V3.5L18.5,9H13Z" />
          </svg>
        );
    }
  };

  return (
    <div className="document-panel" data-testid="document-panel">
      <div className="panel-header">
        <h3>Documents</h3>
        <button className="close-btn" onClick={onClose}>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>

      <div className="panel-content">
        {/* Upload Section */}
        <div className="upload-section">
          <button
            className="upload-area"
            onClick={() => fileInputRef.current?.click()}
            disabled={isUploading}
            data-testid="btn-upload-area"
          >
            {isUploading ? (
              <>
                <div className="spinner"></div>
                <span>Uploading...</span>
              </>
            ) : (
              <>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
                  <polyline points="17 8 12 3 7 8"></polyline>
                  <line x1="12" y1="3" x2="12" y2="15"></line>
                </svg>
                <span>Click to upload documents</span>
                <span className="upload-hint">PDF, DOCX, TXT, PPTX, Images</span>
              </>
            )}
          </button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            multiple
            accept=".pdf,.docx,.doc,.txt,.rtf,.pptx,.ppt,.png,.jpg,.jpeg,.gif,.webp,.md"
            style={{ display: 'none' }}
          />
        </div>

        {/* Documents List */}
        <div className="documents-list">
          {documents.length === 0 ? (
            <div className="no-documents">
              <p>No documents uploaded yet</p>
              <p className="hint">Upload documents to include them in your LLM Council queries</p>
            </div>
          ) : (
            documents.map((doc) => (
              <div
                key={doc.id}
                className={`document-item ${doc.is_active ? 'active' : 'inactive'}`}
                data-testid={`document-${doc.id}`}
              >
                <div className="doc-icon" style={{ color: doc.is_active ? '#4a90e2' : '#999' }}>
                  {getFileIcon(doc.extension)}
                </div>
                
                <div className="doc-info">
                  <div className="doc-name">{doc.filename}</div>
                  <div className="doc-meta">
                    <span>{formatFileSize(doc.size)}</span>
                    <span>•</span>
                    <span>{doc.text_length.toLocaleString()} chars</span>
                    <span>•</span>
                    <span>{doc.chunk_count} chunk{doc.chunk_count !== 1 ? 's' : ''}</span>
                    {doc.is_vision_image && (
                      <>
                        <span>•</span>
                        <span className="vision-badge" title="Image will be analyzed by vision-capable AI models">
                          <svg viewBox="0 0 24 24" fill="currentColor" width="14" height="14" style={{marginRight: '4px', verticalAlign: 'middle'}}>
                            <path d="M12,9A3,3 0 0,0 9,12A3,3 0 0,0 12,15A3,3 0 0,0 15,12A3,3 0 0,0 12,9M12,17A5,5 0 0,1 7,12A5,5 0 0,1 12,7A5,5 0 0,1 17,12A5,5 0 0,1 12,17M12,4.5C7,4.5 2.73,7.61 1,12C2.73,16.39 7,19.5 12,19.5C17,19.5 21.27,16.39 23,12C21.27,7.61 17,4.5 12,4.5Z" />
                          </svg>
                          Vision
                        </span>
                      </>
                    )}
                  </div>
                </div>

                <div className="doc-actions">
                  <label className="toggle-switch" title={doc.is_active ? 'Included in context' : 'Not included'}>
                    <input
                      type="checkbox"
                      checked={doc.is_active}
                      onChange={(e) => onToggle(doc.id, e.target.checked)}
                    />
                    <span className="toggle-slider"></span>
                  </label>
                  
                  <button
                    className="expand-btn"
                    onClick={() => setExpandedDoc(expandedDoc === doc.id ? null : doc.id)}
                    title="Preview content"
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      {expandedDoc === doc.id ? (
                        <polyline points="18 15 12 9 6 15"></polyline>
                      ) : (
                        <polyline points="6 9 12 15 18 9"></polyline>
                      )}
                    </svg>
                  </button>
                  
                  <button
                    className={`delete-btn ${deleteConfirm === doc.id ? 'confirm' : ''}`}
                    onClick={() => handleDelete(doc.id)}
                    title={deleteConfirm === doc.id ? 'Click again to confirm' : 'Delete document'}
                  >
                    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <polyline points="3 6 5 6 21 6"></polyline>
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                  </button>
                </div>

                {expandedDoc === doc.id && (
                  <div className="doc-preview">
                    <div className="preview-label">Content Preview:</div>
                    <div className="preview-content">
                      {doc.preview || 'No preview available'}
                    </div>
                  </div>
                )}
              </div>
            ))
          )}
        </div>
      </div>

      <div className="panel-footer">
        <div className="footer-stats">
          <span>{documents.filter(d => d.is_active).length} of {documents.length} active</span>
        </div>
      </div>
    </div>
  );
}
