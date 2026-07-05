import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { BookMarked, BookOpenCheck, BrainCircuit, CalendarDays, ClipboardList, Loader2, ListChecks, MessageSquareText, Shuffle, Sparkles } from 'lucide-react';
import { get } from '../../api/client';

export type ChatHomeBookOption = { name: string; subject?: string };

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
  onShowReviewPlan: (summary: ChatHomeLearningSummary | null) => void;
  onPracticeFromMemory: (summary: ChatHomeLearningSummary | null) => void;
  onSummarizeMistakes: (summary: ChatHomeLearningSummary | null) => void;
  onShowReport: (mode: 'daily' | 'weekly') => void;
  onPickRandomExercise: () => void;
  onOpenHighlightDialog: () => void;
  onOpenMistakeQuickCapture: () => void;
};

const labels = {
  "morning": "上午好，把复习线索接上",
  "afternoon": "下午好，把复习线索接上",
  "evening": "晚上好，把复习线索接上",
  "noSubject": "未限定学科",
  "genericQa": "通用 QA",
  "continueTitle": "今天的继续点",
  "continueSub": "优先使用当前学科和教材，对话会正常记入历史。",
  "reviewMistakes": "复习到期错题",
  "dueMistakeSuffix": "道到期错题",
  "mistakeFallback": "暂无到期错题，先从薄弱概念开始。",
  "openMistakeBook": "打开错题本",
  "reviewConceptFallback": "复习薄弱概念",
  "conceptFallbackDesc": "根据错题和概念记录自动挑选。",
  "learning": "学习情况",
  "randomExercise": "随机抽一道题",
  "randomExerciseDesc": "从需复习、练习中和新题里优先抽取。",
  "highlightTitle": "查看或后台生成重点",
  "highlightDesc": "不用一直等在弹窗里，可以启动后台任务。",
  "summaryError": "学习摘要暂时不可用，快捷项会退回本地数据。",
  "directTitle": "基于记录继续",
  "reviewPlan": "生成今日复习清单",
  "reviewPlanDesc": "整理到期错题、薄弱概念和可执行顺序。",
  "practiceMemory": "按薄弱点抽一道题",
  "practiceMemoryDesc": "先匹配薄弱概念和错题，再从题库抽取。",
  "mistakeDigest": "总结最近错因",
  "mistakeDigestDesc": "按错因、标签和概念整理复盘建议。",
  "daily": "日报",
  "quickMistake": "错题速录",
  "reviewConceptPrefix": "复习概念：",
  "reviewPrefix": "复习"
} as const;
function firstLine(value = '') {
  const line = value.replace(/\s+/g, ' ').trim();
  return line.length > 42 ? `${line.slice(0, 42)}...` : line;
}

function greeting() {
  const hour = new Date().getHours();
  if (hour < 11) return labels.morning;
  if (hour < 18) return labels.afternoon;
  return labels.evening;
}

