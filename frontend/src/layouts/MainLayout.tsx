import React, { useEffect, useState } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { BarChart3, BookOpen, ClipboardList, GraduationCap, Menu, MessageSquare, PanelLeftClose, PanelLeftOpen, Upload, X } from 'lucide-react';
import { get } from '../api/client';
import { useChatContext } from '../contexts/ChatContext';
import type { ChatMessage as ContextChatMessage } from '../contexts/ChatContext';
import ChatHistorySidebar from '../components/ChatHistorySidebar';
import SystemHealth from '../components/SystemHealth';

const navItems = [
  { to: '/', icon: MessageSquare, label: '对话' },
  { to: '/learning', icon: BarChart3, label: '学习情况' },
  { to: '/mistakes', icon: GraduationCap, label: '错题本' },
  { to: '/exercises', icon: ClipboardList, label: '习题库' },
  { to: '/books', icon: Upload, label: '教材导入' },
];

function detectCompactLayout() {
  if (typeof window === 'undefined' || typeof navigator === 'undefined') return false;
  const width = window.innerWidth || document.documentElement.clientWidth || 1280;
  const ua = navigator.userAgent || '';
  const mobileUa = /Android|iPhone|iPod|Mobile|Windows Phone/i.test(ua);
  const tabletUa = /iPad|Tablet|PlayBook|Silk/i.test(ua) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const coarsePointer = typeof window.matchMedia === 'function' && window.matchMedia('(pointer: coarse)').matches;

  if (width <= 760) return true;
  if ((mobileUa || tabletUa || coarsePointer) && width <= 1180) return true;
  return false;
}

