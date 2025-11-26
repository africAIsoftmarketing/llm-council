/**
 * LLM Council Desktop Application
 * Electron main process - manages backend services and browser window
 */

const { app, BrowserWindow, Tray, Menu, dialog, shell, ipcMain } = require('electron');
const path = require('path');
const { spawn, exec } = require('child_process');
const fs = require('fs');
const Store = require('electron-store');
const treeKill = require('tree-kill');

// Configuration store
const store = new Store({
  defaults: {
    firstRun: true,
    backendPort: 8001,
    frontendPort: 5173,
    autoStart: true,
    minimizeToTray: true
  }
});

// Global references
let mainWindow = null;
let splashWindow = null;
let tray = null;
let backendProcess = null;
let frontendProcess = null;
let isQuitting = false;

// Paths
const isDev = !app.isPackaged;
const resourcesPath = isDev ? path.join(__dirname, '..') : process.resourcesPath;
const pythonPath = isDev 
  ? 'python' 
  : path.join(resourcesPath, 'python', 'python.exe');
const backendPath = isDev 
  ? path.join(__dirname, '..', '..', 'backend')
  : path.join(resourcesPath, 'backend');
const frontendPath = isDev
  ? path.join(__dirname, '..', '..', 'frontend', 'dist')
  : path.join(resourcesPath, 'frontend');
const dataPath = path.join(app.getPath('userData'), 'data');

// Ensure data directory exists
if (!fs.existsSync(dataPath)) {
  fs.mkdirSync(dataPath, { recursive: true });
}

/**
 * Create the splash screen window
 */
function createSplashWindow() {
  splashWindow = new BrowserWindow({
    width: 400,
    height: 300,
    frame: false,
    transparent: true,
    alwaysOnTop: true,
    skipTaskbar: true,
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true
    }
  });

  splashWindow.loadFile(path.join(__dirname, 'splash.html'));
  splashWindow.center();
}

/**
 * Create the main application window
 */
function createMainWindow() {
  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 800,
    minHeight: 600,
    show: false,
    icon: path.join(__dirname, 'icon.ico'),
    webPreferences: {
      nodeIntegration: false,
      contextIsolation: true,
      preload: path.join(__dirname, 'preload.js')
    }
  });

  // Load the frontend
  const port = store.get('backendPort');
  mainWindow.loadURL(`http://localhost:3000`);

  // Show window when ready
  mainWindow.once('ready-to-show', () => {
    if (splashWindow) {
      splashWindow.destroy();
      splashWindow = null;
    }
    mainWindow.show();
    mainWindow.focus();
  });

  // Handle window close
  mainWindow.on('close', (event) => {
    if (!isQuitting && store.get('minimizeToTray')) {
      event.preventDefault();
      mainWindow.hide();
      return false;
    }
  });

  mainWindow.on('closed', () => {
    mainWindow = null;
  });

  // Open external links in default browser
  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: 'deny' };
  });
}

/**
 * Create system tray icon and menu
 */
function createTray() {
  const iconPath = path.join(__dirname, 'tray-icon.png');
  
  // Create a simple icon if not exists
  if (!fs.existsSync(iconPath)) {
    // Will use default electron icon
    tray = new Tray(path.join(__dirname, 'icon.ico'));
  } else {
    tray = new Tray(iconPath);
  }

  const contextMenu = Menu.buildFromTemplate([
    {
      label: 'Open LLM Council',
      click: () => {
        if (mainWindow) {
          mainWindow.show();
          mainWindow.focus();
        }
      }
    },
    {
      label: 'Open in Browser',
      click: () => {
        shell.openExternal('http://localhost:3000');
      }
    },
    { type: 'separator' },
    {
      label: 'Backend Status',
      enabled: false,
      id: 'backend-status'
    },
    {
      label: 'Restart Services',
      click: async () => {
        await stopServices();
        await startServices();
      }
    },
    { type: 'separator' },
    {
      label: 'Quit',
      click: () => {
        isQuitting = true;
        app.quit();
      }
    }
  ]);

  tray.setToolTip('LLM Council');
  tray.setContextMenu(contextMenu);

  tray.on('double-click', () => {
    if (mainWindow) {
      mainWindow.show();
      mainWindow.focus();
    }
  });
}

/**
 * Start the backend Python server
 */
