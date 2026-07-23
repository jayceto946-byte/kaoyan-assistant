import type { ReactNode } from 'react';
import { Trash2 } from 'lucide-react';

import ChatMessage from '../../../components/ChatMessage';
import type { ExerciseRecord } from '../../../types';

export const exerciseStatusText: Record<string, string> = {
  new: '新题',
  practicing: '练习中',
  mastered: '已掌握',
  needs_review: '需复习',
};

export const ExerciseBlock = ({ title, children }: { title: string; children: ReactNode }) => (
  <section className="space-y-2">
    <div className="text-xs font-medium text-text-secondary">{title}</div>
    <div className="rounded-xl border border-border bg-bg-secondary p-3">{children}</div>
  </section>
);

export const ExerciseMetric = ({ label, value }: { label: string; value: number }) => (
  <div className="rounded-xl border border-border bg-bg-card p-4 text-center">
    <div className="text-2xl font-semibold text-text-primary">{value}</div>
    <div className="mt-1 text-xs text-text-secondary">{label}</div>
  </div>
);

export const ExerciseDetail = ({
  record,
  onStatus,
  onPractice,
  onDelete,
}: {
  record: ExerciseRecord;
  onStatus: (status: string) => void;
  onPractice: () => void;
  onDelete: () => void;
}) => (
  <div className="mt-4 space-y-4 border-t border-border pt-4">
    <ExerciseBlock title="题干">
      <ChatMessage
        role="assistant"
        content={record.question_text}
        linkedConcepts={record.linked_concepts || []}
      />
    </ExerciseBlock>
    <ExerciseBlock title="答案">
      {record.answer
        ? <ChatMessage role="assistant" content={record.answer} />
        : <span className="text-sm text-text-secondary">暂无答案</span>}
    </ExerciseBlock>
    <ExerciseBlock title="解析">
      {record.explanation
        ? (
          <ChatMessage
            role="assistant"
            content={record.explanation}
            linkedConcepts={record.linked_concepts || []}
          />
        )
        : <span className="text-sm text-text-secondary">暂无解析</span>}
    </ExerciseBlock>
    <div className="flex flex-wrap gap-2">
      <button
        onClick={onPractice}
        className="rounded border border-border bg-bg-primary px-3 py-1 text-xs hover:border-accent hover:text-accent"
      >
        设为当前练习
      </button>
      {Object.entries(exerciseStatusText).map(([status, label]) => (
        <button
          key={status}
          onClick={() => onStatus(status)}
          className="rounded border border-border bg-bg-primary px-3 py-1 text-xs hover:border-accent hover:text-accent"
        >
          {label}
        </button>
      ))}
      <button
        onClick={onDelete}
        className="flex items-center gap-1 rounded border border-[#e6b2a9] bg-[#fff1ed] px-3 py-1 text-xs text-[var(--danger)] hover:border-[var(--danger)]"
      >
        <Trash2 className="h-3.5 w-3.5" /> 删除
      </button>
    </div>
    {record.origin_type !== 'manual' && (
      <div className="text-xs text-text-secondary">
        来源对象：{record.origin_type} / {record.origin_id}
      </div>
    )}
  </div>
);
