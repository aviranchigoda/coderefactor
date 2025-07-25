const { Menu, app, shell, dialog } = require('electron');
const path = require('path');

function createApplicationMenu() {
  const isMac = process.platform === 'darwin';
  
  const template = [
    // App Menu (macOS only)
    ...(isMac ? [{
      label: app.getName(),
      submenu: [
        { role: 'about' },
        { type: 'separator' },
        {
          label: 'Preferences...',
          accelerator: 'CmdOrCtrl+,',
          click: () => {
            // Send to main window to open preferences
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'open-preferences');
            }
          }
        },
        { type: 'separator' },
        { role: 'services' },
        { type: 'separator' },
        { role: 'hide' },
        { role: 'hideothers' },
        { role: 'unhide' },
        { type: 'separator' },
        { role: 'quit' }
      ]
    }] : []),

    // File Menu
    {
      label: 'File',
      submenu: [
        {
          label: 'Open Project...',
          accelerator: 'CmdOrCtrl+O',
          click: async () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'open-project');
            }
          }
        },
        {
          label: 'Recent Projects',
          submenu: [
            {
              label: 'Clear Recent',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('menu-action', 'clear-recent');
                }
              }
            }
          ]
        },
        { type: 'separator' },
        {
          label: 'Save',
          accelerator: 'CmdOrCtrl+S',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'save-file');
            }
          }
        },
        {
          label: 'Save All',
          accelerator: 'CmdOrCtrl+Shift+S',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'save-all');
            }
          }
        },
        { type: 'separator' },
        {
          label: 'Export Graph...',
          submenu: [
            {
              label: 'Export as JSON',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('menu-action', 'export-graph-json');
                }
              }
            },
            {
              label: 'Export as PNG',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('menu-action', 'export-graph-png');
                }
              }
            },
            {
              label: 'Export as SVG',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('menu-action', 'export-graph-svg');
                }
              }
            }
          ]
        },
        { type: 'separator' },
        ...(isMac ? [] : [{ role: 'quit' }])
      ]
    },

    // Edit Menu
    {
      label: 'Edit',
      submenu: [
        { role: 'undo' },
        { role: 'redo' },
        { type: 'separator' },
        { role: 'cut' },
        { role: 'copy' },
        { role: 'paste' },
        { role: 'selectall' },
        { type: 'separator' },
        {
          label: 'Find',
          accelerator: 'CmdOrCtrl+F',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'find');
            }
          }
        },
        {
          label: 'Find in Files',
          accelerator: 'CmdOrCtrl+Shift+F',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'find-in-files');
            }
          }
        },
        {
          label: 'Replace',
          accelerator: 'CmdOrCtrl+H',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'replace');
            }
          }
        }
      ]
    },

    // Analysis Menu
    {
      label: 'Analysis',
      submenu: [
        {
          label: 'Scan Codebase',
          accelerator: 'CmdOrCtrl+R',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'scan-codebase');
            }
          }
        },
        {
          label: 'Refresh Graph',
          accelerator: 'F5',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'refresh-graph');
            }
          }
        },
        { type: 'separator' },
        {
          label: 'Run Linting',
          submenu: [
            {
              label: 'Python (pylint)',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('menu-action', 'run-lint-python');
                }
              }
            },
            {
              label: 'JavaScript (eslint)',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('menu-action', 'run-lint-javascript');
                }
              }
            },
            {
              label: 'All Languages',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('menu-action', 'run-lint-all');
                }
              }
            }
          ]
        },
        { type: 'separator' },
        {
          label: 'Clear Graph',
          click: async () => {
            const result = await dialog.showMessageBox({
              type: 'warning',
              title: 'Clear Graph',
              message: 'Are you sure you want to clear the entire graph?',
              detail: 'This action cannot be undone.',
              buttons: ['Cancel', 'Clear Graph'],
              defaultId: 0,
              cancelId: 0
            });

            if (result.response === 1) {
              const mainWindow = require('./index').getMainWindow();
              if (mainWindow) {
                mainWindow.webContents.send('menu-action', 'clear-graph');
              }
            }
          }
        }
      ]
    },

    // Refactoring Menu
    {
      label: 'Refactoring',
      submenu: [
        {
          label: 'Find Refactoring Candidates',
          submenu: [
            {
              label: 'Long Methods',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('menu-action', 'find-long-methods');
                }
              }
            },
            {
              label: 'Code Duplication',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('menu-action', 'find-duplicates');
                }
              }
            },
            {
              label: 'Complex Conditionals',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('menu-action', 'find-complex-conditionals');
                }
              }
            }
          ]
        },
        { type: 'separator' },
        {
          label: 'Refactoring History',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'show-refactoring-history');
            }
          }
        }
      ]
    },

    // View Menu
    {
      label: 'View',
      submenu: [
        { role: 'reload' },
        { role: 'forceReload' },
        { role: 'toggleDevTools' },
        { type: 'separator' },
        { role: 'resetZoom' },
        { role: 'zoomIn' },
        { role: 'zoomOut' },
        { type: 'separator' },
        { role: 'togglefullscreen' },
        { type: 'separator' },
        {
          label: 'Toggle Sidebar',
          accelerator: 'CmdOrCtrl+B',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'toggle-sidebar');
            }
          }
        },
        {
          label: 'Toggle Graph Panel',
          accelerator: 'CmdOrCtrl+G',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'toggle-graph-panel');
            }
          }
        },
        {
          label: 'Toggle Error Panel',
          accelerator: 'CmdOrCtrl+E',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'toggle-error-panel');
            }
          }
        },
        { type: 'separator' },
        {
          label: 'Theme',
          submenu: [
            {
              label: 'Light',
              type: 'radio',
              checked: true,
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('menu-action', 'set-theme-light');
                }
              }
            },
            {
              label: 'Dark',
              type: 'radio',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('menu-action', 'set-theme-dark');
                }
              }
            },
            {
              label: 'Auto',
              type: 'radio',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('menu-action', 'set-theme-auto');
                }
              }
            }
          ]
        }
      ]
    },

    // Window Menu (macOS style)
    {
      label: 'Window',
      submenu: [
        { role: 'minimize' },
        { role: 'close' },
        ...(isMac ? [
          { type: 'separator' },
          { role: 'front' },
          { type: 'separator' },
          { role: 'window' }
        ] : [])
      ]
    },

    // Help Menu
    {
      role: 'help',
      submenu: [
        {
          label: 'Documentation',
          click: async () => {
            await shell.openExternal('https://github.com/your-org/codebase-refactor-tool/docs');
          }
        },
        {
          label: 'Keyboard Shortcuts',
          accelerator: 'CmdOrCtrl+?',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'show-shortcuts');
            }
          }
        },
        { type: 'separator' },
        {
          label: 'Report Issue',
          click: async () => {
            await shell.openExternal('https://github.com/your-org/codebase-refactor-tool/issues');
          }
        },
        {
          label: 'Check for Updates',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'check-updates');
            }
          }
        },
        { type: 'separator' },
        ...(!isMac ? [{
          label: 'About',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('menu-action', 'show-about');
            }
          }
        }] : [])
      ]
    }
  ];

  const menu = Menu.buildFromTemplate(template);
  Menu.setApplicationMenu(menu);

  return menu;
}

