export {};

type DesktopUpdateStatus = {
  status: 'idle' | 'disabled' | 'checking' | 'available' | 'none' | 'downloading' | 'downloaded' | 'installing' | 'error';
  message: string;
  currentVersion?: string;
  updateInfo?: { version?: string; releaseName?: string; releaseNotes?: string } | null;
  progress?: { percent?: number; transferred?: number; total?: number } | null;
};

type RemoteCaptureStatus = {
  enabled: boolean;
  urls: string[];
  port: number;
  ready: boolean;
  message: string;
};

declare global {
  interface Window {
    kaoyanDesktop?: {
      isElectron: boolean;
      minimize: () => Promise<void>;
      toggleMaximize: () => Promise<boolean>;
      close: () => Promise<void>;
      restart?: () => Promise<boolean>;
      getRemoteCaptureStatus?: () => Promise<RemoteCaptureStatus>;
      setRemoteCaptureEnabled?: (enabled: boolean) => Promise<RemoteCaptureStatus>;
      getUpdateStatus?: () => Promise<DesktopUpdateStatus>;
      checkForUpdates?: () => Promise<DesktopUpdateStatus>;
      downloadUpdate?: () => Promise<DesktopUpdateStatus>;
      installUpdate?: () => Promise<DesktopUpdateStatus>;
      onUpdateStatus?: (handler: (status: DesktopUpdateStatus) => void) => () => void;
      onStartupError?: (handler: (message: string) => void) => void;
    };
  }
}
