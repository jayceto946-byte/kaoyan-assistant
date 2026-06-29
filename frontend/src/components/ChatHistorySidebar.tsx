import { useEffect, useMemo, useState } from 'react';
import { BookOpen, ChevronRight, History, MessageSquarePlus, PanelLeftClose, PanelLeftOpen } from 'lucide-react';
import { get } from '../api/client';
import type { ChatMessage } from '../contexts/ChatContext';
import SubjectInput from './SubjectInput';

type BookOption = { name: string };
type ConversationSummary = {
  id: string;
  title: string;
  subject: string;
  book_name: string;
  updated_at: string;
  message_count: number;
};

const labels = {
  uncategorized: '\u672a\u5206\u7c7b',
  minutes: '\u5206\u949f',
  hours: '\u5c0f\u65f6',
  days: '\u5929',
  expandHistory: '\u5c55\u5f00\u5386\u53f2',
  collapseHistory: '\u6536\u8d77\u5386\u53f2',
  scope: '\u5bf9\u8bdd\u8303\u56f4',
  subject: '\u79d1\u76ee',
  allSubjects: '\u5168\u90e8\u5b66\u79d1 / \u81ea\u5b9a\u4e49',
  all: '\u5168\u90e8',
  book: '\u6559\u6750',
  noBook: '\u4e0d\u9650\u5b9a\u6559\u6750',
  newConversation: '\u65b0\u4f1a\u8bdd',
  history: '\u5386\u53f2\u8bb0\u5f55',
  loading: '\u52a0\u8f7d\u4e2d',
  empty: '\u6682\u65e0\u5bf9\u8bdd\u5386\u53f2',
};

const subjectColors = ['#2f7d6d', '#3b82f6', '#b45309', '#7c3aed', '#be123c', '#0f766e', '#4f46e5', '#64748b'];

function colorForSubject(subject = '') {
  const key = subject || labels.uncategorized;
  let hash = 0;
  for (const char of key) hash = (hash * 31 + char.charCodeAt(0)) >>> 0;
  return subjectColors[hash % subjectColors.length];
}

function relativeTime(value = '') {
  if (!value) return '';
  const time = new Date(value.replace(' ', 'T')).getTime();
  if (!Number.isFinite(time)) return '';
  const diff = Date.now() - time;
  const minute = 60_000;
  const hour = 60 * minute;
  const day = 24 * hour;
  if (diff < hour) return `${Math.max(1, Math.round(diff / minute))} ${labels.minutes}`;
  if (diff < day) return `${Math.round(diff / hour)} ${labels.hours}`;
  return `${Math.round(diff / day)} ${labels.days}`;
}

