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
   * Get the current user's personal council selection (or global default).
   */
  async getUserCouncil() {
    const response = await fetch(`${API_BASE}/api/config/council`, { credentials: 'include' });
    if (!response.ok) {
      throw new Error('Failed to get user council');
    }
    return response.json();
  },

  /**
   * Save the current user's personal council selection.
   */
  async updateUserCouncil(councilModels, chairmanModel) {
    const response = await fetch(`${API_BASE}/api/config/council`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ council_models: councilModels, chairman_model: chairmanModel }),
    });
    if (!response.ok) {
      let detail;
      try { detail = (await response.json()).detail; } catch { /* noop */ }
      throw new Error(typeof detail === 'string' ? detail : 'Failed to save user council');
    }
    return response.json();
  },

  /**
   * Reset the current user's council back to the global default.
   */
  async resetUserCouncil() {
    const response = await fetch(`${API_BASE}/api/config/council`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!response.ok) {
      throw new Error('Failed to reset user council');
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

  /**
   * Edit a catalogue model (OpenRouter id, optional name/provider).
   */
  async updateCatalogModel(modelId, payload) {
    const response = await fetch(`${API_BASE}/api/models/custom/${encodeURIComponent(modelId)}`, {
      method: 'PUT',
      credentials: 'include',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    if (!response.ok) {
      let detail;
      try { detail = (await response.json()).detail; } catch { /* noop */ }
      throw new Error(typeof detail === 'string' ? detail : 'Failed to update model');
    }
    return response.json();
  },

  /**
   * Delete a catalogue model.
   */
  async deleteCatalogModel(modelId) {
    const response = await fetch(`${API_BASE}/api/models/custom/${encodeURIComponent(modelId)}`, {
      method: 'DELETE',
      credentials: 'include',
    });
    if (!response.ok) {
      let detail;
      try { detail = (await response.json()).detail; } catch { /* noop */ }
      throw new Error(typeof detail === 'string' ? detail : 'Failed to delete model');
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

  // ===== Advanced Config APIs =====

  /**
   * Get advanced LLM configuration.
   */
  async getAdvancedConfig() {
    const response = await fetch(`${API_BASE}/api/config/advanced`);
    if (!response.ok) {
      throw new Error('Failed to get advanced config');
    }
    return response.json();
  },

  /**
   * Save advanced LLM configuration.
   */
  async saveAdvancedConfig(advancedConfig) {
    const response = await fetch(`${API_BASE}/api/config/advanced`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(advancedConfig),
    });
    if (!response.ok) {
      throw new Error('Failed to save advanced config');
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
   * @param {object} advancedSettings - Advanced LLM configuration settings
   * @returns {Promise<void>}
   */
  async sendMessageStream(conversationId, content, onEvent, includeDocuments = true, advancedSettings = null) {
    // Build request body
    const body = { 
      content, 
      include_documents: includeDocuments,
    };

    // Include advanced settings if provided and not using default openrouter mode
    if (advancedSettings) {
      body.advanced = advancedSettings;
    }

    const response = await fetch(
      `${API_BASE}/api/conversations/${conversationId}/message/stream`,
      {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(body),
      }
    );

    if (!response.ok) {
      let detail;
      try { detail = (await response.json()).detail; } catch { /* noop */ }
      const err = new Error(typeof detail === 'string' ? detail : 'request_failed');
      err.status = response.status;
      err.detail = detail;
      throw err;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    // Robust SSE parsing with a persistent buffer.
    // On Heroku, SSE events (especially the large `stage1_complete` payload) can be
    // split across multiple TCP chunks. We must never JSON.parse a partial line, so
    // we accumulate decoded text and only process complete events separated by a
    // blank line (\n\n), keeping any trailing partial data in `buffer`.
    let buffer = '';

    const dispatchEvent = (rawEvent) => {
      // An SSE event may span several `data:` lines; concatenate their payloads.
      // Lines starting with `:` are comments/heartbeats and are ignored.
      const dataLines = [];
      for (const line of rawEvent.split('\n')) {
        if (line.startsWith('data:')) {
          // Strip the leading "data:" and an optional single space.
          dataLines.push(line.slice(line.startsWith('data: ') ? 6 : 5));
        }
      }
      if (dataLines.length === 0) return; // heartbeat / comment-only event
      const data = dataLines.join('\n');
      if (!data.trim()) return;
      try {
        const event = JSON.parse(data);
        onEvent(event.type, event);
      } catch (e) {
        console.error('Failed to parse SSE event:', e, data);
      }
    };

    const processBuffer = () => {
      // Normalize CRLF and process every complete event (terminated by a blank line).
      buffer = buffer.replace(/\r\n/g, '\n');
      let sepIndex;
      while ((sepIndex = buffer.indexOf('\n\n')) !== -1) {
        const rawEvent = buffer.slice(0, sepIndex);
        buffer = buffer.slice(sepIndex + 2);
        if (rawEvent.trim()) dispatchEvent(rawEvent);
      }
    };

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      // stream: true keeps multi-byte UTF-8 sequences intact across chunk boundaries.
      buffer += decoder.decode(value, { stream: true });
      processBuffer();
    }

    // Flush any remaining bytes and process a trailing event without a final blank line.
    buffer += decoder.decode();
    processBuffer();
    if (buffer.trim()) dispatchEvent(buffer);
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

const API_ROOT = import.meta.env.VITE_BACKEND_URL || import.meta.env.REACT_APP_BACKEND_URL || '';

async function jreq(path, options = {}) {
  const res = await fetch(`${API_ROOT}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let detail;
    try { detail = (await res.json()).detail; } catch { /* noop */ }
    const err = new Error(typeof detail === 'string' ? detail : `HTTP ${res.status}`);
    err.status = res.status;
    err.detail = detail;
    throw err;
  }
  if (res.status === 204) return null;
  return res.json();
}

export const authApi = {
  me: () => jreq('/api/auth/me'),
  devLogin: (email, name) => jreq('/api/auth/dev-login', { method: 'POST', body: JSON.stringify({ email, name }) }),
  loginUrl: () => `${API_ROOT}/api/auth/login`,
  logout: () => jreq('/api/auth/logout', { method: 'POST' }),
};

export const paymentsApi = {
  config: () => jreq('/api/payments/config'),
  packs: () => jreq('/api/payments/packs'),
  transactions: () => jreq('/api/payments/transactions'),
  createOrder: (packId) => jreq('/api/payments/orders', { method: 'POST', body: JSON.stringify({ pack_id: packId }) }),
  captureOrder: (orderId) => jreq(`/api/payments/orders/${orderId}/capture`, { method: 'POST' }),
};

export const adminApi = {
  getModels: () => jreq('/api/admin/models'),
  addModel: (modelId) => jreq('/api/admin/models', { method: 'POST', body: JSON.stringify({ model_id: modelId }) }),
  deleteModel: (modelId) => jreq(`/api/admin/models/${encodeURIComponent(modelId)}`, { method: 'DELETE' }),
  setChairman: (modelId) => jreq('/api/admin/chairman', { method: 'PUT', body: JSON.stringify({ model_id: modelId }) }),
  listUsers: (search = '', page = 1) => jreq(`/api/admin/users?search=${encodeURIComponent(search)}&page=${page}`),
  updateUser: (id, patch) => jreq(`/api/admin/users/${id}`, { method: 'PATCH', body: JSON.stringify(patch) }),
  adjustCredits: (id, amount, reason) => jreq(`/api/admin/users/${id}/credits`, { method: 'POST', body: JSON.stringify({ amount, reason }) }),
  getSettings: () => jreq('/api/admin/settings'),
  updateSetting: (key, value) => jreq(`/api/admin/settings/${key}`, { method: 'PUT', body: JSON.stringify({ value }) }),
  stats: () => jreq('/api/admin/stats'),
};
