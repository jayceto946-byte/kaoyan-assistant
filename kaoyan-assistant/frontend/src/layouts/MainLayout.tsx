import React, { useState, useEffect } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { MessageSquare, BookOpen, GraduationCap, Upload, Loader2, BarChart3, ClipboardList, ChevronDown } from 'lucide-react';
import { get } from '../api/client';
import { useChatContext } from '../contexts/ChatContext';
import ChapterTree, { type ChapterNode } from '../components/ChapterTree';
import SystemHealth from '../components/SystemHealth';

interface BookInfo {
  name: string;
  chapter_count: number;
  chapters?: ChapterNode[];
}

const navItems = [
  { to: '/', icon: MessageSquare, label: '对话' },
  { to: '/learning', icon: BarChart3, label: '学习情况' },
  { to: '/mistakes', icon: GraduationCap, label: '错题本' },
  { to: '/exercises', icon: ClipboardList, label: '习题库' },
  { to: '/books', icon: Upload, label: '教材导入' },
];

const MainLayout: React.FC = () => {
  const [books, setBooks] = useState<{ name: string }[]>([]);
  const [currentBook, setCurrentBook] = useState<BookInfo | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const { setBookName } = useChatContext();

  useEffect(() => {
    const loadBooks = async () => {
      try {
        setLoading(true);
        setError('');
        const res = await get('/books/list');
        if (!res || !res.success) {
          setError(res?.message || '获取教材列表失败');
          setLoading(false);
          return;
        }
        const bookList = res.data || [];
        setBooks(bookList);
        if (bookList.length > 0) await switchBook(bookList[0].name);
        else setError('暂无教材，请先导入');
      } catch (err) {
        console.error('[MainLayout] loadBooks error:', err);
        setError('连接后端失败，请确认后端已启动');
      } finally {
        setLoading(false);
      }
    };
    const handleBooksChanged = () => loadBooks();
    window.addEventListener('books:changed', handleBooksChanged);
    loadBooks();
    return () => window.removeEventListener('books:changed', handleBooksChanged);
  }, []);

  const switchBook = async (name: string) => {
    try {
      const res = await get(`/books/switch/${encodeURIComponent(name)}`);
      if (!res || !res.success) {
        console.warn('切换教材失败:', res?.message);
        return;
      }
      setCurrentBook(res.data);
      setBookName(res.data.name);
    } catch (err) {
      console.error('[MainLayout] switchBook error:', err);
    }
  };

  return (
    <div className="app-shell flex h-[100dvh] w-screen overflow-hidden bg-bg-primary text-text-primary">
      <aside className="flex w-[292px] flex-shrink-0 flex-col border-r border-border bg-bg-secondary/90">
        <div className="flex h-[72px] items-center border-b border-border px-5">
          <div className="mr-3 flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-bg-card shadow-sm">
            <BookOpen className="h-5 w-5 text-accent" />
          </div>
          <div className="flex min-w-0 flex-1 items-center gap-2">
            <h1 className="truncate text-base font-semibold tracking-normal text-text-primary">考研助手</h1>
            <SystemHealth bookName={currentBook?.name} />
          </div>
        </div>

        <section className="border-b border-border px-4 py-4">
          <div className="mb-2 flex items-center justify-between gap-2">
            <label className="text-xs font-medium text-text-secondary">当前教材</label>
            {currentBook && !loading && <span className="rounded bg-bg-card px-2 py-0.5 text-[11px] text-text-secondary">{currentBook.chapter_count} 章</span>}
          </div>

          {loading ? (
            <div className="flex items-center gap-2 rounded-lg border border-border bg-bg-card px-3 py-2 text-sm text-text-secondary shadow-sm">
              <Loader2 className="h-4 w-4 animate-spin" />
              加载中...
            </div>
          ) : error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{error}</div>
          ) : (
            <div className="relative">
              <select
                className="app-select w-full pr-9 shadow-sm"
                value={currentBook?.name || ''}
                onChange={(e) => {
                  const name = e.target.value;
                  if (name) switchBook(name);
                }}
              >
                {books.length === 0 && <option value="">暂无教材</option>}
                {books.map((b) => <option key={b.name} value={b.name}>{b.name}</option>)}
              </select>
              <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-text-secondary" />
            </div>
          )}
        </section>

        <section className="flex min-h-0 flex-1 flex-col border-b border-border">
          <div className="flex items-center justify-between px-4 py-3">
            <div className="text-xs font-medium text-text-secondary">目录</div>
            <div className="text-[11px] text-text-secondary">章节索引</div>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto px-3 pb-3">
            {currentBook?.chapters && currentBook.chapters.length > 0 ? (
              <ChapterTree chapters={currentBook.chapters} />
            ) : (
              <div className="rounded-lg border border-dashed border-border bg-bg-card px-4 py-3 text-sm text-text-secondary">{loading ? '加载目录...' : '暂无目录'}</div>
            )}
          </div>
        </section>


        <nav className="p-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `mb-1 flex items-center rounded-lg border px-3 py-2.5 text-sm transition-colors ${
                  isActive
                    ? 'border-accent/25 bg-[var(--accent-soft)] text-accent shadow-sm'
                    : 'border-transparent text-text-secondary hover:border-border hover:bg-bg-card hover:text-text-primary'
                }`
              }
            >
              <item.icon className="mr-3 h-4 w-4" />
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <main className="flex min-w-0 flex-1 flex-col overflow-hidden bg-bg-primary">
        <Outlet context={{ currentBook }} />
      </main>
    </div>
  );
};

export default MainLayout;
