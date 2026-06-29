const { app, BrowserWindow, ipcMain } = require('electron');
const { autoUpdater } = require('electron-updater');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const BACKEND_PORT = Number(process.env.KAOYAN_BACKEND_PORT || 8000);
const BACKEND_URL = process.env.KAOYAN_BACKEND_URL || `http://127.0.0.1:${BACKEND_PORT}`;
const FRONTEND_DEV_URL = process.env.KAOYAN_FRONTEND_DEV_URL || '';

let mainWindow = null;
let backendProcess = null;
let shuttingDown = false;
let updaterConfigured = false;
let updateState = {
  status: 'idle',
  message: '尚未检查更新',
  currentVersion: app.getVersion(),
  updateInfo: null,
  progress: null,
};

function projectRoot() {
  return path.resolve(__dirname, '..');
}

function packagedBackendPath() {
  return path.join(process.resourcesPath, 'backend', 'backend_server', 'backend_server.exe');
}

function runtimePaths() {
  const userData = app.getPath('userData');
  return {
    userData,
    dataDir: path.join(userData, 'data'),
    envPath: path.join(userData, '.env'),
    mineruOutputPath: path.join(userData, 'mineru_output'),
  };
}

function backendEnv() {
  const paths = runtimePaths();
  fs.mkdirSync(paths.dataDir, { recursive: true });
  fs.mkdirSync(paths.mineruOutputPath, { recursive: true });

  return {
    ...process.env,
    KAOYAN_BACKEND_PORT: String(BACKEND_PORT),
    DATA_DIR: paths.dataDir,
    ENV_PATH: paths.envPath,
    MINERU_OUTPUT_PATH: paths.mineruOutputPath,
    SKIP_VECTOR_WARMUP: process.env.SKIP_VECTOR_WARMUP || '1',
    SKIP_EMBEDDING_WARMUP: process.env.SKIP_EMBEDDING_WARMUP || '1',
    EMBEDDING_LOCAL_FILES_ONLY: process.env.EMBEDDING_LOCAL_FILES_ONLY || '1',
  };
}

function loadUpdateConfig() {
  const configPath = path.join(__dirname, 'update-config.json');
  let config = {};
  try {
    if (fs.existsSync(configPath)) {
      config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
    }
  } catch (error) {
    console.error('[updater] failed to read update-config.json', error);
  }

  const owner = process.env.KAOYAN_UPDATE_OWNER || config.owner;
  const repo = process.env.KAOYAN_UPDATE_REPO || config.repo;
  const provider = process.env.KAOYAN_UPDATE_PROVIDER || config.provider || 'github';
  const releaseType = process.env.KAOYAN_UPDATE_RELEASE_TYPE || config.releaseType || 'release';

  if (!owner || !repo || owner === 'YOUR_GITHUB_OWNER' || repo === 'YOUR_GITHUB_REPO') {
    return null;
  }

  return { provider, owner, repo, releaseType };
}

function emitUpdateState(nextState) {
  updateState = { ...updateState, ...nextState, currentVersion: app.getVersion() };
  mainWindow?.webContents.send('updates:status', updateState);
  return updateState;
}

function configureUpdater() {
  if (updaterConfigured) return true;

  if (!app.isPackaged && process.env.KAOYAN_ALLOW_DEV_UPDATES !== '1') {
    emitUpdateState({
      status: 'disabled',
      message: '开发模式不执行自动更新。打包后的安装版会启用 GitHub Releases 更新。',
    });
    return false;
  }

  const updateConfig = loadUpdateConfig();
  if (!updateConfig) {
    emitUpdateState({
      status: 'disabled',
      message: '尚未配置 GitHub 更新仓库，请修改 desktop/update-config.json 的 owner/repo。',
    });
    return false;
  }

  autoUpdater.autoDownload = false;
  autoUpdater.autoInstallOnAppQuit = false;
  autoUpdater.setFeedURL(updateConfig);

  autoUpdater.on('checking-for-update', () => emitUpdateState({ status: 'checking', message: '正在检查更新...', progress: null }));
  autoUpdater.on('update-available', (info) => emitUpdateState({ status: 'available', message: `发现新版本 ${info.version || ''}`.trim(), updateInfo: info, progress: null }));
  autoUpdater.on('update-not-available', (info) => emitUpdateState({ status: 'none', message: '当前已经是最新版本', updateInfo: info, progress: null }));
  autoUpdater.on('download-progress', (progress) => emitUpdateState({ status: 'downloading', message: `正在下载更新 ${Math.round(progress.percent || 0)}%`, progress }));
  autoUpdater.on('update-downloaded', (info) => emitUpdateState({ status: 'downloaded', message: '更新已下载，重启后安装', updateInfo: info, progress: null }));
  autoUpdater.on('error', (error) => emitUpdateState({ status: 'error', message: `更新失败：${error.message || error}`, progress: null }));

  updaterConfigured = true;
  return true;
}