async function startBackend() {
  return new Promise((resolve, reject) => {
    console.log('Starting backend server...');
    console.log('Python path:', pythonPath);
    console.log('Backend path:', backendPath);

    // Set environment variables
    const env = {
      ...process.env,
      DATA_DIR: dataPath,
      PYTHONPATH: backendPath
    };

    // Check if using embedded Python or system Python
    const pythonCmd = fs.existsSync(pythonPath) ? pythonPath : 'python';

    backendProcess = spawn(pythonCmd, [
      '-m', 'uvicorn',
      'main:app',
      '--host', '0.0.0.0',
      '--port', String(store.get('backendPort')),
      '--reload'
    ], {
      cwd: backendPath,
      env: env,
      shell: true,
      windowsHide: true
    });

    backendProcess.stdout.on('data', (data) => {
      console.log(`Backend: ${data}`);
      if (data.toString().includes('Application startup complete')) {
        resolve();
      }
    });

    backendProcess.stderr.on('data', (data) => {
      console.error(`Backend Error: ${data}`);
      // Uvicorn logs to stderr by default
      if (data.toString().includes('Application startup complete')) {
        resolve();
      }
    });

    backendProcess.on('error', (error) => {
      console.error('Failed to start backend:', error);
      reject(error);
    });

    backendProcess.on('exit', (code) => {
      console.log(`Backend process exited with code ${code}`);
      backendProcess = null;
    });

    // Resolve after timeout if server doesn't signal ready
    setTimeout(() => resolve(), 5000);
  });
}

/**
 * Start the frontend dev server (for development) or serve static files
 */
async function startFrontend() {
  return new Promise((resolve) => {
    if (isDev) {
      // In development, start Vite dev server
      console.log('Starting frontend dev server...');
      const frontendDir = path.join(__dirname, '..', '..', 'frontend');
      
      frontendProcess = spawn('npm', ['run', 'dev'], {
        cwd: frontendDir,
        shell: true,
        windowsHide: true,
        env: { ...process.env, HOST: '0.0.0.0', PORT: '3000' }
      });

      frontendProcess.stdout.on('data', (data) => {
        console.log(`Frontend: ${data}`);
        if (data.toString().includes('Local:')) {
          resolve();
        }
      });

      frontendProcess.stderr.on('data', (data) => {
        console.error(`Frontend Error: ${data}`);
      });

      setTimeout(() => resolve(), 5000);
    } else {
      // In production, frontend is served by a simple HTTP server or directly loaded
      // The built frontend is in resources/frontend
      console.log('Frontend: Using pre-built static files');
      
      // Start a simple static file server
      const http = require('http');
      const finalhandler = require('finalhandler');
      const serveStatic = require('serve-static');
      
      // Fallback: load directly from file if serve-static not available
      resolve();
    }
  });
}

/**
 * Start all services
 */
async function startServices() {
  try {
    await startBackend();
    await startFrontend();
    console.log('All services started successfully');
    return true;
  } catch (error) {
    console.error('Failed to start services:', error);
    dialog.showErrorBox(
      'Service Error',
      `Failed to start LLM Council services: ${error.message}`
    );
    return false;
  }
}

/**
 * Stop all services
 */
async function stopServices() {
  return new Promise((resolve) => {
    const promises = [];

    if (backendProcess) {
      promises.push(new Promise((res) => {
        treeKill(backendProcess.pid, 'SIGTERM', (err) => {
          if (err) console.error('Error killing backend:', err);
          backendProcess = null;
          res();
        });
      }));
    }

    if (frontendProcess) {
      promises.push(new Promise((res) => {
        treeKill(frontendProcess.pid, 'SIGTERM', (err) => {
          if (err) console.error('Error killing frontend:', err);
          frontendProcess = null;
          res();
        });
      }));
    }

    Promise.all(promises).then(() => {
      console.log('All services stopped');
      resolve();
    });
  });
}

/**
 * Check if backend is healthy
 */
async function checkBackendHealth() {
  try {
    const http = require('http');
    return new Promise((resolve) => {
      const req = http.get(`http://localhost:${store.get('backendPort')}/`, (res) => {
        resolve(res.statusCode === 200);
      });
      req.on('error', () => resolve(false));
      req.setTimeout(2000, () => {
        req.destroy();
        resolve(false);
      });
    });
  } catch {
    return false;
  }
}

// App event handlers
app.whenReady().then(async () => {
  // Create splash screen
  createSplashWindow();

  // Start services
  await startServices();

  // Wait a bit for services to fully start
  await new Promise(resolve => setTimeout(resolve, 2000));

  // Create main window and tray
  createMainWindow();
  createTray();

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    // Don't quit, minimize to tray
    if (!store.get('minimizeToTray')) {
      app.quit();
    }
  }
});

app.on('before-quit', async () => {
  isQuitting = true;
  await stopServices();
});

app.on('quit', () => {
  if (tray) {
    tray.destroy();
  }
});

// IPC handlers for renderer process
ipcMain.handle('get-config', () => {
  return store.store;
});

ipcMain.handle('set-config', (event, key, value) => {
  store.set(key, value);
  return true;
});

ipcMain.handle('restart-services', async () => {
  await stopServices();
  return await startServices();
});

ipcMain.handle('check-health', async () => {
  return await checkBackendHealth();
});

ipcMain.handle('open-external', (event, url) => {
  shell.openExternal(url);
});

ipcMain.handle('get-data-path', () => {
  return dataPath;
});
