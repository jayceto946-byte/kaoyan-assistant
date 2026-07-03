const { app, BrowserWindow, ipcMain, shell } = require('electron');
const { autoUpdater } = require('electron-updater');
const { spawn } = require('node:child_process');
const fs = require('node:fs');
const path = require('node:path');

const BACKEND_PORT = Number(process.env.KAOYAN_BACKEND_PORT || 8000);
const BACKEND_URL = process.env.KAOYAN_BACKEND_URL || `http://127.0.0.1:${BACKEND_PORT}`;
const FRONTEND_DEV_URL = process.env.KAOYAN_FRONTEND_DEV_URL || '';

let mainWindow = null;
let backendProcess = null;
let backendStartError = null;
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
  const logDir = path.join(userData, 'logs');
  return {
    userData,
    logDir,
    backendLogPath: path.join(logDir, 'backend.log'),
    dataDir: path.join(userData, 'data'),
    envPath: path.join(userData, '.env'),
    mineruOutputPath: path.join(userData, 'mineru_output'),
  };
}

function appendBackendLog(message) {
  const paths = runtimePaths();
  fs.mkdirSync(paths.logDir, { recursive: true });
  fs.appendFileSync(paths.backendLogPath, `${new Date().toISOString()} ${message}\n`, 'utf8');
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
    SKIP_VECTOR_WARMUP: process.env.SKIP_VECTOR_WARMUP || '0',
    SKIP_EMBEDDING_WARMUP: process.env.SKIP_EMBEDDING_WARMUP || '0',
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

function sendStartupError(message) {
  backendStartError = message;
  mainWindow?.webContents.send('startup-error', startupInfo(message));
}

function startupInfo(message = backendStartError) {
  const paths = runtimePaths();
  return {
    message: message || '',
    backendUrl: BACKEND_URL,
    logPath: paths.backendLogPath,
    dataDir: paths.dataDir,
  };
}

function attachBackendLogging() {
  if (!backendProcess) return;
  backendProcess.stdout?.on('data', (chunk) => appendBackendLog(`[stdout] ${chunk.toString().trimEnd()}`));
  backendProcess.stderr?.on('data', (chunk) => appendBackendLog(`[stderr] ${chunk.toString().trimEnd()}`));
  backendProcess.on('error', (error) => {
    const message = `后端进程启动失败：${error.message || error}`;
    appendBackendLog(`[error] ${message}`);
    sendStartupError(message);
  });
  backendProcess.on('exit', (code, signal) => {
    const message = `后端进程退出：code=${code ?? 'null'}, signal=${signal ?? 'null'}`;
    appendBackendLog(`[exit] ${message}`);
    if (!shuttingDown) sendStartupError(message);
  });
}

function startBackend() {
  if (process.env.KAOYAN_SKIP_BACKEND === '1') {
    appendBackendLog('[main] KAOYAN_SKIP_BACKEND=1, backend spawn skipped.');
    return;
  }

  try {
    const env = backendEnv();
    if (app.isPackaged) {
      const executable = packagedBackendPath();
      appendBackendLog(`[main] starting packaged backend: ${executable}`);
      if (!fs.existsSync(executable)) {
        sendStartupError(`找不到后端可执行文件：${executable}`);
        return;
      }
      backendProcess = spawn(executable, [], {
        cwd: path.dirname(executable),
        windowsHide: true,
        env,
      });
      attachBackendLogging();
      return;
    }

    const python = process.env.KAOYAN_PYTHON || path.join(projectRoot(), 'venv310', 'Scripts', 'python.exe');
    appendBackendLog(`[main] starting dev backend: ${python}`);
    backendProcess = spawn(
      python,
      ['-m', 'uvicorn', 'backend.main:app', '--host', '127.0.0.1', '--port', String(BACKEND_PORT)],
      {
        cwd: projectRoot(),
        windowsHide: true,
        env,
      },
    );
    attachBackendLogging();
  } catch (error) {
    const message = `后端启动准备失败：${error.message || error}`;
    appendBackendLog(`[error] ${message}`);
    sendStartupError(message);
  }
}

async function waitForBackend(timeoutMs = 60000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (backendStartError) return false;
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
    minWidth: 720,
    minHeight: 560,
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
    const message = backendStartError || `后端服务启动超时：${BACKEND_URL}`;
    appendBackendLog(`[timeout] ${message}`);
    mainWindow.webContents.send('startup-error', startupInfo(message));
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

ipcMain.handle('startup:info', () => startupInfo());
ipcMain.handle('startup:open-web', async () => shell.openExternal(BACKEND_URL));
ipcMain.handle('startup:open-log', async () => {
  const logPath = runtimePaths().backendLogPath;
  fs.mkdirSync(path.dirname(logPath), { recursive: true });
  if (!fs.existsSync(logPath)) fs.writeFileSync(logPath, '', 'utf8');
  return shell.openPath(logPath);
});

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
