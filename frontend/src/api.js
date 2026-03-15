/**
 * API client for the LLM Council backend.
 * Uses relative URLs when served from the same origin (production),
 * or REACT_APP_BACKEND_URL/VITE_BACKEND_URL in development.
 */

// Use environment variable if set, otherwise use relative URL (empty string)
// This ensures proper routing through Kubernetes ingress
const API_BASE = import.meta.env.VITE_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL || '';

export const api = {
  // ===== Configuration APIs =====
  
  /**
   * Get current configuration.
   */
  async getConfig() {
    const response = await fetch(`${API_BASE}/api/config`);
    if (!response.ok) {
      throw new Error('Failed to get configuration');
    }
    return response.json();
  },

  /**
   * Update configuration.
   */
  async updateConfig(config) {
    const response = await fetch(`${API_BASE}/api/config`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    });
    if (!response.ok) {
      throw new Error('Failed to update configuration');
    }
    return response.json();
  },

  /**
   * Validate OpenRouter API key.
   */
  async validateApiKey(apiKey) {
    const response = await fetch(`${API_BASE}/api/config/validate-key`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ api_key: apiKey }),
    });
    if (!response.ok) {
      throw new Error('Failed to validate API key');
    }
    return response.json();
  },

  /**
   * Get available models.
   */
  async getAvailableModels() {
    const response = await fetch(`${API_BASE}/api/models/available`);
    if (!response.ok) {
      throw new Error('Failed to get available models');
    }
    return response.json();
  },

  /**
   * Add a custom model.
   */
  async addCustomModel(modelId, modelName, provider) {
    const response = await fetch(`${API_BASE}/api/models/custom`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ model_id: modelId, model_name: modelName, provider }),
    });
    if (!response.ok) {
      throw new Error('Failed to add custom model');
    }
    return response.json();
  },

  // ===== LM Studio APIs =====

  /**
   * Test LM Studio connection.
   */
  async testLmStudioConnection(url, modelName = null) {
    const response = await fetch(`${API_BASE}/api/lm-studio/test`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ url, model_name: modelName }),
    });
    if (!response.ok) {
      throw new Error('Failed to test LM Studio connection');
    }
    return response.json();
  },

  /**
   * Get all configured LM Studio URLs.
   */
  async getLmStudioUrls() {
    const response = await fetch(`${API_BASE}/api/lm-studio/urls`);
    if (!response.ok) {
      throw new Error('Failed to get LM Studio URLs');
    }
    return response.json();
  },

  // ===== Document APIs =====

  /**
   * Get all documents.
   */
  async getDocuments() {
    const response = await fetch(`${API_BASE}/api/documents`);
    if (!response.ok) {
      throw new Error('Failed to get documents');
    }
    return response.json();
  },

  /**
   * Upload a document.
   */
  async uploadDocument(file, onProgress) {
    const formData = new FormData();
    formData.append('file', file);

    const response = await fetch(`${API_BASE}/api/documents/upload`, {
      method: 'POST',
      body: formData,
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to upload document');
    }
    return response.json();
  },

  /**
   * Get document details.
   */
  async getDocument(docId) {
    const response = await fetch(`${API_BASE}/api/documents/${docId}`);
    if (!response.ok) {
      throw new Error('Failed to get document');
    }
    return response.json();
  },

  /**
   * Delete a document.
   */
  async deleteDocument(docId) {
    const response = await fetch(`${API_BASE}/api/documents/${docId}`, {
      method: 'DELETE',
    });
    if (!response.ok) {
      throw new Error('Failed to delete document');
    }
    return response.json();
  },

  /**
   * Toggle document active status.
   */
  async toggleDocument(docId, isActive) {
    const response = await fetch(`${API_BASE}/api/documents/${docId}/toggle`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ is_active: isActive }),
    });
    if (!response.ok) {
      throw new Error('Failed to toggle document');
    }
    return response.json();
  },

  /**
   * Get supported file types.
   */
  async getSupportedTypes() {
    const response = await fetch(`${API_BASE}/api/documents/supported-types`);
    if (!response.ok) {
      throw new Error('Failed to get supported types');
    }
    return response.json();
  },

  /**
   * Get document processing status (useful for OCR tracking).
   */
  async getDocumentStatus(docId) {
    const response = await fetch(`${API_BASE}/api/documents/${docId}/status`);
    if (!response.ok) {
      throw new Error('Failed to get document status');
    }
    return response.json();
  },

  /**
   * Get OCR engine status.
   */
  async getOcrStatus() {
    const response = await fetch(`${API_BASE}/api/ocr/status`);
    if (!response.ok) {
      throw new Error('Failed to get OCR status');
    }
    return response.json();
  },

  // ===== Conversation APIs =====

  /**
   * List all conversations.
   */
  async listConversations() {
    const response = await fetch(`${API_BASE}/api/conversations`);
    if (!response.ok) {
      throw new Error('Failed to list conversations');
    }
    return response.json();
  },

  /**
   * Create a new conversation.
   */
  async createConversation() {
    const response = await fetch(`${API_BASE}/api/conversations`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({}),
    });
    if (!response.ok) {
      throw new Error('Failed to create conversation');
    }
    return response.json();
  },

  /**
   * Get a specific conversation.
   */
  async getConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`
    );
    if (!response.ok) {
      throw new Error('Failed to get conversation');
    }
    return response.json();
  },

  /**
   * Delete a conversation.
   */
  async deleteConversation(conversationId) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}`,
      { method: 'DELETE' }
    );
    if (!response.ok) {
      throw new Error('Failed to delete conversation');
    }
    return response.json();
  },

  /**
   * Send a message in a conversation.
   */
  async sendMessage(conversationId, content, includeDocuments = true) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, include_documents: includeDocuments }),
      }
    );
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to send message');
    }
    return response.json();
  },

  /**
   * Send a message and receive streaming updates.
   * @param {string} conversationId - The conversation ID
   * @param {string} content - The message content
   * @param {function} onEvent - Callback function for each event: (eventType, data) => void
   * @param {boolean} includeDocuments - Whether to include document context
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent, includeDocuments = true) {
    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ content, include_documents: includeDocuments }),
      }
    );

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to send message');
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const data = line.slice(6);
          try {
            const event = JSON.parse(data);
            onEvent(event.type, event);
          } catch (e) {
            console.error('Failed to parse SSE event:', e);
          }
        }
      }
    }
  },

  // ===== Health Check =====

  /**
   * Check backend health and configuration status.
   */
  async healthCheck() {
    try {
      const response = await fetch(`${API_BASE}/api/health`);
      if (!response.ok) {
        return { status: 'error', configured: false };
      }
      return response.json();
    } catch (error) {
      return { status: 'error', configured: false, error: error.message };
    }
  },
};