const MainLayout: React.FC = () => {
  const navigate = useNavigate();
  const initialCompact = detectCompactLayout();
  const [compactLayout, setCompactLayout] = useState(initialCompact);
  const [sidebarExpanded, setSidebarExpanded] = useState(!initialCompact);
  const { bookName, setBookName, subject, setSubject, conversationId, messages, newConversation, loadConversation } = useChatContext();

  useEffect(() => {
    const updateLayout = () => {
      const compact = detectCompactLayout();
      setCompactLayout(compact);
      if (compact) setSidebarExpanded(false);
    };
    updateLayout();
    window.addEventListener('resize', updateLayout);
    window.addEventListener('orientationchange', updateLayout);
    return () => {
      window.removeEventListener('resize', updateLayout);
      window.removeEventListener('orientationchange', updateLayout);
    };
  }, []);

  const startNewConversation = () => {
    newConversation();
    setSidebarExpanded(false);
    navigate('/');
  };

  const loadExistingConversation = ({ id, messages: nextMessages, subject: nextSubject, bookName: nextBookName }: { id: string; messages: ContextChatMessage[]; subject: string; bookName: string }) => {
    loadConversation(id, nextMessages, { subject: nextSubject, bookName: nextBookName });
    setSidebarExpanded(false);
    navigate('/');
  };

  const switchBook = async (name: string) => {
    if (!name) {
      setBookName('');
      return;
    }
    try {
      const res = await get(`/books/switch/${encodeURIComponent(name)}`);
      if (res?.success) {
        setBookName(res.data?.name || name);
        if (res.data?.subject) setSubject(res.data.subject);
      } else {
        setBookName(name);
      }
    } catch {
      setBookName(name);
    }
  };

  const historySidebar = (
    <ChatHistorySidebar
      embedded
      open
      subject={subject}
      bookName={bookName}
      conversationId={conversationId}
      refreshKey={messages.length}
      onToggle={() => undefined}
      onSubjectChange={setSubject}
      onBookChange={switchBook}
      onNewConversation={startNewConversation}
      onLoadConversation={loadExistingConversation}
    />
  );

  const sidebarContent = (mode: 'desktop' | 'drawer') => (
    <>
      <div className="flex h-[52px] items-center border-b border-border bg-bg-card/86 px-3 backdrop-blur">
        <div className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-[var(--surface-black)]">
          <BookOpen className="h-4.5 w-4.5 text-white" />
        </div>
        <div className="ml-3 flex min-w-0 flex-1 items-center gap-2">
          <h1 className="type-title truncate text-text-primary">考研助手</h1>
          <SystemHealth bookName={bookName} />
        </div>
        <button
          type="button"
          onClick={() => setSidebarExpanded(false)}
          className="ml-2 flex h-8 w-8 items-center justify-center rounded-full border border-border bg-bg-card text-text-secondary hover:border-accent/50 hover:text-accent"
          aria-label={mode === 'desktop' ? '折叠侧边栏' : '关闭侧边栏'}
        >
          {mode === 'desktop' ? <PanelLeftClose className="h-4 w-4" /> : <X className="h-4 w-4" />}
        </button>
      </div>

      <section className="flex min-h-0 flex-1 border-b border-border">{historySidebar}</section>

      <nav className="p-2.5">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            onClick={() => mode === 'drawer' && setSidebarExpanded(false)}
            className={({ isActive }) =>
              `mb-1 flex items-center rounded-full border px-3 py-2.5 type-control transition-colors ${
                isActive
                  ? 'border-accent/30 bg-[var(--accent-soft)] text-accent'
                  : 'border-transparent text-text-secondary hover:border-border hover:bg-bg-card hover:text-text-primary'
              }`
            }
          >
            <item.icon className="mr-3 h-4 w-4" />
            {item.label}
          </NavLink>
        ))}
      </nav>
    </>
  );

  const rail = (mode: 'desktop' | 'compact') => (
    <aside className={`${mode === 'desktop' ? 'w-[68px]' : 'w-[52px]'} relative z-20 flex flex-shrink-0 flex-col items-center border-r border-black bg-[var(--surface-black)] py-2`}>
      <button
        type="button"
        onClick={() => setSidebarExpanded(true)}
        className="mb-2 flex h-9 w-9 items-center justify-center rounded-full border border-white/15 bg-white/10 text-white hover:bg-white/16"
        aria-label="展开侧边栏"
      >
        {mode === 'desktop' ? <PanelLeftOpen className="h-4.5 w-4.5" /> : <Menu className="h-4.5 w-4.5" />}
      </button>
      <button
        type="button"
        onClick={startNewConversation}
        className="mb-3 flex h-9 w-9 items-center justify-center rounded-full border border-white/15 bg-white/10 text-white/72 hover:bg-white/16 hover:text-white"
        aria-label="新会话"
      >
        <MessageSquare className="h-4.5 w-4.5" />
      </button>
      <nav className="mt-auto flex w-full flex-col items-center gap-1 pb-1">
        {navItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className={({ isActive }) =>
              `flex h-10 w-10 items-center justify-center rounded-lg transition-colors ${
                isActive ? 'bg-white text-accent' : 'text-white/62 hover:bg-white/10 hover:text-white'
              }`
            }
            aria-label={item.label}
            title={item.label}
          >
            <item.icon className="h-4.5 w-4.5" />
          </NavLink>
        ))}
      </nav>
    </aside>
  );

  return (
    <div data-layout={compactLayout ? 'compact' : 'desktop'} data-sidebar={sidebarExpanded ? 'expanded' : 'collapsed'} className="app-shell flex h-[100dvh] w-full overflow-hidden bg-bg-primary text-text-primary">
      {!compactLayout && (sidebarExpanded ? (
        <aside className="relative z-20 flex w-[292px] flex-shrink-0 flex-col overflow-hidden border-r border-border bg-bg-secondary/95 backdrop-blur 2xl:w-[320px]">
          {sidebarContent('desktop')}
        </aside>
      ) : rail('desktop'))}

      {compactLayout && rail('compact')}

      {compactLayout && sidebarExpanded && (
        <div className="fixed inset-0 z-50 flex bg-black/35">
          <aside className="flex h-full w-[min(292px,86vw)] flex-col overflow-hidden border-r border-border bg-bg-secondary">
            {sidebarContent('drawer')}
          </aside>
          <button type="button" className="min-w-0 flex-1" onClick={() => setSidebarExpanded(false)} aria-label="关闭侧边栏" />
        </div>
      )}

      <main className="relative z-0 flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-bg-primary">
        <Outlet />
      </main>
    </div>
  );
};

export default MainLayout;
