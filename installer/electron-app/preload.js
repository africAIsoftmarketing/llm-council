/**
 * Preload script for LLM Council Desktop
 * Exposes safe APIs to the renderer process
 */

const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  // Configuration
  getConfig: () => ipcRenderer.invoke('get-config'),
  setConfig: (key, value) => ipcRenderer.invoke('set-config', key, value),
  
  // Service management
  restartServices: () => ipcRenderer.invoke('restart-services'),
  checkHealth: () => ipcRenderer.invoke('check-health'),
  
  // Utilities
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  getDataPath: () => ipcRenderer.invoke('get-data-path'),
  
  // App info
  platform: process.platform,
  version: process.env.npm_package_version || '2.0.0'
});