function startBackend() {
  if (process.env.KAOYAN_SKIP_BACKEND === '1') return;

  if (app.isPackaged) {
    backendProcess = spawn(packagedBackendPath(), [], {
      cwd: path.dirname(packagedBackendPath()),
      windowsHide: true,
      env: backendEnv(),
    });
    return;
  }

  const python = process.env.KAOYAN_PYTHON || path.join(projectRoot(), 'venv310', 'Scripts', 'python.exe');
  backendProcess = spawn(
    python,
    ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
    {
      cwd: projectRoot(),
      windowsHide: true,
      env: backendEnv(),
    },
  );

  backendProcess.stdout?.on('data', (chunk) => console.log(`[backend] ${chunk}`.trim()));
  backendProcess.stderr?.on('data', (chunk) => console.error(`[backend] ${chunk}`.trim()));
}

async function waitForBackend(timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const res = await fetch(`${BACKEND_URL}/health`);
      if (res.ok) return true;
    } catch {
      // Backend is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 600));
  }
  return false;
}

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 820,
    minWidth: 980,
    minHeight: 640,
    frame: false,
    show: false,
    backgroundColor: '#f4f6f1',
    title: '考研智能辅助系统',
    webPreferences: {
      preload: path.join(__dirname, 'preload.cjs'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.once('ready-to-show', () => mainWindow?.show());
  mainWindow.loadFile(path.join(__dirname, 'loading.html'));

  const targetUrl = FRONTEND_DEV_URL || BACKEND_URL;
  waitForBackend().then((ready) => {
    if (shuttingDown || !mainWindow) return;
    if (ready || FRONTEND_DEV_URL) {
      mainWindow.loadURL(targetUrl);
      return;
    }
    mainWindow.webContents.send('startup-error', `后端服务启动超时：${BACKEND_URL}`);
  });
}

ipcMain.handle('window:minimize', () => mainWindow?.minimize());
ipcMain.handle('window:toggle-maximize', () => {
  if (!mainWindow) return false;
  if (mainWindow.isMaximized()) mainWindow.unmaximize();
  else mainWindow.maximize();
  return mainWindow.isMaximized();
});
ipcMain.handle('window:close', () => mainWindow?.close());

ipcMain.handle('updates:status', () => updateState);
ipcMain.handle('updates:check', async () => {
  if (!configureUpdater()) return updateState;
  await autoUpdater.checkForUpdates();
  return updateState;
});
ipcMain.handle('updates:download', async () => {
  if (!configureUpdater()) return updateState;
  emitUpdateState({ status: 'downloading', message: '正在下载更新...', progress: null });
  await autoUpdater.downloadUpdate();
  return updateState;
});
ipcMain.handle('updates:install', () => {
  if (updateState.status !== 'downloaded') {
    return emitUpdateState({ status: 'error', message: '更新尚未下载完成，无法安装。' });
  }
  shuttingDown = true;
  autoUpdater.quitAndInstall(false, true);
  return emitUpdateState({ status: 'installing', message: '正在重启并安装更新...' });
});

app.whenReady().then(() => {
  startBackend();
  configureUpdater();
  createWindow();
});

app.on('before-quit', () => {
  shuttingDown = true;
  if (backendProcess && !backendProcess.killed) {
    backendProcess.kill();
  }
});

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') app.quit();
});
