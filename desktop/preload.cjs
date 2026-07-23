const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('kaoyanDesktop', {
  isElectron: true,
  minimize: () => ipcRenderer.invoke('window:minimize'),
  toggleMaximize: () => ipcRenderer.invoke('window:toggle-maximize'),
  close: () => ipcRenderer.invoke('window:close'),
  restart: () => ipcRenderer.invoke('app:restart'),
  getStartupInfo: () => ipcRenderer.invoke('startup:info'),
  openWebFallback: () => ipcRenderer.invoke('startup:open-web'),
  openBackendLog: () => ipcRenderer.invoke('startup:open-log'),
  getRemoteCaptureStatus: () => ipcRenderer.invoke('remote-capture:status'),
  setRemoteCaptureEnabled: (enabled) => ipcRenderer.invoke('remote-capture:set-enabled', Boolean(enabled)),
  getUpdateStatus: () => ipcRenderer.invoke('updates:status'),
  checkForUpdates: () => ipcRenderer.invoke('updates:check'),
  downloadUpdate: () => ipcRenderer.invoke('updates:download'),
  installUpdate: () => ipcRenderer.invoke('updates:install'),
  onUpdateStatus: (handler) => {
    const listener = (_event, status) => handler(status);
    ipcRenderer.on('updates:status', listener);
    return () => ipcRenderer.removeListener('updates:status', listener);
  },
  onStartupError: (handler) => {
    const listener = (_event, payload) => handler(payload);
    ipcRenderer.on('startup-error', listener);
    return () => ipcRenderer.removeListener('startup-error', listener);
  },
});