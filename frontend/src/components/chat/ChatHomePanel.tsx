import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookMarked, BookOpenCheck, BrainCircuit, CalendarDays, ClipboardList, Loader2, Shuffle } from 'lucide-react';
import { get } from '../../api/client';
import { scopeContainsBook, type TextbookScopeOption } from '../../utils/textbookScopes';

export type ChatHomeBookOption = TextbookScopeOption;

export type ChatHomeDueMistake = {
  id: string;
  question_text?: string;
  subject?: string;
  chapter?: string | null;
  tags?: string[];
  linked_concepts?: Array<{ name: string }>;
  mistake_type?: string[];
};

export type ChatHomeConceptPlan = {
  name: string;
  reasons?: string[];
  related_mistakes?: ChatHomeDueMistake[];
  exposure_count?: number;
  priority?: number;
};

export type ChatHomeLearningSummary = {
  due_mistakes?: ChatHomeDueMistake[];
  concept_review_plan?: ChatHomeConceptPlan[];
  mistake_stats?: { due_today?: number; total?: number; by_type?: Record<string, number>; by_tag?: Record<string, number> };
  mistake_weak_points?: Array<{ name: string; count?: number; type?: string }>;
  weak_concepts?: Array<{ name: string; reasons?: string[] }>;
};

type ChatHomePanelProps = {
  bookName: string;
  subject: string;
  books: ChatHomeBookOption[];
  isLoading: boolean;
  onReviewMistake: (mistake: ChatHomeDueMistake) => void;
  onReviewConcept: (concept: ChatHomeConceptPlan, summary: ChatHomeLearningSummary | null) => void;
  onPracticeFromMemory: (summary: ChatHomeLearningSummary | null) => void;
  onShowReport: (mode: 'daily' | 'weekly') => void;
  onPickRandomExercise: () => void;
  onOpenHighlightDialog: () => void;
  onOpenMistakeQuickCapture: () => void;
};

function firstLine(value = '') {
  const line = value.replace(/\s+/g, ' ').trim();
  return line.length > 54 ? `${line.slice(0, 54)}...` : line;
}

