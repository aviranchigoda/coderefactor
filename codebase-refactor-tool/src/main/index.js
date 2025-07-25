const { app, BrowserWindow, ipcMain } = require('electron');
const { spawn } = require('child_process');
const path = require('path');
const { setupIPCHandlers } = require('./ipc-handlers');
const { createApplicationMenu } = require('./menu');
const { WindowManager } = require('./window-manager');

let mainWindow;
let pythonProcess;
let windowManager;

function createWindow() {
  // Create the browser window
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1000,
    minHeight: 600,
    show: false, // Don't show until ready-to-show
    icon: path.join(__dirname, '../../resources/icons/app-icon.png'),
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      enableRemoteModule: false,
      preload: path.join(__dirname, 'preload.js'),
      webSecurity: true
    }
  });

  // Initialize window manager
  windowManager = new WindowManager(mainWindow);

  // Load the app
  if (process.env.NODE_ENV === 'development') {
    mainWindow.loadURL('http://localhost:3000');
    mainWindow.webContents.openDevTools();
  } else {
    mainWindow.loadFile(path.join(__dirname, '../renderer/index.html'));
  }

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    mainWindow.show();
    
    // Focus on macOS
    if (process.platform === 'darwin') {
      app.focus();
    }
  });

  // Handle window closed
  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Handle window state changes
  mainWindow.on('maximize', () => {
    mainWindow.webContents.send('window-state-changed', { maximized: true });
  });

  mainWindow.on('unmaximize', () => {
    mainWindow.webContents.send('window-state-changed', { maximized: false });
  });

  return mainWindow;
}

function startPythonBackend() {
  console.log('Starting Python backend...');
  
  const pythonPath = process.env.PYTHON_PATH || 'python';
  const backendPath = path.join(__dirname, '../../backend/main.py');
  
  pythonProcess = spawn(pythonPath, [backendPath], {
    cwd: path.join(__dirname, '../..'),
    stdio: ['pipe', 'pipe', 'pipe']
  });

  pythonProcess.stdout.on('data', (data) => {
    console.log(`Python Backend: ${data.toString().trim()}`);
    
    // Send backend logs to renderer if needed
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend-log', {
        type: 'info',
        message: data.toString().trim()
      });
    }
  });

  pythonProcess.stderr.on('data', (data) => {
    console.error(`Python Backend Error: ${data.toString().trim()}`);
    
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend-log', {
        type: 'error',
        message: data.toString().trim()
      });
    }
  });

  pythonProcess.on('close', (code) => {
    console.log(`Python backend exited with code ${code}`);
    
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend-status', {
        status: 'disconnected',
        code: code
      });
    }
  });

  pythonProcess.on('error', (error) => {
    console.error('Failed to start Python backend:', error);
    
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('backend-error', {
        error: error.message
      });
    }
  });
}

function stopPythonBackend() {
  if (pythonProcess && !pythonProcess.killed) {
    console.log('Stopping Python backend...');
    pythonProcess.kill('SIGTERM');
    
    // Force kill after 5 seconds if graceful shutdown fails
    setTimeout(() => {
      if (pythonProcess && !pythonProcess.killed) {
        console.log('Force killing Python backend...');
        pythonProcess.kill('SIGKILL');
      }
    }, 5000);
  }
}

// App event handlers
app.whenReady().then(() => {
  // Create application menu
  createApplicationMenu();
  
  // Create main window
  createWindow();
  
  // Setup IPC handlers
  setupIPCHandlers(mainWindow);
  
  // Start Python backend
  startPythonBackend();
  
  // Handle app activation (macOS)
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Handle all windows closed
app.on('window-all-closed', () => {
  // On macOS, keep app running even when all windows are closed
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Handle app before quit
app.on('before-quit', (event) => {
  console.log('Application is about to quit...');
  
  // Stop Python backend gracefully
  stopPythonBackend();
});

// Handle app will quit
app.on('will-quit', (event) => {
  console.log('Application will quit...');
});

// Security: Prevent new window creation
app.on('web-contents-created', (event, contents) => {
  contents.on('new-window', (event, navigationUrl) => {
    event.preventDefault();
    console.warn('Blocked new window creation:', navigationUrl);
  });
});

// Security: Prevent navigation to external URLs
app.on('web-contents-created', (event, contents) => {
  contents.on('will-navigate', (event, navigationUrl) => {
    const parsedUrl = new URL(navigationUrl);
    
    if (parsedUrl.origin !== 'http://localhost:3000' && 
        parsedUrl.origin !== 'file://') {
      event.preventDefault();
      console.warn('Blocked navigation to:', navigationUrl);
    }
  });
});

// Handle certificate errors in development
app.on('certificate-error', (event, webContents, url, error, certificate, callback) => {
  if (process.env.NODE_ENV === 'development') {
    // In development, ignore certificate errors for localhost
    event.preventDefault();
    callback(true);
  } else {
    callback(false);
  }
});

// Export for testing
module.exports = {
  createWindow,
  startPythonBackend,
  stopPythonBackend,
  getMainWindow: () => mainWindow,
  getPythonProcess: () => pythonProcess
};