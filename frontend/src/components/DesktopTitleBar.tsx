export default function DesktopTitleBar() {
  if (!window.kaoyanDesktop?.isElectron) return null;
  return <div className="electron-titlebar" aria-hidden="true" />;
}