export default function ChatHomePanel({
  bookName,
  subject,
  books,
  isLoading,
  onReviewMistake,
  onReviewConcept,
  onShowReviewPlan,
  onPracticeFromMemory,
  onSummarizeMistakes,
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
  const scopeLabel = `${subject || labels.noSubject} · ${bookName || labels.genericQa}`;
  const hasBooks = books.length > 0;

  return (
    <div className="mx-auto flex min-h-[55vh] w-full max-w-5xl flex-col justify-center py-8">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--surface-black)]">
            <Sparkles className="h-5 w-5 text-white" />
          </div>
          <div className="type-hero min-w-0 text-text-primary">{greeting()}</div>
        </div>
        <div className="type-caption max-w-full truncate rounded-full border border-border bg-bg-card px-3 py-1.5 text-text-secondary">{scopeLabel}</div>
      </div>

      <div className="grid gap-3 lg:grid-cols-[minmax(0,1.25fr)_minmax(280px,0.75fr)]">
        <section className="rounded-[18px] border border-border bg-bg-card p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <div className="type-section-title text-text-primary">{labels.continueTitle}</div>

            </div>
            {loading && <Loader2 className="h-4 w-4 animate-spin text-accent" />}
          </div>

          <div className="grid gap-2 md:grid-cols-2">
            <ActionCard
              icon={<BookOpenCheck className="h-4 w-4" />}
              title={dueMistakes.length ? `${labels.reviewPrefix} ${dueMistakes.length} ${labels.dueMistakeSuffix}` : labels.reviewMistakes}
              description={firstMistake ? firstLine(firstMistake.question_text) : labels.mistakeFallback}
              disabled={!dueMistakes.length || isLoading}
              onClick={() => firstMistake && onReviewMistake(firstMistake)}
              secondary={firstMistake ? <Link to={`/mistakes?mistake_id=${encodeURIComponent(firstMistake.id)}`} className="type-caption text-accent hover:underline">{labels.openMistakeBook}</Link> : undefined}
            />
            <ActionCard
              icon={<BrainCircuit className="h-4 w-4" />}
              title={firstConcept ? `${labels.reviewConceptPrefix}${firstConcept.name}` : labels.reviewConceptFallback}
              description={firstConcept?.reasons?.[0] || labels.conceptFallbackDesc}
              disabled={!firstConcept || isLoading}
              onClick={() => firstConcept && onReviewConcept(firstConcept, summary)}
              secondary={<Link to="/learning" className="type-caption text-accent hover:underline">{labels.learning}</Link>}
            />
            <ActionCard
              icon={<Shuffle className="h-4 w-4" />}
              title={labels.randomExercise}
              description={labels.randomExerciseDesc}
              disabled={isLoading}
              onClick={onPickRandomExercise}
            />
            <ActionCard
              icon={<BookMarked className="h-4 w-4" />}
              title={labels.highlightTitle}
              description={labels.highlightDesc}
              disabled={!hasBooks || isLoading}
              onClick={onOpenHighlightDialog}
            />
          </div>
          {failed && <div className="mt-3 rounded-lg border border-border bg-bg-primary px-3 py-2 text-xs text-text-secondary">{labels.summaryError}</div>}
        </section>

        <section className="rounded-[18px] border border-border bg-bg-card p-4">
          <div className="type-section-title text-text-primary">{labels.directTitle}</div>
          <div className="mt-3 space-y-2">
            <QuickAction icon={<ListChecks className="h-3.5 w-3.5" />} title={labels.reviewPlan} description={labels.reviewPlanDesc} disabled={isLoading} onClick={() => onShowReviewPlan(summary)} />
            <QuickAction icon={<MessageSquareText className="h-3.5 w-3.5" />} title={labels.practiceMemory} description={labels.practiceMemoryDesc} disabled={isLoading} onClick={() => onPracticeFromMemory(summary)} />
            <QuickAction icon={<ClipboardList className="h-3.5 w-3.5" />} title={labels.mistakeDigest} description={labels.mistakeDigestDesc} disabled={isLoading} onClick={() => onSummarizeMistakes(summary)} />
          </div>
          <div className="mt-3 grid grid-cols-2 gap-2">
            <button type="button" onClick={() => onShowReport('daily')} disabled={isLoading} className="type-control inline-flex items-center justify-center gap-1.5 rounded-lg border border-border bg-bg-primary px-3 py-2 text-text-secondary hover:border-accent/45 hover:text-text-primary disabled:opacity-55"><CalendarDays className="h-3.5 w-3.5" />{labels.daily}</button>
            <button type="button" onClick={onOpenMistakeQuickCapture} disabled={isLoading} className="type-control inline-flex items-center justify-center gap-1.5 rounded-lg border border-border bg-bg-primary px-3 py-2 text-text-secondary hover:border-accent/45 hover:text-text-primary disabled:opacity-55"><ClipboardList className="h-3.5 w-3.5" />{labels.quickMistake}</button>
          </div>
        </section>
      </div>
    </div>
  );
}

function QuickAction({ icon, title, description, disabled, onClick }: { icon: React.ReactNode; title: string; description: string; disabled?: boolean; onClick: () => void }) {
  return (
    <button type="button" onClick={onClick} disabled={disabled} className="type-body flex w-full items-start gap-2 rounded-lg border border-border bg-bg-card px-3 py-2 text-left text-text-secondary transition-colors hover:border-accent/45 hover:text-text-primary disabled:cursor-not-allowed disabled:opacity-55">
      <span className="mt-0.5 flex-shrink-0 text-accent">{icon}</span>
      <span className="min-w-0">
        <span className="type-control block text-text-primary">{title}</span>
        <span className="mt-0.5 block">{description}</span>
      </span>
    </button>
  );
}

function ActionCard({ icon, title, description, disabled, onClick, secondary }: { icon: React.ReactNode; title: string; description: string; disabled?: boolean; onClick: () => void; secondary?: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-border bg-[var(--surface-subtle)] p-3">
      <button type="button" onClick={onClick} disabled={disabled} className="flex w-full items-start gap-3 text-left disabled:cursor-not-allowed disabled:opacity-45">
        <span className="mt-0.5 flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border border-accent/20 bg-[var(--accent-softer)] text-accent">{icon}</span>
        <span className="min-w-0 flex-1">
          <span className="type-section-title block text-text-primary">{title}</span>
          <span className="type-body mt-1 block text-text-secondary">{description}</span>
        </span>
      </button>
      {secondary && <div className="mt-2 pl-11">{secondary}</div>}
    </div>
  );
}