// Context menu for different areas
function createContextMenu(type, data = {}) {
  let template = [];

  switch (type) {
    case 'graph-node':
      template = [
        {
          label: 'View Details',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('context-menu-action', 'view-node-details', data);
            }
          }
        },
        {
          label: 'Find Usages',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('context-menu-action', 'find-usages', data);
            }
          }
        },
        { type: 'separator' },
        {
          label: 'Refactor',
          submenu: [
            {
              label: 'Extract Method',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('context-menu-action', 'extract-method', data);
                }
              }
            },
            {
              label: 'Rename',
              click: () => {
                const mainWindow = require('./index').getMainWindow();
                if (mainWindow) {
                  mainWindow.webContents.send('context-menu-action', 'rename', data);
                }
              }
            }
          ]
        }
      ];
      break;

    case 'file-tree':
      template = [
        {
          label: 'Open File',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('context-menu-action', 'open-file', data);
            }
          }
        },
        {
          label: 'Analyze File',
          click: () => {
            const mainWindow = require('./index').getMainWindow();
            if (mainWindow) {
              mainWindow.webContents.send('context-menu-action', 'analyze-file', data);
            }
          }
        },
        { type: 'separator' },
        {
          label: 'Show in Explorer',
          click: () => {
            shell.showItemInFolder(data.path);
          }
        }
      ];
      break;

    default:
      template = [
        { role: 'copy' },
        { role: 'paste' },
        { type: 'separator' },
        { role: 'selectall' }
      ];
  }

  return Menu.buildFromTemplate(template);
}

module.exports = {
  createApplicationMenu,
  createContextMenu
};