import React, { useState } from 'react';
import { Loader2, Shuffle } from 'lucide-react';
import type { ChatExerciseCard } from '../../types';
import { post } from '../../api/client';
import { SimpleMarkdown } from './MarkdownMessage';

const ExerciseCard: React.FC<{ card: ChatExerciseCard; bookName: string }> = ({ card, bookName }) => {
  const [answerOpen, setAnswerOpen] = useState(false);
  const [practiceLoading, setPracticeLoading] = useState(false);
  const [message, setMessage] = useState('');
  const record = card.record;
  const bookQuery = bookName ? `?book_name=${encodeURIComponent(bookName)}` : '';

  const submitPractice = async (quality: number, addToMistake = false) => {
    setPracticeLoading(true);
    setMessage('');
    try {
      const res = await post(`/exercises/practice${bookQuery}`, {
        id: record.id,
        user_answer: '',
        quality,
        add_to_mistake: addToMistake,
      });
      if (!res?.success) {
        setMessage(res?.message || '练习记录失败');
        return;
      }
      setMessage(addToMistake && res.mistake_id ? '已记录为做错，并转入错题本。' : '已记录本次练习结果。');
      window.dispatchEvent(new Event('exercises:changed'));
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setPracticeLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-border bg-[var(--surface-subtle)] p-4">
        <div className="mb-3 flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-base font-semibold text-text-primary"><Shuffle className="h-4 w-4 text-accent" />随机抽题</div>
            <div className="mt-1 flex flex-wrap gap-2 text-xs text-text-secondary">
              <span>{record.subject || bookName || '未分类'}</span>
              {record.chapter && <span>{record.chapter}</span>}
              <span>难度 {record.difficulty || 3}</span>
              <span>练习 {record.practice_count || 0} 次</span>
            </div>
          </div>
          <span className="rounded-lg border border-accent/25 bg-[var(--accent-softer)] px-2.5 py-1 text-xs text-accent">{record.status || 'new'}</span>
        </div>
        <div className="rounded-xl border border-border bg-bg-card p-3">
          <SimpleMarkdown content={record.question_text} />
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          <button type="button" onClick={() => setAnswerOpen((open) => !open)} className="rounded-lg border border-border bg-bg-card px-3 py-1.5 text-xs text-text-primary hover:border-accent/50 hover:text-accent">
            {answerOpen ? '收起答案解析' : '查看答案解析'}
          </button>
          <button type="button" disabled={practiceLoading} onClick={() => submitPractice(1, true)} className="rounded-lg border border-red-200 bg-red-50 px-3 py-1.5 text-xs text-[var(--danger)] disabled:opacity-50">做错入错题</button>
          <button type="button" disabled={practiceLoading} onClick={() => submitPractice(3)} className="rounded-lg border border-[#dec98b] bg-[#fff7de] px-3 py-1.5 text-xs text-[var(--warning)] disabled:opacity-50">勉强会</button>
          <button type="button" disabled={practiceLoading} onClick={() => submitPractice(5)} className="rounded-lg border border-[#bfd4c6] bg-[#edf6f0] px-3 py-1.5 text-xs text-[var(--success)] disabled:opacity-50">掌握</button>
        </div>
        {practiceLoading && <div className="mt-3 flex items-center gap-2 text-xs text-text-secondary"><Loader2 className="h-3.5 w-3.5 animate-spin" />正在记录...</div>}
        {message && <div className="mt-3 rounded-lg border border-border bg-bg-card px-3 py-2 text-xs text-text-secondary">{message}</div>}
      </div>
      {answerOpen && (
        <div className="space-y-3 rounded-xl border border-border bg-bg-card p-4">
          <section>
            <div className="mb-2 text-xs font-medium text-text-secondary">答案</div>
            {record.answer ? <SimpleMarkdown content={record.answer} /> : <div className="text-sm text-text-secondary">暂无答案</div>}
          </section>
          <section>
            <div className="mb-2 text-xs font-medium text-text-secondary">解析</div>
            {record.explanation ? <SimpleMarkdown content={record.explanation} /> : <div className="text-sm text-text-secondary">暂无解析</div>}
          </section>
        </div>
      )}
    </div>
  );
};

export default ExerciseCard;