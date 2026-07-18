import { Maximize2, X } from 'lucide-react';

const desktopApi = window.kaoyanDesktop;

export default function DesktopTitleBar() {
  if (!desktopApi?.isElectron) return null;

  return (
    <div className="electron-titlebar" aria-label="桌面窗口控制">
      <div className="electron-titlebar-drag" aria-hidden="true" onDoubleClick={() => void desktopApi.toggleMaximize()} />
      <div className="electron-window-controls" aria-label="窗口控制">
        <button type="button" className="electron-control-button" aria-label="最大化或还原" title="最大化或还原" onClick={() => desktopApi.toggleMaximize()}>
          <Maximize2 size={15} strokeWidth={1.9} />
        </button>
        <button type="button" className="electron-control-button electron-control-close" aria-label="关闭" title="关闭" onClick={() => desktopApi.close()}>
          <X size={17} strokeWidth={2} />
        </button>
      </div>
    </div>
  );
}
