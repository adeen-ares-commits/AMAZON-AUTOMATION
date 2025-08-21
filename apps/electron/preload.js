const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Dialog APIs
  showErrorDialog: (title, content) => ipcRenderer.invoke('show-error-dialog', title, content),
  showInfoDialog: (title, content) => ipcRenderer.invoke('show-info-dialog', title, content),
  showConfirmationDialog: (title, content) => ipcRenderer.invoke('show-confirmation-dialog', title, content),
  
  // Backend connection check
  checkBackendStatus: () => ipcRenderer.invoke('check-backend-status'),
  
  // Form submission
  submitForm: (payload) => ipcRenderer.invoke('submit-form', payload),
  submitFormWithFiles: (payload, detail) => ipcRenderer.invoke('submit-form-with-files', payload, detail),
  
  // CSV upload
  submitCsvUpload: (formData) => ipcRenderer.invoke('submit-csv-upload', formData),
  
  // Platform info
  platform: process.platform,
  
  // App version
  appVersion: process.env.npm_package_version || '1.0.0'
});

// Expose a safe version of console for debugging
contextBridge.exposeInMainWorld('electronConsole', {
  log: (...args) => console.log(...args),
  error: (...args) => console.error(...args),
  warn: (...args) => console.warn(...args),
  info: (...args) => console.info(...args)
});
