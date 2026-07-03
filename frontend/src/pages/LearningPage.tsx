import React, { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity,
  AlertTriangle,
  BookOpen,
  BrainCircuit,
  CalendarDays,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  ClipboardList,
  ExternalLink,

  HelpCircle,
  Loader2,
  RefreshCw,
} from 'lucide-react';
import { get, post, runReadOnlyAgent } from '../api/client';
import ChatMessage from '../components/ChatMessage';
import AgentResultCard from '../components/chat/AgentResultCard';
import ScopeSelector, { type ScopeBookOption } from '../components/ScopeSelector';
import { useChatContext } from '../contexts/ChatContext';
import type { ChatAgentCard, ConceptCandidate, ReviewHistoryItem } from '../types';

interface LearningMistakeSummary {
  id: string;
  question_text: string;
  source?: string;
  subject?: string;
  chapter?: string | null;
  tags?: string[];
  mistake_type?: string[];
  next_review?: string | null;
  interval?: number | null;
  review_history?: ReviewHistoryItem[];
  linked_concepts?: ConceptCandidate[];
}

interface ConceptReviewCardData {
  name: string;
  priority: number;
  reasons: string[];
  days_since_seen?: number | null;
  days_since_review?: number | null;
  exposure_count: number;
  mastery_level?: number;
  weak?: boolean;
  recent_questions: Array<{ question: string; source: string; timestamp: string; weak?: boolean; mistake_id?: string }>;
  related_mistakes: LearningMistakeSummary[];
  textbook_snippets: Array<{ type: string; text: string; chapter?: string }>;
}

interface DailySubjectDetail {
  subject: string;
  book_name?: string;
  qa: number;
  mistake: number;
  total: number;
  concepts: Array<{ name: string; count: number }>;
}

interface DailyDetail {
  date: string;
  qa: number;
  mistake: number;
  total: number;
  subjects: DailySubjectDetail[];
}

interface LearningSummary {
  stats: {
    total_concepts: number;
    total_exposures: number;
    weak_count: number;
    forgotten_count: number;
  };
  top_concepts: Array<{ name: string; count: number; weak_flag?: boolean; source_chapters?: string[] }>;
  weak_concepts: Array<{ name: string; exposure_count: number; weak_reason?: string; last_weak_at?: string }>;
  review_queue: Array<{ name: string; reason: string }>;
  concept_review_plan: ConceptReviewCardData[];
  daily: Array<{ date: string; qa: number; mistake: number; total: number }>;
  daily_details?: DailyDetail[];
  mistake_stats: { total: number; due_today: number };
  mistake_weak_points: Array<{ name: string; type: string; count: number }>;
  subjects?: string[];
  selected_subject?: string;
  review_rules?: {
    mistake_due?: string;
    concept_due?: string;
    concept_reviewed?: string;
  };
  due_mistakes?: LearningMistakeSummary[];
}

const mistakeHref = (id: string) => `/mistakes?mistake_id=${encodeURIComponent(id)}`;

