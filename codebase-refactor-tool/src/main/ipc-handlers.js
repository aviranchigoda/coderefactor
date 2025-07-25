const { ipcMain, dialog, shell, app } = require('electron');
const fs = require('fs').promises;
const path = require('path');
const fetch = require('node-fetch');

// Backend API configuration
const BACKEND_BASE_URL = process.env.BACKEND_URL || 'http://localhost:5000';
const API_TIMEOUT = 30000; // 30 seconds

let mainWindow;

// Helper function for API calls
async function callBackendAPI(endpoint, method = 'GET', data = null) {
  try {
    const url = `${BACKEND_BASE_URL}/api${endpoint}`;
    const options = {
      method,
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: API_TIMEOUT,
    };

    if (data) {
      options.body = JSON.stringify(data);
    }

    const response = await fetch(url, options);
    
    if (!response.ok) {
      throw new Error(`API error: ${response.status} ${response.statusText}`);
    }
    
    return await response.json();
  } catch (error) {
    console.error(`Backend API call failed: ${endpoint}`, error);
    throw error;
  }
}

// Setup all IPC handlers
function setupIPCHandlers(window) {
  mainWindow = window;

  // Project Management Handlers
  ipcMain.handle('scan-project', async (event, projectPath) => {
    try {
      const result = await callBackendAPI('/project/scan', 'POST', { path: projectPath });
      
      // Send progress updates to renderer
      if (mainWindow) {
        mainWindow.webContents.send('progress-update', {
          type: 'scan',
          status: 'completed',
          data: result
        });
      }
      
      return result;
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('open-project-dialog', async () => {
    try {
      const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory'],
        title: 'Select Project Directory'
      });
      
      if (!result.canceled && result.filePaths.length > 0) {
        return { path: result.filePaths[0] };
      }
      
      return { canceled: true };
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('get-project-info', async () => {
    try {
      return await callBackendAPI('/project/info');
    } catch (error) {
      return { error: error.message };
    }
  });

  // Graph Operation Handlers
  ipcMain.handle('get-graph', async () => {
    try {
      return await callBackendAPI('/graph');
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('get-graph-stats', async () => {
    try {
      return await callBackendAPI('/graph/stats');
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('clear-graph', async () => {
    try {
      return await callBackendAPI('/graph/clear', 'DELETE');
    } catch (error) {
      return { error: error.message };
    }
  });

  // File Operation Handlers
  ipcMain.handle('get-file-tree', async (event, projectPath) => {
    try {
      return await callBackendAPI('/files/tree', 'POST', { path: projectPath });
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('get-file-content', async (event, filePath) => {
    try {
      const content = await fs.readFile(filePath, 'utf8');
      return { content };
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('save-file', async (event, filePath, content) => {
    try {
      await fs.writeFile(filePath, content, 'utf8');
      return { success: true };
    } catch (error) {
      return { error: error.message };
    }
  });

  // Refactoring Operation Handlers
  ipcMain.handle('get-refactoring-candidates', async (event, pattern) => {
    try {
      return await callBackendAPI('/refactoring/candidates', 'POST', { pattern });
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('apply-refactoring', async (event, nodeId, refactorType, options) => {
    try {
      return await callBackendAPI('/refactoring/apply', 'POST', {
        nodeId,
        refactorType,
        options
      });
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('preview-refactoring', async (event, nodeId, refactorType, options) => {
    try {
      return await callBackendAPI('/refactoring/preview', 'POST', {
        nodeId,
        refactorType,
        options
      });
    } catch (error) {
      return { error: error.message };
    }
  });

  // Lint Operation Handlers
  ipcMain.handle('get-lint-errors', async (event, filePath) => {
    try {
      return await callBackendAPI('/lint/errors', 'POST', { filePath });
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('run-linting', async (event, projectPath, language) => {
    try {
      return await callBackendAPI('/lint/run', 'POST', { projectPath, language });
    } catch (error) {
      return { error: error.message };
    }
  });

  // Analysis Operation Handlers
  ipcMain.handle('analyze-code', async (event, filePath) => {
    try {
      return await callBackendAPI('/analysis/file', 'POST', { filePath });
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('get-call-graph', async (event, entityId) => {
    try {
      return await callBackendAPI(`/analysis/calls/${entityId}`);
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('find-usages', async (event, entityId) => {
    try {
      return await callBackendAPI(`/analysis/usages/${entityId}`);
    } catch (error) {
      return { error: error.message };
    }
  });

  // Backend Communication Handlers
  ipcMain.handle('get-backend-status', async () => {
    try {
      const response = await fetch(`${BACKEND_BASE_URL}/health`, { timeout: 5000 });
      return { status: response.ok ? 'connected' : 'error' };
    } catch (error) {
      return { status: 'disconnected', error: error.message };
    }
  });

  ipcMain.handle('restart-backend', async () => {
    // This would restart the Python backend process
    // Implementation depends on how the backend is managed
    return { message: 'Backend restart requested' };
  });

  // Application Operation Handlers
  ipcMain.handle('get-app-version', () => {
    return { version: app.getVersion() };
  });

  ipcMain.handle('open-external', async (event, url) => {
    try {
      await shell.openExternal(url);
      return { success: true };
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('show-message-box', async (event, options) => {
    try {
      const result = await dialog.showMessageBox(mainWindow, options);
      return result;
    } catch (error) {
      return { error: error.message };
    }
  });

  // Window Operation Handlers
  ipcMain.handle('minimize-window', () => {
    if (mainWindow) {
      mainWindow.minimize();
      return { success: true };
    }
    return { error: 'No window available' };
  });

  ipcMain.handle('maximize-window', () => {
    if (mainWindow) {
      if (mainWindow.isMaximized()) {
        mainWindow.unmaximize();
      } else {
        mainWindow.maximize();
      }
      return { success: true };
    }
    return { error: 'No window available' };
  });

  ipcMain.handle('close-window', () => {
    if (mainWindow) {
      mainWindow.close();
      return { success: true };
    }
    return { error: 'No window available' };
  });

  ipcMain.handle('is-window-maximized', () => {
    if (mainWindow) {
      return { maximized: mainWindow.isMaximized() };
    }
    return { error: 'No window available' };
  });

  // Settings Operation Handlers
  ipcMain.handle('get-settings', async () => {
    try {
      const settingsPath = path.join(app.getPath('userData'), 'settings.json');
      const content = await fs.readFile(settingsPath, 'utf8');
      return JSON.parse(content);
    } catch (error) {
      // Return default settings if file doesn't exist
      return {
        theme: 'light',
        autoSave: true,
        showLineNumbers: true,
        fontFamily: 'Monaco, Consolas, monospace',
        fontSize: 14
      };
    }
  });

  ipcMain.handle('update-settings', async (event, settings) => {
    try {
      const settingsPath = path.join(app.getPath('userData'), 'settings.json');
      await fs.writeFile(settingsPath, JSON.stringify(settings, null, 2));
      return { success: true };
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('reset-settings', async () => {
    try {
      const settingsPath = path.join(app.getPath('userData'), 'settings.json');
      await fs.unlink(settingsPath);
      return { success: true };
    } catch (error) {
      return { error: error.message };
    }
  });

  // Utility Handlers
  ipcMain.handle('select-directory', async () => {
    try {
      const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openDirectory']
      });
      return result;
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('select-file', async (event, filters) => {
    try {
      const result = await dialog.showOpenDialog(mainWindow, {
        properties: ['openFile'],
        filters: filters || []
      });
      return result;
    } catch (error) {
      return { error: error.message };
    }
  });

  ipcMain.handle('save-file-dialog', async (event, defaultPath, filters) => {
    try {
      const result = await dialog.showSaveDialog(mainWindow, {
        defaultPath,
        filters: filters || []
      });
      return result;
    } catch (error) {
      return { error: error.message };
    }
  });

  // Development Helpers (only in development)
  if (process.env.NODE_ENV === 'development') {
    ipcMain.handle('open-dev-tools', () => {
      if (mainWindow) {
        mainWindow.webContents.openDevTools();
        return { success: true };
      }
      return { error: 'No window available' };
    });

    ipcMain.handle('reload-app', () => {
      if (mainWindow) {
        mainWindow.reload();
        return { success: true };
      }
      return { error: 'No window available' };
    });

    ipcMain.handle('clear-cache', async () => {
      try {
        if (mainWindow) {
          await mainWindow.webContents.session.clearCache();
          return { success: true };
        }
        return { error: 'No window available' };
      } catch (error) {
        return { error: error.message };
      }
    });
  }

  // Error handling for renderer errors
  ipcMain.on('renderer-error', (event, errorData) => {
    console.error('Renderer process error:', errorData);
  });

  console.log('IPC handlers setup completed');
}

module.exports = { setupIPCHandlers };