export default function ChatHomePanel({
  bookName,
  subject,
  books,
  isLoading,
  onReviewMistake,
  onReviewConcept,
  onPracticeFromMemory,
  onShowReport,
  onPickRandomExercise,
  onOpenHighlightDialog,
  onOpenMistakeQuickCapture,
}: ChatHomePanelProps) {
  const [summary, setSummary] = useState<ChatHomeLearningSummary | null>(null);
  const [loading, setLoading] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    if (!bookName) {
      setSummary(null);
      setFailed(false);
      return;
    }
    let alive = true;
    setLoading(true);
    setFailed(false);
    const params = new URLSearchParams({ book_name: bookName, subject, limit: '12' });
    get(`/kg/learning-summary?${params.toString()}`, 30000)
      .then((res) => {
        if (!alive) return;
        setSummary(res?.success ? res.data || null : null);
        setFailed(!res?.success);
      })
      .catch(() => {
        if (!alive) return;
        setSummary(null);
        setFailed(true);
      })
      .finally(() => {
        if (alive) setLoading(false);
      });
    return () => {
      alive = false;
    };
  }, [bookName, subject]);

  const dueMistakes = summary?.due_mistakes || [];
  const conceptPlan = summary?.concept_review_plan || [];
  const firstMistake = dueMistakes[0];
  const firstConcept = conceptPlan[0];
  const currentScope = books.find((book) => scopeContainsBook(book, bookName));
  const scopeLabel = `${subject || '未限定学科'} / ${currentScope?.displayName || currentScope?.name || bookName || '通用问答'}`;

  return (
    <div className="mx-auto flex min-h-[55vh] w-full max-w-5xl flex-col justify-center py-8">
      <header className="mb-5">
        <div className="flex items-center gap-2">
          <h2 className="type-hero text-text-primary">下一步学习</h2>
          {loading && <Loader2 className="h-4 w-4 animate-spin text-accent" />}
        </div>
        <p className="type-body mt-1 text-text-secondary">根据复习时间和薄弱记录，先处理最值得回看的内容。</p>
        <p className="type-caption mt-2 text-text-secondary">当前范围：{scopeLabel}</p>
      </header>

      <section className="app-panel overflow-hidden">
        <div className="grid lg:grid-cols-[minmax(0,1.35fr)_minmax(260px,0.65fr)]">
          <div className="border-b border-border lg:border-b-0 lg:border-r">
            <div className="border-b border-border px-5 py-3">
              <h3 className="type-section-title text-text-primary">优先复习</h3>
            </div>
            <TaskRow
              icon={<BookOpenCheck className="h-4 w-4" />}
              title={dueMistakes.length ? `${dueMistakes.length} 道错题已到复习时间` : '今天没有到期错题'}
              description={firstMistake ? firstLine(firstMistake.question_text) : '可以从薄弱概念或题库练习继续。'}
              actionLabel="开始复习"
              disabled={!firstMistake || isLoading}
              onClick={() => firstMistake && onReviewMistake(firstMistake)}
              secondary={firstMistake ? <Link to={`/mistakes?mistake_id=${encodeURIComponent(firstMistake.id)}`} className="type-caption text-accent hover:underline">查看错题本</Link> : undefined}
            />
            <TaskRow
              icon={<BrainCircuit className="h-4 w-4" />}
              title={firstConcept ? `复习概念：${firstConcept.name}` : '暂无待复习概念'}
              description={firstConcept?.reasons?.[0] || '概念复习计划会根据错题和学习记录更新。'}
              actionLabel="开始复习"
              disabled={!firstConcept || isLoading}
              onClick={() => firstConcept && onReviewConcept(firstConcept, summary)}
              secondary={<Link to="/learning" className="type-caption text-accent hover:underline">查看学习情况</Link>}
            />
          </div>

          <div>
            <div className="border-b border-border px-5 py-3">
              <h3 className="type-section-title text-text-primary">其他入口</h3>
            </div>
            <div className="divide-y divide-border">
              <ToolButton icon={<ClipboardList className="h-4 w-4" />} label="按薄弱点抽题" onClick={() => onPracticeFromMemory(summary)} disabled={isLoading} />
              <ToolButton icon={<Shuffle className="h-4 w-4" />} label="随机抽一道题" onClick={onPickRandomExercise} disabled={isLoading} />
              <ToolButton icon={<BookMarked className="h-4 w-4" />} label="教材重点" onClick={onOpenHighlightDialog} disabled={!books.length || isLoading} />
              <ToolButton icon={<CalendarDays className="h-4 w-4" />} label="今日学习报告" onClick={() => onShowReport('daily')} disabled={isLoading} />
              <ToolButton icon={<ClipboardList className="h-4 w-4" />} label="快速录入错题" onClick={onOpenMistakeQuickCapture} disabled={isLoading} />
            </div>
          </div>
        </div>
      </section>
      {failed && <p className="type-caption mt-3 text-[var(--warning-text)]">学习摘要暂时不可用，仍可使用右侧入口继续学习。</p>}
    </div>
  );
}

function TaskRow({ icon, title, description, actionLabel, disabled, onClick, secondary }: { icon: React.ReactNode; title: string; description: string; actionLabel: string; disabled?: boolean; onClick: () => void; secondary?: React.ReactNode }) {
  return (
    <div className="flex items-start gap-3 border-b border-border px-5 py-4 last:border-b-0">
      <span className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg bg-[var(--accent-softer)] text-accent">{icon}</span>
      <div className="min-w-0 flex-1">
        <h4 className="type-section-title text-text-primary">{title}</h4>
        <p className="type-body mt-1 text-text-secondary">{description}</p>
        {secondary && <div className="mt-1.5">{secondary}</div>}
      </div>
      <button type="button" onClick={onClick} disabled={disabled} className="app-secondary-button flex-shrink-0 disabled:cursor-not-allowed disabled:opacity-45">{actionLabel}</button>
    </div>
  );
}

function ToolButton({ icon, label, disabled, onClick }: { icon: React.ReactNode; label: string; disabled?: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} className="type-control flex w-full items-center gap-3 px-5 py-3 text-left text-text-primary hover:bg-[var(--accent-softer)] disabled:cursor-not-allowed disabled:opacity-45">
      <span className="text-accent">{icon}</span>
      <span>{label}</span>
    </button>
  );
}