const LearningPage: React.FC = () => {
  const { bookName, setBookName, subject, setSubject } = useChatContext();
  const [books, setBooks] = useState<ScopeBookOption[]>([]);
  const [summary, setSummary] = useState<LearningSummary | null>(null);
  const [subjectFilter, setSubjectFilter] = useState(subject || '');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [reviewMessage, setReviewMessage] = useState('');
  const [agentCard, setAgentCard] = useState<ChatAgentCard | null>(null);
  const [agentLoading, setAgentLoading] = useState(false);
  const [expandedDueId, setExpandedDueId] = useState('');
  const [selectedActivityDate, setSelectedActivityDate] = useState('');

  useEffect(() => {
    let cancelled = false;
    get('/books/list')
      .then((res) => {
        if (!cancelled && res?.success) setBooks(res.data || []);
      })
      .catch(() => {
        if (!cancelled) setBooks([]);
      });
    const onChanged = () => {
      get('/books/list')
        .then((res) => setBooks(res?.success ? res.data || [] : []))
        .catch(() => setBooks([]));
    };
    window.addEventListener('books:changed', onChanged);
    return () => {
      cancelled = true;
      window.removeEventListener('books:changed', onChanged);
    };
  }, []);

  useEffect(() => {
    setSubjectFilter(subject || '');
  }, [subject]);

  const switchBook = async (name: string) => {
    if (!name) {
      setBookName('');
      setSummary(null);
      return;
    }
    try {
      const res = await get(`/books/switch/${encodeURIComponent(name)}`);
      if (res?.success) {
        setBookName(res.data.name);
        if (res.data.subject) setSubject(res.data.subject);
      }
    } catch {
      setBookName(name);
    }
  };

  const updateSubjectFilter = (value: string) => {
    setSubjectFilter(value);
    setSubject(value);
  };

  const load = useCallback(async () => {
    if (!bookName) return;
    setLoading(true);
    setError('');
    setReviewMessage('');
    try {
      const params = new URLSearchParams({ book_name: bookName });
      if (subjectFilter) params.set('subject', subjectFilter);
      const res = await get(`/kg/learning-summary?${params.toString()}`, 90000);
      if (res?.success) setSummary(res.data);
      else setError(res?.message || '学习情况加载失败');
    } catch (e) {
      setError(e instanceof DOMException && e.name === 'AbortError' ? '学习情况加载超时，请稍后重试或先缩小筛选范围。' : e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [bookName, subjectFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const handleConceptReview = async (name: string, quality = 4) => {
    if (!bookName) return;
    setReviewMessage('');
    try {
      const res = await post(`/kg/concept-review?book_name=${encodeURIComponent(bookName)}`, { name, quality });
      if (!res?.success) {
        setReviewMessage(res?.message || '概念复习记录失败');
        return;
      }
      setReviewMessage(`已记录「${name}」的概念复习`);
      await load();
    } catch (e) {
      setReviewMessage(e instanceof Error ? e.message : String(e));
    }
  };

  const runLearningAgent = async () => {
    if (!bookName || agentLoading) return;
    const question = '生成今日复习计划并指出最近薄弱点';
    setAgentLoading(true);
    setReviewMessage('');
    try {
      const response = await runReadOnlyAgent(question, bookName, subjectFilter || subject, '', true);
      setAgentCard({ question, response });
    } catch (e) {
      setReviewMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setAgentLoading(false);
    }
  };
  const subjects = summary?.subjects || [];
  const subjectSuggestions = Array.from(new Set([...subjects, ...books.map((book) => book.subject || '').filter(Boolean)]));

  return (
    <div className="learning-page flex h-full min-w-0 flex-col">
      <div className="learning-page-header flex flex-wrap items-center justify-between gap-3 border-b border-border bg-bg-primary px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-text-primary">学习情况</h2>
        </div>
        <div className="flex min-w-0 flex-wrap items-center justify-end gap-2">
          <ScopeSelector
            subject={subjectFilter}
            bookName={bookName}
            books={books}
            suggestions={subjectSuggestions}
            onSubjectChange={updateSubjectFilter}
            onBookChange={switchBook}
            allowAllSubjects
            align="right"
            width="wide"
            disabled={loading && !books.length}
          />
          <button
            onClick={runLearningAgent}
            disabled={agentLoading || loading || !bookName}
            className="flex items-center gap-1.5 rounded-xl border border-border bg-bg-primary px-3 py-1.5 text-sm text-text-primary transition-colors hover:border-accent disabled:opacity-50"
          >
            <BrainCircuit className={`h-4 w-4 ${agentLoading ? 'animate-pulse text-accent' : ''}`} />
            AI 复习计划
          </button>
          <button
            onClick={load}
            disabled={loading || !bookName}
            className="flex items-center gap-1.5 rounded-xl border border-border bg-bg-primary px-3 py-1.5 text-sm text-text-primary transition-colors hover:border-accent disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
            刷新
          </button>
        </div>
      </div>

      <div className="learning-page-content flex-1 overflow-y-auto p-6">
        {loading && (
          <div className="flex items-center justify-center gap-2 py-12 text-text-secondary">
            <Loader2 className="h-5 w-5 animate-spin" />
            正在整理学习情况，数据较多时可能需要十几秒
          </div>
        )}

        {error && !loading && (
          <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-[#9f3f2e]">{error}</div>
        )}

        {!bookName && !loading && !error && (
          <div className="rounded-xl border border-dashed border-border bg-bg-card px-4 py-10 text-center text-sm text-text-secondary">
            学习情况依赖教材知识图谱。请选择一个教材后查看概念、错题和复习队列。
          </div>
        )}

        {bookName && !loading && !error && summary && (
          <div className="space-y-6">
            {agentCard && <AgentResultCard card={agentCard} />}

            <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Metric icon={BrainCircuit} label="严格概念" value={summary.stats.total_concepts} />
              <Metric icon={Activity} label="高置信接触" value={summary.stats.total_exposures} />
              <Metric icon={AlertTriangle} label="薄弱概念" value={summary.stats.weak_count} tone="warn" />
              <Metric icon={CalendarDays} label="今日待复习错题" value={summary.mistake_stats.due_today} tone="accent" rules={summary.review_rules} />
            </div>

            {reviewMessage && <div className="rounded-lg border border-[#c9d8bd] bg-[#eef5e8] px-3 py-2 text-sm text-[#557a46]">{reviewMessage}</div>}

            <ExpandableSection title="待复习错题" count={summary.due_mistakes?.length || 0} defaultOpen={Boolean(summary.due_mistakes?.length)}>
              <div className="space-y-3 p-4">
                {summary.due_mistakes?.length ? (
                  summary.due_mistakes.map((mistake) => (
                    <MistakePreview
                      key={mistake.id}
                      mistake={mistake}
                      expanded={expandedDueId === mistake.id}
                      onToggle={() => setExpandedDueId(expandedDueId === mistake.id ? '' : mistake.id)}
                    />
                  ))
                ) : (
                  <Empty text="当前没有到期错题" compact />
                )}
              </div>
            </ExpandableSection>

            <ExpandableSection title="今日概念复习" count={summary.concept_review_plan?.length || 0} defaultOpen>
              <div className="learning-concept-grid grid grid-cols-1 gap-3 p-4 xl:grid-cols-2">
                {summary.concept_review_plan?.length ? (
                  summary.concept_review_plan.map((item) => (
                    <ConceptReviewCard key={item.name} item={item} onReview={handleConceptReview} />
                  ))
                ) : (
                  <div className="xl:col-span-2"><Empty text="暂无需要优先复习的概念" compact /></div>
                )}
              </div>
            </ExpandableSection>

            <ExpandableSection title="待复习概念" count={summary.review_queue.length} defaultOpen>
              <div className="space-y-2 p-4">
                {summary.review_queue.length ? (
                  summary.review_queue.map((item) => (
                    <div key={item.name} className="flex items-center justify-between rounded border border-border bg-bg-primary px-3 py-2 text-sm">
                      <span className="truncate text-text-primary">{item.name}</span>
                      <span className="ml-3 text-xs text-text-secondary">{item.reason === 'weak' ? '薄弱' : '遗忘'}</span>
                    </div>
                  ))
                ) : (
                  <Empty text="暂无待复习概念" compact />
                )}
              </div>
            </ExpandableSection>

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-3">
              <Panel title="高频概念">
                {summary.top_concepts.length ? (
                  summary.top_concepts.map((item) => (
                    <RankRow key={item.name} name={item.name} detail={`${item.count} 次`} />
                  ))
                ) : (
                  <Empty text="暂无高置信概念" compact />
                )}
              </Panel>
              <Panel title="错题相关薄弱点">
                {summary.mistake_weak_points.length ? (
                  summary.mistake_weak_points.map((item) => (
                    <RankRow key={`${item.type}-${item.name}`} name={item.name} detail={`${item.count} 道`} />
                  ))
                ) : (
                  <Empty text="暂无错题薄弱点" compact />
                )}
              </Panel>
              <ActivityHeatmap
                daily={summary.daily_details || summary.daily.map((item) => ({ ...item, subjects: [] }))}
                selectedDate={selectedActivityDate}
                onSelectDate={setSelectedActivityDate}
              />
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

const toDateKey = (date: Date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

const heatColor = (total: number) => {
  if (total <= 0) return 'bg-[#f5f5f7] border-[#e0e0e0]';
  if (total === 1) return 'bg-[#dceeff] border-[#b8dcff]';
  if (total <= 3) return 'bg-[#a8d4ff] border-[#7dbdff]';
  if (total <= 7) return 'bg-[#3f97e8] border-[#237fca]';
  return 'bg-[#0066cc] border-[#0057ad]';
};

const ActivityHeatmap = ({ daily, selectedDate, onSelectDate }: { daily: DailyDetail[]; selectedDate: string; onSelectDate: (date: string) => void }) => {
  const detailByDate = new Map(daily.map((item) => [item.date, item]));
  const today = new Date();
  const start = new Date(today);
  start.setHours(0, 0, 0, 0);
  start.setDate(today.getDate() - today.getDay() - 77);
  const weeks = Array.from({ length: 12 }, (_, weekIndex) => (
    Array.from({ length: 7 }, (_, dayIndex) => {
      const date = new Date(start);
      date.setDate(start.getDate() + weekIndex * 7 + dayIndex);
      const key = toDateKey(date);
      return { key, detail: detailByDate.get(key) };
    })
  ));
  const latest = daily.find((item) => item.total > 0)?.date || toDateKey(today);
  const currentDate = selectedDate || latest;
  const current = detailByDate.get(currentDate);

  return (
    <section className="rounded-[18px] border border-border bg-bg-card">
      <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
          <CalendarDays className="h-4 w-4 text-accent" /> 最近每日活动
        </div>
        <div className="flex items-center gap-1 text-[11px] text-text-secondary">
          <span>少</span>
          {[0, 1, 3, 7, 10].map((value) => <span key={value} className={`h-3 w-3 rounded-sm border ${heatColor(value)}`} />)}
          <span>多</span>
        </div>
      </div>
      <div className="space-y-4 p-4">
        <div className="overflow-x-auto pb-1">
          <div className="grid w-max grid-flow-col grid-rows-7 gap-1">
            {weeks.flatMap((week) => week.map(({ key, detail }) => (
              <button
                key={key}
                type="button"
                onClick={() => onSelectDate(key)}
                title={`${key}：${detail?.total || 0} 次`}
                className={`h-3.5 w-3.5 rounded-sm border transition-transform hover:scale-110 ${heatColor(detail?.total || 0)} ${currentDate === key ? 'ring-2 ring-accent ring-offset-1 ring-offset-bg-card' : ''}`}
                aria-label={`${key} 学习活动 ${detail?.total || 0} 次`}
              />
            )))}
          </div>
        </div>
        <div className="rounded border border-border bg-bg-primary p-3">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div className="text-sm font-semibold text-text-primary">{currentDate}</div>
            <div className="text-xs text-text-secondary">{current?.total || 0} 次</div>
          </div>
          {current ? (
            <div className="space-y-3">
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded border border-border px-2 py-0.5 text-text-secondary">问答 {current.qa}</span>
                <span className="rounded border border-border px-2 py-0.5 text-text-secondary">错题 {current.mistake}</span>
              </div>
              {current.subjects.length ? current.subjects.map((item) => (
                <div key={item.book_name || item.subject} className="space-y-2 border-t border-border pt-3 first:border-t-0 first:pt-0">
                  <div className="flex items-center justify-between gap-2 text-xs">
                    <span className="truncate font-medium text-text-primary">{item.book_name || item.subject}</span>
                    <span className="flex-shrink-0 text-text-secondary">问答 {item.qa} / 错题 {item.mistake}</span>
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {item.concepts.length ? item.concepts.map((concept) => (
                      <span key={concept.name} className="rounded border border-accent/25 bg-accent/10 px-2 py-0.5 text-xs text-accent-hover">
                        {concept.name}{concept.count > 1 ? ` ×${concept.count}` : ''}
                      </span>
                    )) : <span className="text-xs text-text-secondary">暂无概念明细</span>}
                  </div>
                </div>
              )) : <div className="text-xs text-text-secondary">暂无教材概念明细</div>}
            </div>
          ) : (
            <div className="py-6 text-center text-xs text-text-secondary">这一天暂无记录</div>
          )}
        </div>
      </div>
    </section>
  );
};
const ConceptReviewCard = ({ item, onReview }: { item: ConceptReviewCardData; onReview: (name: string, quality?: number) => void }) => {
  const [open, setOpen] = useState(false);
  const linkedMistakes = item.related_mistakes.slice(0, 4);

  return (
    <article className="concept-review-card rounded-xl border border-border bg-bg-primary p-3 sm:p-4">
      <div className="flex items-start justify-between gap-2 sm:gap-3">
        <button type="button" onClick={() => setOpen(!open)} className="min-w-0 flex-1 text-left">
          <div className="flex min-w-0 items-center justify-start gap-2">
            {open ? <ChevronDown className="h-4 w-4 text-accent" /> : <ChevronRight className="h-4 w-4 text-text-secondary" />}
            <BrainCircuit className={`h-4 w-4 ${item.weak ? 'text-[#9f3f2e]' : 'text-accent'}`} />
            <h3 className="min-w-0 flex-1 truncate text-sm font-semibold text-text-primary">{item.name}</h3>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {item.reasons.map((reason) => (
              <span key={reason} className="max-w-full truncate rounded border border-accent/25 bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent-hover">{reason}</span>
            ))}
          </div>
        </button>
        <button onClick={() => onReview(item.name, 4)} className="flex h-8 flex-shrink-0 items-center gap-1.5 whitespace-nowrap rounded border border-border px-2.5 py-1 text-xs text-text-primary hover:border-accent hover:text-accent">
          <CheckCircle2 className="h-3.5 w-3.5" /> 已复习
        </button>
      </div>

      {open && (
        <div className="mt-4 grid gap-3 text-sm md:grid-cols-2">
          <MiniBlock icon={BookOpen} title="教材线索">
            {item.textbook_snippets.length ? item.textbook_snippets.map((snippet, index) => (
              <p key={`${snippet.type}-${index}`} className="text-xs leading-5 text-text-secondary">{snippet.chapter || snippet.text}</p>
            )) : <p className="text-xs text-text-secondary">暂无章节线索</p>}
          </MiniBlock>
          <MiniBlock icon={ClipboardList} title="相关错题">
            {item.related_mistakes.length ? (
              <div className="space-y-2">
                <p className="text-xs leading-5 text-text-secondary">已关联 {item.related_mistakes.length} 道错题，题目内容在错题本中查看。</p>
                <div className="flex flex-wrap gap-2">
                  {linkedMistakes.map((mistake) => (
                    <Link key={mistake.id} to={mistakeHref(mistake.id)} className="inline-flex items-center gap-1 rounded border border-border bg-bg-primary px-2 py-1 text-xs text-accent-hover hover:border-accent hover:text-accent">
                      {mistake.id} <ExternalLink className="h-3 w-3" />
                    </Link>
                  ))}
                  <Link to="/mistakes" className="inline-flex items-center gap-1 rounded border border-border bg-bg-primary px-2 py-1 text-xs text-text-primary hover:border-accent hover:text-accent">
                    打开错题本 <ExternalLink className="h-3 w-3" />
                  </Link>
                </div>
              </div>
            ) : <p className="text-xs text-text-secondary">暂无关联错题</p>}
          </MiniBlock>
        </div>
      )}
    </article>
  );
};

const MiniBlock = ({ icon: Icon, title, children }: { icon: React.ElementType; title: string; children: React.ReactNode }) => (
  <div className="rounded border border-border bg-bg-card p-3">
    <div className="mb-2 flex items-center gap-1.5 text-xs font-medium text-text-primary"><Icon className="h-3.5 w-3.5 text-accent" />{title}</div>
    <div className="space-y-2">{children}</div>
  </div>
);

const MistakePreview = ({ mistake, expanded, onToggle }: { mistake: LearningMistakeSummary; expanded: boolean; onToggle: () => void }) => (
  <div className="rounded-xl border border-border bg-bg-primary p-3">
    <button type="button" onClick={onToggle} className="flex w-full items-start justify-between gap-3 text-left">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
          {expanded ? <ChevronDown className="h-4 w-4 text-accent" /> : <ChevronRight className="h-4 w-4 text-text-secondary" />}
          <span className="truncate">{mistake.source || mistake.subject || mistake.id}</span>
        </div>
        <div className="mt-1 flex flex-wrap gap-2 text-xs text-text-secondary">
          {mistake.subject && <span>{mistake.subject}</span>}
          {mistake.chapter && <span>{mistake.chapter}</span>}
          {mistake.next_review && <span>到期 {mistake.next_review}</span>}
        </div>
      </div>
      <Link to={mistakeHref(mistake.id)} onClick={(e) => e.stopPropagation()} className="inline-flex flex-shrink-0 items-center gap-1 text-xs text-accent-hover hover:text-accent">
        打开 <ExternalLink className="h-3 w-3" />
      </Link>
    </button>
    {expanded && (
      <div className="mt-3 rounded border border-border bg-bg-card p-3">
        <ChatMessage role="assistant" content={mistake.question_text || mistake.id} linkedConcepts={mistake.linked_concepts || []} />
      </div>
    )}
  </div>
);

const Metric = ({ icon: Icon, label, value, tone = 'normal', rules }: { icon: React.ElementType; label: string; value: number; tone?: 'normal' | 'warn' | 'accent'; rules?: LearningSummary['review_rules'] }) => {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative rounded-[18px] border border-border bg-bg-card p-4">
      <div className="flex items-start justify-between gap-2 sm:gap-3">
        <div className="flex items-center gap-2 text-xs text-text-secondary">
          <Icon className={tone === 'warn' ? 'h-4 w-4 text-[#9f3f2e]' : tone === 'accent' ? 'h-4 w-4 text-accent' : 'h-4 w-4'} />
          {label}
        </div>
        {rules && (
          <button onClick={() => setOpen(!open)} className="rounded p-0.5 text-text-secondary hover:text-accent" title="复习标准">
            <HelpCircle className="h-4 w-4" />
          </button>
        )}
      </div>
      <div className="mt-2 text-2xl font-semibold text-text-primary">{value ?? 0}</div>
      {rules && open && (
        <div className="absolute right-3 top-9 z-20 w-[min(340px,calc(100vw-88px))] rounded-xl border border-border bg-bg-primary p-3 text-xs">
          <RuleItem title="待复习错题" text={rules.mistake_due || '错题按 SM-2 的 next_review 判断，到期即进入待复习。'} />
          <RuleItem title="今日概念复习" text={rules.concept_due || '概念按薄弱、错题关联、未接触天数和未复习天数综合排序。'} />
          <RuleItem title="已复习判定" text={rules.concept_reviewed || '点击已复习后写入复习时间和质量评分，并更新掌握度。'} />
        </div>
      )}
    </div>
  );
};

const RuleItem = ({ title, text }: { title: string; text: string }) => (
  <div className="space-y-1 border-b border-border py-2 last:border-b-0 last:pb-0 first:pt-0">
    <div className="font-semibold text-text-primary">{title}</div>
    <p className="leading-5 text-text-secondary">{text}</p>
  </div>
);

const Header = ({ title, count, open, onToggle }: { title: string; count?: number; open?: boolean; onToggle?: () => void }) => (
  <button type="button" onClick={onToggle} className="flex w-full items-center justify-between border-b border-border px-4 py-3 text-left text-sm font-medium text-text-primary">
    <span className="flex items-center gap-2">
      {open ? <ChevronDown className="h-4 w-4 text-accent" /> : <ChevronRight className="h-4 w-4 text-text-secondary" />}
      {title}
    </span>
    {typeof count === 'number' && <span className="text-xs font-normal text-text-secondary">{count}</span>}
  </button>
);

const ExpandableSection = ({ title, count, defaultOpen = false, children }: { title: string; count?: number; defaultOpen?: boolean; children: React.ReactNode }) => {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <section className="rounded-[18px] border border-border bg-bg-card">
      <Header title={title} count={count} open={open} onToggle={() => setOpen(!open)} />
      {open && children}
    </section>
  );
};

const Panel = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="rounded-[18px] border border-border bg-bg-card">
    <div className="border-b border-border px-4 py-3 text-sm font-medium text-text-primary">{title}</div>
    <div className="space-y-2 p-4">{children}</div>
  </section>
);

const RankRow = ({ name, detail }: { name: string; detail: string }) => (
  <div className="flex items-center justify-between gap-3 text-sm">
    <span className="truncate text-text-primary">{name}</span>
    <span className="flex-shrink-0 text-xs text-text-secondary">{detail}</span>
  </div>
);

const Empty = ({ text, compact = false }: { text: string; compact?: boolean }) => (
  <div className={`text-center text-sm text-text-secondary ${compact ? 'py-3' : 'py-8'}`}>{text}</div>
);

export default LearningPage;
