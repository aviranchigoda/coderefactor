const { contextBridge, ipcRenderer } = require('electron');

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld('electronAPI', {
  // Project management
  scanProject: (projectPath) => ipcRenderer.invoke('scan-project', projectPath),
  openProjectDialog: () => ipcRenderer.invoke('open-project-dialog'),
  getProjectInfo: () => ipcRenderer.invoke('get-project-info'),
  
  // Graph operations
  getGraph: () => ipcRenderer.invoke('get-graph'),
  getGraphStats: () => ipcRenderer.invoke('get-graph-stats'),
  clearGraph: () => ipcRenderer.invoke('clear-graph'),
  
  // File operations
  getFileTree: (projectPath) => ipcRenderer.invoke('get-file-tree', projectPath),
  getFileContent: (filePath) => ipcRenderer.invoke('get-file-content', filePath),
  saveFile: (filePath, content) => ipcRenderer.invoke('save-file', filePath, content),
  
  // Refactoring operations
  getRefactoringCandidates: (pattern) => ipcRenderer.invoke('get-refactoring-candidates', pattern),
  applyRefactoring: (nodeId, refactorType, options) => 
    ipcRenderer.invoke('apply-refactoring', nodeId, refactorType, options),
  previewRefactoring: (nodeId, refactorType, options) => 
    ipcRenderer.invoke('preview-refactoring', nodeId, refactorType, options),
  
  // Lint operations
  getLintErrors: (filePath) => ipcRenderer.invoke('get-lint-errors', filePath),
  runLinting: (projectPath, language) => ipcRenderer.invoke('run-linting', projectPath, language),
  
  // Analysis operations
  analyzeCode: (filePath) => ipcRenderer.invoke('analyze-code', filePath),
  getCallGraph: (entityId) => ipcRenderer.invoke('get-call-graph', entityId),
  findUsages: (entityId) => ipcRenderer.invoke('find-usages', entityId),
  
  // Backend communication
  getBackendStatus: () => ipcRenderer.invoke('get-backend-status'),
  restartBackend: () => ipcRenderer.invoke('restart-backend'),
  
  // Application operations
  getAppVersion: () => ipcRenderer.invoke('get-app-version'),
  openExternal: (url) => ipcRenderer.invoke('open-external', url),
  showMessageBox: (options) => ipcRenderer.invoke('show-message-box', options),
  
  // Window operations
  minimizeWindow: () => ipcRenderer.invoke('minimize-window'),
  maximizeWindow: () => ipcRenderer.invoke('maximize-window'),
  closeWindow: () => ipcRenderer.invoke('close-window'),
  isWindowMaximized: () => ipcRenderer.invoke('is-window-maximized'),
  
  // Settings operations
  getSettings: () => ipcRenderer.invoke('get-settings'),
  updateSettings: (settings) => ipcRenderer.invoke('update-settings', settings),
  resetSettings: () => ipcRenderer.invoke('reset-settings'),
  
  // Event listeners
  onBackendLog: (callback) => {
    ipcRenderer.on('backend-log', (event, data) => callback(data));
    return () => ipcRenderer.removeAllListeners('backend-log');
  },
  
  onBackendStatus: (callback) => {
    ipcRenderer.on('backend-status', (event, data) => callback(data));
    return () => ipcRenderer.removeAllListeners('backend-status');
  },
  
  onBackendError: (callback) => {
    ipcRenderer.on('backend-error', (event, data) => callback(data));
    return () => ipcRenderer.removeAllListeners('backend-error');
  },
  
  onWindowStateChanged: (callback) => {
    ipcRenderer.on('window-state-changed', (event, data) => callback(data));
    return () => ipcRenderer.removeAllListeners('window-state-changed');
  },
  
  onProgressUpdate: (callback) => {
    ipcRenderer.on('progress-update', (event, data) => callback(data));
    return () => ipcRenderer.removeAllListeners('progress-update');
  },
  
  // Utility functions
  selectDirectory: () => ipcRenderer.invoke('select-directory'),
  selectFile: (filters) => ipcRenderer.invoke('select-file', filters),
  saveFileDialog: (defaultPath, filters) => 
    ipcRenderer.invoke('save-file-dialog', defaultPath, filters),
  
  // Development helpers (only available in development mode)
  ...(process.env.NODE_ENV === 'development' && {
    openDevTools: () => ipcRenderer.invoke('open-dev-tools'),
    reloadApp: () => ipcRenderer.invoke('reload-app'),
    clearCache: () => ipcRenderer.invoke('clear-cache')
  })
});

// Expose a limited set of Node.js APIs for the renderer
contextBridge.exposeInMainWorld('nodeAPI', {
  platform: process.platform,
  arch: process.arch,
  versions: {
    node: process.versions.node,
    chrome: process.versions.chrome,
    electron: process.versions.electron
  },
  env: {
    NODE_ENV: process.env.NODE_ENV
  }
});

// Security: Remove dangerous globals
delete window.require;
delete window.exports;
delete window.module;

// Add some security headers
window.addEventListener('DOMContentLoaded', () => {
  // Prevent drag and drop of files
  document.addEventListener('dragover', (e) => e.preventDefault());
  document.addEventListener('drop', (e) => e.preventDefault());
  
  // Prevent right-click context menu in production
  if (process.env.NODE_ENV === 'production') {
    document.addEventListener('contextmenu', (e) => e.preventDefault());
  }
});

// Error handling
window.addEventListener('error', (event) => {
  console.error('Renderer error:', event.error);
  ipcRenderer.send('renderer-error', {
    message: event.error.message,
    stack: event.error.stack,
    filename: event.filename,
    lineno: event.lineno,
    colno: event.colno
  });
});

window.addEventListener('unhandledrejection', (event) => {
  console.error('Unhandled promise rejection:', event.reason);
  ipcRenderer.send('renderer-error', {
    message: 'Unhandled promise rejection',
    reason: event.reason?.toString() || 'Unknown reason'
  });
});