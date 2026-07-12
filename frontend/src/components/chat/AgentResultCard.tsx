import { useMemo, useState } from 'react';
import { Bot, CheckCircle2, ChevronDown, ChevronRight, Database, FileText, ShieldCheck } from 'lucide-react';
import type { ChatAgentCard } from '../../types';
import { MarkdownMessage } from './MarkdownMessage';

const toolLabels: Record<string, string> = {
  search_textbook: '教材',
  search_concepts: '概念',
  link_concepts: '关联',
  get_due_mistakes: '到期错题',
  get_mistake_stats: '错题统计',
  build_review_plan: '复习计划',
  propose_add_mistake: '待确认错题',
  propose_concept_review: '待确认复习',
};

function compactData(value: unknown) {
  if (!value || typeof value !== 'object') return '';
  const data = value as Record<string, unknown>;
  if (Array.isArray(data.snippets)) return `${data.snippets.length} 条片段`;
  if (Array.isArray(data.concepts)) return `${data.concepts.length} 个概念`;
  if (Array.isArray(data.mistakes)) return `${data.mistakes.length} 道错题`;
  if (Array.isArray(data.plan)) return `${data.plan.length} 项`;
  if (data.stats && typeof data.stats === 'object') return '统计已读取';
  if (data.preview) return '等待确认';
  return '';
}

export default function AgentResultCard({ card }: { card: ChatAgentCard }) {
  const [open, setOpen] = useState(false);
  const { response } = card;
  const successfulTools = response.tool_outputs.filter((item) => item.result.success);
  const pendingActions = response.summary.pending_actions || [];
  const chips = useMemo(() => (
    successfulTools.map((item) => ({
      name: item.tool,
      label: toolLabels[item.tool] || item.tool,
      detail: compactData(item.result.data),
    }))
  ), [successfulTools]);

  return (
    <article className="agent-result-card overflow-hidden rounded-xl border border-border bg-bg-card">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-border px-3 py-2.5">
        <div className="flex min-w-0 items-center gap-2">
          <span className="flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-[var(--surface-black)] text-white">
            <Bot className="h-3.5 w-3.5" />
          </span>
          <span className="truncate text-sm font-semibold text-text-primary">工具编排</span>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="status-success inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs">
            <ShieldCheck className="h-3 w-3" />
            只读
          </span>
          {pendingActions.length > 0 && (
            <span className="inline-flex items-center gap-1 rounded-full border border-accent/25 bg-[var(--accent-softer)] px-2 py-0.5 text-xs text-accent-hover">
              <CheckCircle2 className="h-3 w-3" />
              {pendingActions.length} 项待确认
            </span>
          )}
        </div>
      </div>

      <div className="px-3 py-3">
        {response.answer ? (
          <MarkdownMessage content={response.answer} />
        ) : (
          <div className="text-sm text-text-secondary">工具已执行，暂无生成总结。</div>
        )}
      </div>

      {chips.length > 0 && (
        <div className="border-t border-border px-3 py-2">
          <button
            type="button"
            onClick={() => setOpen(!open)}
            className="flex w-full items-center justify-between gap-3 text-left text-xs text-text-secondary transition-colors hover:text-text-primary"
          >
            <span className="inline-flex items-center gap-1.5">
              {open ? <ChevronDown className="h-3.5 w-3.5 text-accent" /> : <ChevronRight className="h-3.5 w-3.5" />}
              证据
            </span>
            <span>{chips.length}</span>
          </button>

          {open && (
            <div className="mt-2 grid gap-2 sm:grid-cols-2">
              {chips.map((chip) => (
                <div key={`${chip.name}-${chip.detail}`} className="flex items-center gap-2 rounded-lg border border-border bg-bg-primary px-2.5 py-2 text-xs">
                  {chip.name === 'search_textbook' ? <FileText className="h-3.5 w-3.5 text-accent" /> : <Database className="h-3.5 w-3.5 text-accent" />}
                  <span className="font-medium text-text-primary">{chip.label}</span>
                  {chip.detail && <span className="min-w-0 truncate text-text-secondary">{chip.detail}</span>}
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </article>
  );
}
