const { BrowserWindow, screen } = require('electron');
const path = require('path');

class WindowManager {
  constructor(mainWindow) {
    this.mainWindow = mainWindow;
    this.windows = new Map();
    this.setupWindowStateManagement();
  }

  setupWindowStateManagement() {
    if (!this.mainWindow) return;

    // Save window state when it changes
    this.mainWindow.on('resize', () => this.saveWindowState());
    this.mainWindow.on('move', () => this.saveWindowState());
    this.mainWindow.on('maximize', () => this.saveWindowState());
    this.mainWindow.on('unmaximize', () => this.saveWindowState());
    this.mainWindow.on('minimize', () => this.saveWindowState());
    this.mainWindow.on('restore', () => this.saveWindowState());

    // Restore window state on startup
    this.restoreWindowState();
  }

  saveWindowState() {
    if (!this.mainWindow) return;

    const bounds = this.mainWindow.getBounds();
    const state = {
      x: bounds.x,
      y: bounds.y,
      width: bounds.width,
      height: bounds.height,
      isMaximized: this.mainWindow.isMaximized(),
      isMinimized: this.mainWindow.isMinimized(),
      timestamp: Date.now()
    };

    // Store in user data (you could use electron-store or similar)
    global.windowState = state;
  }

  restoreWindowState() {
    if (!this.mainWindow || !global.windowState) return;

    const state = global.windowState;
    const { workAreaSize } = screen.getPrimaryDisplay();

    // Validate bounds are within screen
    if (this.isValidPosition(state, workAreaSize)) {
      this.mainWindow.setBounds({
        x: state.x,
        y: state.y,
        width: state.width,
        height: state.height
      });

      if (state.isMaximized) {
        this.mainWindow.maximize();
      }
    }
  }

  isValidPosition(state, workAreaSize) {
    return (
      state.x >= 0 &&
      state.y >= 0 &&
      state.x + state.width <= workAreaSize.width &&
      state.y + state.height <= workAreaSize.height
    );
  }

  createChildWindow(name, options = {}) {
    const defaultOptions = {
      width: 800,
      height: 600,
      parent: this.mainWindow,
      modal: true,
      show: false,
      autoHideMenuBar: true,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(__dirname, 'preload.js')
      }
    };

    const windowOptions = { ...defaultOptions, ...options };
    const childWindow = new BrowserWindow(windowOptions);

    // Store reference
    this.windows.set(name, childWindow);

    // Handle window closed
    childWindow.on('closed', () => {
      this.windows.delete(name);
    });

    // Show when ready
    childWindow.once('ready-to-show', () => {
      childWindow.show();
    });

    return childWindow;
  }

  getWindow(name) {
    return this.windows.get(name);
  }

  closeWindow(name) {
    const window = this.windows.get(name);
    if (window && !window.isDestroyed()) {
      window.close();
    }
  }

  closeAllChildWindows() {
    for (const [name, window] of this.windows) {
      if (!window.isDestroyed()) {
        window.close();
      }
    }
    this.windows.clear();
  }

  // Predefined window creators
  createSettingsWindow() {
    return this.createChildWindow('settings', {
      width: 600,
      height: 500,
      resizable: false,
      title: 'Settings'
    });
  }

  createAboutWindow() {
    return this.createChildWindow('about', {
      width: 400,
      height: 300,
      resizable: false,
      title: 'About Codebase Refactor Tool'
    });
  }

  createPreferencesWindow() {
    return this.createChildWindow('preferences', {
      width: 700,
      height: 550,
      title: 'Preferences'
    });
  }

  createRefactoringPreviewWindow(refactoringData) {
    const window = this.createChildWindow('refactoring-preview', {
      width: 1000,
      height: 700,
      title: 'Refactoring Preview'
    });

    // Pass refactoring data to window when ready
    window.webContents.once('did-finish-load', () => {
      window.webContents.send('refactoring-data', refactoringData);
    });

    return window;
  }

  createErrorReportWindow(errorData) {
    const window = this.createChildWindow('error-report', {
      width: 800,
      height: 600,
      title: 'Error Report'
    });

    window.webContents.once('did-finish-load', () => {
      window.webContents.send('error-data', errorData);
    });

    return window;
  }

  // Window state utilities
  centerWindow(window = this.mainWindow) {
    if (!window) return;

    const { workAreaSize } = screen.getPrimaryDisplay();
    const bounds = window.getBounds();
    
    const x = Math.round((workAreaSize.width - bounds.width) / 2);
    const y = Math.round((workAreaSize.height - bounds.height) / 2);
    
    window.setPosition(x, y);
  }

  fitToScreen(window = this.mainWindow) {
    if (!window) return;

    const { workAreaSize } = screen.getPrimaryDisplay();
    const maxWidth = Math.round(workAreaSize.width * 0.9);
    const maxHeight = Math.round(workAreaSize.height * 0.9);
    
    window.setSize(
      Math.min(window.getBounds().width, maxWidth),
      Math.min(window.getBounds().height, maxHeight)
    );
    
    this.centerWindow(window);
  }

  // Focus management
  focusMainWindow() {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      if (this.mainWindow.isMinimized()) {
        this.mainWindow.restore();
      }
      this.mainWindow.focus();
    }
  }

  // Window visibility
  hideAllWindows() {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.hide();
    }
    
    for (const window of this.windows.values()) {
      if (!window.isDestroyed()) {
        window.hide();
      }
    }
  }

  showAllWindows() {
    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.show();
    }
    
    for (const window of this.windows.values()) {
      if (!window.isDestroyed()) {
        window.show();
      }
    }
  }

  // Development utilities
  openDevToolsForAll() {
    if (process.env.NODE_ENV !== 'development') return;

    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.webContents.openDevTools();
    }
    
    for (const window of this.windows.values()) {
      if (!window.isDestroyed()) {
        window.webContents.openDevTools();
      }
    }
  }

  reloadAllWindows() {
    if (process.env.NODE_ENV !== 'development') return;

    if (this.mainWindow && !this.mainWindow.isDestroyed()) {
      this.mainWindow.reload();
    }
    
    for (const window of this.windows.values()) {
      if (!window.isDestroyed()) {
        window.reload();
      }
    }
  }

  // Statistics
  getWindowStats() {
    return {
      mainWindowExists: this.mainWindow && !this.mainWindow.isDestroyed(),
      childWindowCount: this.windows.size,
      childWindows: Array.from(this.windows.keys()),
      mainWindowState: this.mainWindow ? {
        isVisible: this.mainWindow.isVisible(),
        isMaximized: this.mainWindow.isMaximized(),
        isMinimized: this.mainWindow.isMinimized(),
        isFocused: this.mainWindow.isFocused()
      } : null
    };
  }

  // Cleanup
  destroy() {
    this.closeAllChildWindows();
    this.windows.clear();
    this.mainWindow = null;
  }
}

module.exports = { WindowManager };