export default function ChatHistorySidebar({
  open,
  books,
  subject,
  bookName,
  conversationId,
  refreshKey,
  onToggle,
  onSubjectChange,
  onBookChange,
  onNewConversation,
  onLoadConversation,
}: {
  open: boolean;
  books: BookOption[];
  subject: string;
  bookName: string;
  conversationId: string;
  refreshKey: number;
  onToggle: () => void;
  onSubjectChange: (subject: string) => void;
  onBookChange: (bookName: string) => void;
  onNewConversation: () => void;
  onLoadConversation: (payload: { id: string; messages: ChatMessage[]; subject: string; bookName: string }) => void;
}) {
  const [conversations, setConversations] = useState<ConversationSummary[]>([]);
  const [loading, setLoading] = useState(false);

  const query = useMemo(() => {
    const params = new URLSearchParams({ limit: '80' });
    if (subject.trim()) params.set('subject', subject.trim());
    if (bookName.trim()) params.set('book_name', bookName.trim());
    return params.toString();
  }, [subject, bookName]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    get(`/chat/conversations?${query}`, 20000)
      .then((res) => {
        if (!cancelled) setConversations(res?.success ? res.data || [] : []);
      })
      .catch(() => {
        if (!cancelled) setConversations([]);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [query, conversationId, refreshKey]);

  const loadConversation = async (id: string) => {
    const res = await get(`/chat/conversations/${encodeURIComponent(id)}`, 20000);
    if (!res?.success || !res.data) return;
    const messages = (res.data.messages || []).map((item: any) => ({
      role: item.role === 'assistant' ? 'assistant' : 'user',
      content: item.content || '',
      stage: item.role === 'assistant' ? 'done' : undefined,
    })) as ChatMessage[];
    onLoadConversation({ id: res.data.id, messages, subject: res.data.subject || '', bookName: res.data.book_name || '' });
  };

  if (!open) {
    return (
      <button type="button" onClick={onToggle} className="absolute left-3 top-4 z-20 flex h-9 w-9 items-center justify-center rounded-lg border border-border bg-bg-card text-text-secondary shadow-sm hover:border-accent hover:text-accent" title={labels.expandHistory}>
        <PanelLeftOpen className="h-4 w-4" />
      </button>
    );
  }

  return (
    <aside className="relative flex h-full w-[294px] flex-shrink-0 flex-col border-r border-border bg-bg-secondary/90">
      <div className="border-b border-border p-4">
        <div className="mb-3 flex items-center justify-between">
          <div className="flex items-center gap-2 text-sm font-semibold text-text-primary"><BookOpen className="h-4 w-4 text-accent" />{labels.scope}</div>
          <button type="button" onClick={onToggle} className="rounded-lg p-1.5 text-text-secondary hover:bg-bg-card hover:text-text-primary" title={labels.collapseHistory}><PanelLeftClose className="h-4 w-4" /></button>
        </div>
        <div className="space-y-2">
          <div className="rounded-lg border border-border bg-bg-card px-3 py-2">
            <div className="mb-1 text-xs text-text-secondary">{labels.subject}</div>
            <div className="flex items-center gap-2">
              <SubjectInput value={subject} onChange={onSubjectChange} placeholder={labels.allSubjects} className="min-w-0 flex-1 border-0 bg-transparent px-0 text-sm outline-none" />
              {subject && <button type="button" onClick={() => onSubjectChange('')} className="text-xs text-text-secondary hover:text-accent">{labels.all}</button>}
            </div>
          </div>
          <div className="flex items-center gap-2 text-text-secondary"><ChevronRight className="h-4 w-4" /><div className="h-px flex-1 bg-border" /></div>
          <div className="rounded-lg border border-border bg-bg-card px-3 py-2">
            <div className="mb-1 text-xs text-text-secondary">{labels.book}</div>
            <select value={bookName} onChange={(e) => onBookChange(e.target.value)} className="app-select app-select-plain h-8 min-h-0 w-full border-0 bg-transparent px-0 pr-6 text-sm shadow-none">
              <option value="">{labels.noBook}</option>
              {books.map((book) => <option key={book.name} value={book.name}>{book.name}</option>)}
            </select>
          </div>
          <button type="button" onClick={onNewConversation} className="mt-2 flex h-9 w-full items-center justify-center gap-2 rounded-lg border border-border bg-bg-card text-sm text-text-primary shadow-sm hover:border-accent/50 hover:bg-[var(--accent-softer)]">
            <MessageSquarePlus className="h-4 w-4" />{labels.newConversation}
          </button>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col p-3">
        <div className="mb-2 flex items-center justify-between px-1 text-sm font-semibold text-text-primary"><span className="flex items-center gap-2"><History className="h-4 w-4 text-accent" />{labels.history}</span><span className="text-xs font-normal text-text-secondary">{loading ? labels.loading : `${conversations.length}`}</span></div>
        <div className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1">
          {conversations.length === 0 && <div className="rounded-lg border border-dashed border-border px-3 py-8 text-center text-sm text-text-secondary">{labels.empty}</div>}
          {conversations.map((item) => {
            const color = colorForSubject(item.subject);
            const active = item.id === conversationId;
            const showColor = !subject.trim();
            return (
              <button key={item.id} type="button" onClick={() => loadConversation(item.id)} className={`relative w-full overflow-hidden rounded-lg px-3 py-2.5 text-left transition-colors ${active ? 'bg-bg-card shadow-sm' : 'hover:bg-bg-card/80'}`}>
                {showColor && <span className="pointer-events-none absolute inset-y-1 left-0 w-24 rounded-r-lg" style={{ background: `linear-gradient(90deg, ${color}80 0%, ${color}38 46%, transparent 100%)` }} />}
                <div className="relative flex items-center justify-between gap-2">
                  <div className="min-w-0 truncate text-sm font-medium text-text-primary">{item.title}</div>
                  <div className="flex-shrink-0 text-xs text-text-secondary">{relativeTime(item.updated_at)}</div>
                </div>
                <div className="relative mt-1 flex min-w-0 items-center gap-1 text-xs text-text-secondary">
                  <span className="truncate">{item.subject || labels.uncategorized}</span>
                  {item.book_name && <><span>/</span><span className="truncate">{item.book_name}</span></>}
                </div>
              </button>
            );
          })}
        </div>
      </div>
    </aside>
  );
}