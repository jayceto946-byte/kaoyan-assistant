import React, { useEffect, useRef, useState } from 'react';
import { CalendarDays, GraduationCap, ImagePlus, Send, Shuffle, Square } from 'lucide-react';
import { get, post } from '../api/client';
import ChatHistorySidebar from '../components/ChatHistorySidebar';
import ChatMessage from '../components/ChatMessage';
import { ErrorBoundary } from '../components/ErrorBoundary';
import { useChatContext } from '../contexts/ChatContext';
import { useChat } from '../hooks/useChat';

type BookOption = { name: string };
type ReportMode = 'daily' | 'weekly';
type ActionMode = ReportMode | 'exercise';

const ChatPage: React.FC = () => {
  const [input, setInput] = useState('');
  const [books, setBooks] = useState<BookOption[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(() => window.localStorage.getItem('kaoyan_chat_sidebar') !== 'closed');
  const [actionLoading, setActionLoading] = useState<ActionMode | null>(null);
  const { messages, isLoading, sendMessage, stop } = useChat();
  const { bookName, setBookName, subject, setSubject, conversationId, newConversation, loadConversation, addMessage } = useChatContext();
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const loadBooks = async () => {
      try {
        const res = await get('/books/list');
        if (res?.success) setBooks(res.data || []);
      } catch {
        setBooks([]);
      }
    };
    const onChanged = () => loadBooks();
    window.addEventListener('books:changed', onChanged);
    loadBooks();
    return () => window.removeEventListener('books:changed', onChanged);
  }, []);

  useEffect(() => {
    window.localStorage.setItem('kaoyan_chat_sidebar', sidebarOpen ? 'open' : 'closed');
  }, [sidebarOpen]);

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [messages]);

  const switchBook = async (name: string) => {
    if (!name) {
      setBookName('');
      return;
    }
    try {
      const res = await get(`/books/switch/${encodeURIComponent(name)}`);
      if (res?.success) setBookName(res.data.name);
    } catch {
      setBookName(name);
    }
  };

  const handleSubmit = (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;
    sendMessage(input);
    setInput('');
    if (textareaRef.current) textareaRef.current.style.height = 'auto';
  };

  const handleInput = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    setInput(e.target.value);
    e.target.style.height = 'auto';
    e.target.style.height = Math.min(e.target.scrollHeight, 160) + 'px';
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  };

  const showReport = async (mode: ReportMode) => {
    if (actionLoading) return;
    const isDaily = mode === 'daily';
    const title = isDaily ? '学习日报' : '学习周报';
    addMessage({ role: 'user', content: `展示我的${title}` });
    setActionLoading(mode);
    try {
      const params = new URLSearchParams({ book_name: bookName || 'default', subject, days: isDaily ? '1' : '7' });
      const res = await get(`/reports/weekly?${params.toString()}`);
      if (!res?.success) throw new Error(res?.message || `生成${title}失败`);
      addMessage({ role: 'assistant', content: '', stage: 'done', reportCard: { kind: mode, report: res.data } });
    } catch (err) {
      addMessage({ role: 'assistant', content: `出错了：${err instanceof Error ? err.message : String(err)}`, stage: 'error' });
    } finally {
      setActionLoading(null);
    }
  };

  const pickRandomExercise = async () => {
    if (actionLoading) return;
    addMessage({ role: 'user', content: '随机抽一道习题' });
    setActionLoading('exercise');
    const bookQuery = bookName ? `?book_name=${encodeURIComponent(bookName)}` : '';
    try {
      const statuses = ['needs_review', 'practicing', 'new', ''];
      let pool: any[] = [];
      for (const status of statuses) {
        const res = await post(`/exercises/list${bookQuery}`, { search_kw: '', status, limit: 100 });
        if (res?.success && Array.isArray(res.data) && res.data.length) {
          pool = status ? res.data : res.data.filter((item: any) => item.status !== 'mastered');
          if (pool.length) break;
        }
      }
      if (!pool.length) {
        addMessage({ role: 'assistant', content: '习题库里暂时没有可抽取的题目。可以先在“习题库”导入 Word/PDF，或从错题本转入习题。', stage: 'done' });
        return;
      }
      const record = pool[Math.floor(Math.random() * pool.length)];
      addMessage({ role: 'assistant', content: '', stage: 'done', exerciseCard: { record } });
    } catch (err) {
      addMessage({ role: 'assistant', content: `出错了：${err instanceof Error ? err.message : String(err)}`, stage: 'error' });
    } finally {
      setActionLoading(null);
    }
  };

  const openMistakeQuickCapture = () => {
    addMessage({ role: 'user', content: '打开错题速录' });
    addMessage({ role: 'assistant', content: '', stage: 'done', utilityCard: { kind: 'mistake_quick_capture' } });
  };

  return (
    <div className="relative flex h-full min-w-0 bg-bg-primary">
      <ChatHistorySidebar
        open={sidebarOpen}
        books={books}
        subject={subject}
        bookName={bookName}
        conversationId={conversationId}
        refreshKey={messages.length}
        onToggle={() => setSidebarOpen((prev) => !prev)}
        onSubjectChange={setSubject}
        onBookChange={switchBook}
        onNewConversation={newConversation}
        onLoadConversation={({ id, messages: nextMessages, subject: nextSubject, bookName: nextBookName }) => loadConversation(id, nextMessages, { subject: nextSubject, bookName: nextBookName })}
      />

      <div className="flex min-w-0 flex-1 flex-col">
        <div className="border-b border-border bg-bg-primary/95 px-6 py-4">
          <div className="mx-auto flex max-w-6xl items-center justify-between gap-3">
            <div className={`flex items-center gap-3 ${sidebarOpen ? '' : 'pl-9'}`}>
              <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-bg-card shadow-sm">
                <GraduationCap className="h-5 w-5 text-accent" />
              </div>
              <div>
                <h2 className="text-base font-semibold text-text-primary">学习对话</h2>
              </div>
            </div>
          </div>
        </div>

        <div ref={scrollRef} className="flex-1 overflow-y-auto px-5 py-6">
          <div className="mx-auto max-w-5xl space-y-2">
            {messages.length === 0 && (
              <div className="flex min-h-[55vh] flex-col items-center justify-center text-center text-text-secondary">
                <div className="mb-5 flex h-14 w-14 items-center justify-center rounded-2xl border border-border bg-bg-card shadow-sm">
                  <GraduationCap className="h-7 w-7 text-accent" />
                </div>
                <p className="text-lg font-semibold text-text-primary">从一个具体问题开始</p>
                <p className="mt-2 max-w-md text-sm leading-6">左侧可限定科目和教材，也可以切换任意历史会话继续追问。</p>
              </div>
            )}
            {messages.map((msg, i) => (
              <ErrorBoundary key={i}>
                <ChatMessage role={msg.role} content={msg.content} stage={msg.stage} linkedConcepts={msg.linkedConcepts} reportCard={msg.reportCard} exerciseCard={msg.exerciseCard} utilityCard={msg.utilityCard} />
              </ErrorBoundary>
            ))}
          </div>
        </div>

        <div className="border-t border-border bg-bg-secondary/95 p-4">
          <form onSubmit={handleSubmit} className="mx-auto flex max-w-5xl items-end gap-2">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={handleInput}
              onKeyDown={handleKeyDown}
              placeholder="输入问题..."
              disabled={isLoading}
              className="max-h-[160px] min-h-[48px] flex-1 resize-none overflow-y-auto rounded-xl border border-border bg-bg-card px-4 py-3 text-sm text-text-primary shadow-sm outline-none transition-colors placeholder-text-secondary focus:border-accent"
            />
            {isLoading ? (
              <button type="button" onClick={stop} className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl border border-red-300 bg-red-50 text-red-700 transition-colors hover:bg-red-100">
                <Square className="h-4 w-4 fill-current" />
              </button>
            ) : (
              <button type="submit" disabled={!input.trim()} className="flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-accent text-white shadow-sm transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-40">
                <Send className="h-4 w-4" />
              </button>
            )}
          </form>

          <div className="mx-auto mt-2 max-w-5xl">
            <div className="flex flex-wrap gap-2">
              <button type="button" onClick={() => showReport('daily')} disabled={Boolean(actionLoading)} className={`flex h-8 items-center gap-1.5 rounded-lg border px-3 text-xs transition-colors ${actionLoading === 'daily' ? 'border-accent/30 bg-[var(--accent-soft)] text-accent' : 'border-border bg-bg-card text-text-secondary hover:border-accent/40 hover:text-text-primary'} disabled:opacity-60`}>
                <CalendarDays className="h-3.5 w-3.5" />
                {actionLoading === 'daily' ? '整理日报' : '学习日报'}
              </button>
              <button type="button" onClick={() => showReport('weekly')} disabled={Boolean(actionLoading)} className={`flex h-8 items-center gap-1.5 rounded-lg border px-3 text-xs transition-colors ${actionLoading === 'weekly' ? 'border-accent/30 bg-[var(--accent-soft)] text-accent' : 'border-border bg-bg-card text-text-secondary hover:border-accent/40 hover:text-text-primary'} disabled:opacity-60`}>
                <CalendarDays className="h-3.5 w-3.5" />
                {actionLoading === 'weekly' ? '整理周报' : '学习周报'}
              </button>
              <button type="button" onClick={pickRandomExercise} disabled={Boolean(actionLoading)} className={`flex h-8 items-center gap-1.5 rounded-lg border px-3 text-xs transition-colors ${actionLoading === 'exercise' ? 'border-accent/30 bg-[var(--accent-soft)] text-accent' : 'border-border bg-bg-card text-text-secondary hover:border-accent/40 hover:text-text-primary'} disabled:opacity-60`}>
                <Shuffle className="h-3.5 w-3.5" />
                {actionLoading === 'exercise' ? '抽题中' : '随机抽题'}
              </button>
              <button type="button" onClick={openMistakeQuickCapture} className="flex h-8 items-center gap-1.5 rounded-lg border border-border bg-bg-card px-3 text-xs text-text-secondary transition-colors hover:border-accent/40 hover:text-text-primary">
                <ImagePlus className="h-3.5 w-3.5" />
                错题速录
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ChatPage;