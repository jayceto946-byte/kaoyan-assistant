import React, { useEffect, useMemo, useRef, useState } from 'react';
import { CheckCircle2, ChevronDown, ChevronRight, ClipboardList, Loader2, Search, Sparkles, Upload } from 'lucide-react';
import { get, post } from '../api/client';
import ChatMessage from '../components/ChatMessage';
import SubjectInput from '../components/SubjectInput';
import { useChatContext } from '../contexts/ChatContext';
import type { BookInfo, ExerciseCandidate, ExerciseRecord, ExerciseStats } from '../types';

const statusText: Record<string, string> = {
  new: '新题',
  practicing: '练习中',
  mastered: '已掌握',
  needs_review: '需复习',
};

function titleOf(record: ExerciseRecord) {
  const raw = record.question_text || record.source || '未命名习题';
  const line = raw.replace(/\$\$[\s\S]*?\$\$/g, ' ').replace(/\$(?:\\.|[^$\\])*?\$/g, ' ').split('\n').map((item) => item.trim()).find(Boolean) || raw;
  return line.length > 56 ? `${line.slice(0, 56)}...` : line;
}

function candidateToExercise(candidate: ExerciseCandidate) {
  return {
    question_text: candidate.question_text,
    answer: candidate.answer || '',
    explanation: candidate.explanation || '',
    source: candidate.source || '',
    subject: candidate.subject || '',
    chapter: candidate.chapter || '',
    tags: candidate.tags.join(', '),
    question_type: candidate.suggested_type || '',
    difficulty: candidate.difficulty || 3,
    linked_concepts: candidate.linked_concepts || [],
    origin_type: 'import_candidate',
    origin_id: candidate.id,
    status: 'needs_review',
    notes: candidate.reasons.join('; '),
  };
}

const ExercisesPage: React.FC = () => {
  const { bookName, setBookName } = useChatContext();
  const [books, setBooks] = useState<BookInfo[]>([]);
  const [targetName, setTargetName] = useState(bookName || '数学');
  const activeName = targetName.trim() || bookName || 'default';
  const bookQuery = activeName && activeName !== 'default' ? `?book_name=${encodeURIComponent(activeName)}` : '';

  const [records, setRecords] = useState<ExerciseRecord[]>([]);
  const [stats, setStats] = useState<ExerciseStats | null>(null);
  const [searchKw, setSearchKw] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [expandedId, setExpandedId] = useState('');
  const [practiceId, setPracticeId] = useState('');
  const [practiceAnswer, setPracticeAnswer] = useState('');
  const [practiceSolutionOpen, setPracticeSolutionOpen] = useState(false);
  const [practiceMessage, setPracticeMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [importing, setImporting] = useState(false);
  const [message, setMessage] = useState('');
  const [importFile, setImportFile] = useState<File | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [importSource, setImportSource] = useState('');
  const [importChapter, setImportChapter] = useState('');
  const [extractedPreview, setExtractedPreview] = useState('');
  const [candidates, setCandidates] = useState<ExerciseCandidate[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());

  const importSummary = useMemo(() => {
    const needsLlm = candidates.filter((item) => item.needs_llm).length;
    return { total: candidates.length, needsLlm, confident: candidates.length - needsLlm };
  }, [candidates]);

  const practicePool = useMemo(() => {
    const rank: Record<string, number> = { needs_review: 0, practicing: 1, new: 2, mastered: 3 };
    return [...records].sort((a, b) => (rank[a.status] ?? 2) - (rank[b.status] ?? 2) || (a.practice_count || 0) - (b.practice_count || 0));
  }, [records]);

  const currentPractice = useMemo(() => {
    if (practiceId) return records.find((item) => item.id === practiceId) || null;
    return practicePool.find((item) => item.status !== 'mastered') || practicePool[0] || null;
  }, [practiceId, practicePool, records]);

  const loadBooks = async () => {
    try {
      const res = await get('/books/list');
      if (res?.success) setBooks(res.data || []);
    } catch {
      setBooks([]);
    }
  };

  const load = async () => {
    setLoading(true);
    setMessage('');
    try {
      const listRes = await post(`/exercises/list${bookQuery}`, { search_kw: searchKw, status: statusFilter, limit: 100 });
      if (listRes?.success) setRecords(listRes.data || []);
      const statsRes = await get(`/exercises/stats${bookQuery}`);
      if (statsRes?.success) setStats(statsRes.data);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadBooks();
  }, []);

  useEffect(() => {
    if (bookName) setTargetName(bookName);
  }, [bookName]);

  useEffect(() => {
    load();
  }, [bookQuery, statusFilter]);

  const updateTargetName = (value: string) => {
    setTargetName(value);
    if (value && books.some((book) => book.name === value)) setBookName(value);
    setCandidates([]);
    setSelectedIds(new Set());
    setExtractedPreview('');
  };

  const analyzeImportFile = async () => {
    if (!importFile) {
      setMessage('请选择 Word 或 PDF 文件');
      return;
    }
    setImporting(true);
    setMessage('');
    try {
      const fd = new FormData();
      fd.append('file', importFile);
      fd.append('source', importSource || importFile.name);
      fd.append('subject', activeName);
      fd.append('chapter', importChapter);
      fd.append('limit', '200');
      const res = await fetch(`/api/exercises/upload-analyze${bookQuery}`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!res.ok || !data?.success) {
        setMessage(data?.message || `文件导入失败：${res.status}`);
        return;
      }
      const next = data.data || [];
      setCandidates(next);
      setSelectedIds(new Set(next.map((item: ExerciseCandidate) => item.id)));
      setExtractedPreview(data.extract?.text ? data.extract.text.slice(0, 1200) : '');
      const warnings = data.extract?.warnings?.length ? `；${data.extract.warnings.join('；')}` : '';
      setMessage(`${data.message || `已分析 ${next.length} 道候选题`}${warnings}`);
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setImporting(false);
    }
  };

  const importSelected = async () => {
    const selected = candidates.filter((item) => selectedIds.has(item.id));
    if (selected.length === 0) {
      setMessage('请至少选择一道候选题');
      return;
    }
    setImporting(true);
    try {
      const res = await post(`/exercises/batch-add${bookQuery}`, { exercises: selected.map(candidateToExercise) });
      if (!res?.success) {
        setMessage(res?.message || '批量导入失败');
        return;
      }
      setMessage(res.message || `已导入 ${selected.length} 道候选题`);
      setCandidates((prev) => prev.filter((item) => !selectedIds.has(item.id)));
      setSelectedIds(new Set());
      await load();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : String(e));
    } finally {
      setImporting(false);
    }
  };

  const updateStatus = async (id: string, status: string) => {
    const res = await post(`/exercises/status${bookQuery}`, { id, status });
    if (!res?.success) {
      setMessage(res?.message || '状态更新失败');
      return;
    }
    setRecords((prev) => prev.map((item) => (item.id === id ? res.data : item)));
    await load();
  };

  const selectPractice = (record?: ExerciseRecord | null) => {
    const next = record || practicePool.find((item) => item.id !== currentPractice?.id && item.status !== 'mastered') || practicePool.find((item) => item.id !== currentPractice?.id) || practicePool[0] || null;
    setPracticeId(next?.id || '');
    setPracticeAnswer('');
    setPracticeSolutionOpen(false);
    setPracticeMessage('');
  };

  const submitPractice = async (quality: number, addToMistake = false) => {
    if (!currentPractice) return;
    try {
      const res = await post(`/exercises/practice${bookQuery}`, {
        id: currentPractice.id,
        user_answer: practiceAnswer,
        quality,
        add_to_mistake: addToMistake,
      });
      if (!res?.success) {
        setPracticeMessage(res?.message || '练习记录失败');
        return;
      }
      setPracticeMessage(addToMistake && res.mistake_id ? '已记录练习，并转入错题本' : '已记录练习结果');
      setRecords((prev) => prev.map((item) => (item.id === currentPractice.id ? res.data : item)));
      await load();
    } catch (e) {
      setPracticeMessage(e instanceof Error ? e.message : String(e));
    }
  };

  const sendPracticeToMistake = async () => {
    if (!currentPractice) return;
    try {
      const res = await post(`/exercises/to-mistake${bookQuery}`, {
        id: currentPractice.id,
        user_answer: practiceAnswer,
        mistake_type: ['思路卡住'],
      });
      if (!res?.success) {
        setPracticeMessage(res?.message || '转入错题本失败');
        return;
      }
      setPracticeMessage('已转入错题本');
      setRecords((prev) => prev.map((item) => (item.id === currentPractice.id ? res.data : item)));
      await load();
    } catch (e) {
      setPracticeMessage(e instanceof Error ? e.message : String(e));
    }
  };

  const toggleCandidate = (id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-border bg-bg-primary px-5 py-4">
        <div>
          <h2 className="text-sm font-semibold text-text-primary">习题库</h2>
        </div>
        <button onClick={load} disabled={loading} className="flex items-center gap-1.5 rounded-xl border border-border bg-bg-primary px-3 py-1.5 text-sm text-text-primary hover:border-accent disabled:opacity-50">
          {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />} 刷新
        </button>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-[360px_minmax(0,1fr)] overflow-hidden">
        <aside className="overflow-y-auto border-r border-border bg-bg-secondary/95 p-4">
          <div className="space-y-4">
            <section className="space-y-3 rounded-xl border border-border bg-bg-card shadow-sm p-4">
              <div>
                <div className="text-sm font-medium text-text-primary">教材 / 学科</div>
                <p className="mt-1 text-xs text-text-secondary">有教材时优先选择教材；没有教材时可输入自定义学科。</p>
              </div>
              <select value={books.some((book) => book.name === targetName) ? targetName : ''} onChange={(e) => updateTargetName(e.target.value)} className="w-full rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm outline-none focus:border-accent">
                <option value="">不限定教材，使用下方学科</option>
                {books.map((book) => <option key={book.name} value={book.name}>{book.name}</option>)}
              </select>
              <SubjectInput value={targetName} onChange={updateTargetName} suggestions={books.map((book) => book.name)} placeholder="如 线代 / 微积分 / 优化设计" className="w-full rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm outline-none focus:border-accent" />
            </section>

            <section className="space-y-3 rounded-xl border border-border bg-bg-card shadow-sm p-4">
              <div className="flex items-center gap-2 text-sm font-medium text-text-primary"><Sparkles className="h-4 w-4 text-accent" /> Word/PDF 导入</div>
              <div className="grid grid-cols-2 gap-2">
                <input placeholder="来源，如 2025 模拟卷" value={importSource} onChange={(e) => setImportSource(e.target.value)} className="rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm outline-none focus:border-accent" />
                <input placeholder="章节，可留空" value={importChapter} onChange={(e) => setImportChapter(e.target.value)} className="rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm outline-none focus:border-accent" />
              </div>
              <button onClick={() => fileInputRef.current?.click()} className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-bg-primary px-3 py-4 text-sm text-text-primary hover:border-accent">
                <Upload className="h-4 w-4" /> {importFile ? importFile.name : '选择 Word/PDF 文件'}
              </button>
              <input ref={fileInputRef} type="file" accept=".docx,.pdf,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document" onChange={(e) => setImportFile(e.target.files?.[0] || null)} className="hidden" />
              <button onClick={analyzeImportFile} disabled={importing || !importFile} className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">
                {importing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} 分析文件
              </button>
              {extractedPreview && <div className="max-h-32 overflow-y-auto rounded border border-border bg-bg-secondary p-3 text-xs leading-5 text-text-secondary">{extractedPreview}</div>}
              {message && <div className="rounded border border-border bg-bg-primary px-3 py-2 text-xs text-text-secondary">{message}</div>}
            </section>

            {candidates.length > 0 && (
              <section className="space-y-3 rounded-xl border border-border bg-bg-card shadow-sm p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-medium text-text-primary">候选题确认</div>
                    <div className="mt-1 text-xs text-text-secondary">{importSummary.total} 道 · {importSummary.needsLlm} 道建议精标</div>
                  </div>
                  <button onClick={() => setSelectedIds(new Set(candidates.map((item) => item.id)))} className="rounded border border-border px-2.5 py-1 text-xs hover:border-accent">全选</button>
                </div>
                <button onClick={importSelected} disabled={importing || selectedIds.size === 0} className="flex w-full items-center justify-center gap-2 rounded-xl bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50"><CheckCircle2 className="h-4 w-4" /> 导入选中 {selectedIds.size}</button>
              </section>
            )}
          </div>
        </aside>

        <main className="overflow-y-auto p-6">
          <div className="space-y-5">
            <div className="grid grid-cols-3 gap-4">
              <Metric label="总习题" value={stats?.total || 0} />
              <Metric label="需复习" value={stats?.by_status?.needs_review || 0} />
              <Metric label="已掌握" value={stats?.by_status?.mastered || 0} />
            </div>

            <section className="space-y-4 rounded-xl border border-border bg-bg-card shadow-sm p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <h3 className="text-sm font-semibold text-text-primary">练习</h3>
                  <p className="text-xs text-text-secondary">优先抽取需复习、练习中和新题</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button onClick={() => selectPractice()} disabled={practicePool.length === 0} className="rounded-xl border border-border bg-bg-primary px-3 py-1.5 text-xs hover:border-accent disabled:opacity-50">换一题</button>
                  {currentPractice && <button onClick={sendPracticeToMistake} className="rounded-xl border border-border bg-bg-primary px-3 py-1.5 text-xs hover:border-accent">转入错题本</button>}
                </div>
              </div>

              {currentPractice ? (
                <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_340px]">
                  <div className="space-y-3">
                    <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
                      <span className="rounded border border-border px-2 py-0.5">{statusText[currentPractice.status] || currentPractice.status}</span>
                      <span className="rounded border border-border px-2 py-0.5">练习 {currentPractice.practice_count || 0} 次</span>
                      {currentPractice.chapter && <span className="rounded border border-border px-2 py-0.5">{currentPractice.chapter}</span>}
                      {(currentPractice.tags || []).map((tag) => <span key={tag} className="rounded bg-bg-secondary px-2 py-0.5">{tag}</span>)}
                    </div>
                    <ChatMessage role="assistant" content={currentPractice.question_text} linkedConcepts={currentPractice.linked_concepts || []} />
                  </div>
                  <div className="space-y-3">
                    <textarea value={practiceAnswer} onChange={(e) => setPracticeAnswer(e.target.value)} placeholder="写下你的答案或思路" className="min-h-[132px] w-full rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none focus:border-accent" />
                    <button onClick={() => setPracticeSolutionOpen((open) => !open)} className="w-full rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm hover:border-accent">{practiceSolutionOpen ? '收起答案解析' : '查看答案解析'}</button>
                    {practiceSolutionOpen && (
                      <div className="space-y-3 rounded-xl border border-border bg-bg-secondary p-3">
                        <Block title="答案">{currentPractice.answer ? <ChatMessage role="assistant" content={currentPractice.answer} /> : <span className="text-sm text-text-secondary">暂无答案</span>}</Block>
                        <Block title="解析">{currentPractice.explanation ? <ChatMessage role="assistant" content={currentPractice.explanation} linkedConcepts={currentPractice.linked_concepts || []} /> : <span className="text-sm text-text-secondary">暂无解析</span>}</Block>
                      </div>
                    )}
                    <div className="grid grid-cols-3 gap-2">
                      <button onClick={() => submitPractice(1, true)} className="rounded-lg border border-[#e6b2a9] bg-[#fff1ed] px-3 py-2 text-xs text-[var(--danger)] hover:border-[var(--danger)]">做错</button>
                      <button onClick={() => submitPractice(3)} className="rounded-lg border border-[#e3c98f] bg-[#fff6df] px-3 py-2 text-xs text-[var(--warning)] hover:border-[var(--warning)]">勉强会</button>
                      <button onClick={() => submitPractice(5)} className="rounded-lg border border-[#c9d8bd] bg-[#eef5e8] px-3 py-2 text-xs text-[var(--success)] hover:border-[var(--success)]">掌握</button>
                    </div>
                    {practiceMessage && <div className="rounded border border-border bg-bg-primary px-3 py-2 text-xs text-text-secondary">{practiceMessage}</div>}
                  </div>
                </div>
              ) : (
                <div className="rounded-xl border border-dashed border-border bg-bg-secondary py-8 text-center text-sm text-text-secondary">暂无可练习习题，请先导入 Word/PDF 题目</div>
              )}
            </section>

            {candidates.length > 0 && (
              <section className="space-y-3 rounded-xl border border-border bg-bg-card shadow-sm p-4">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-text-primary">待确认候选题</h3>
                  <span className="text-xs text-text-secondary">{selectedIds.size} / {candidates.length} 已选</span>
                </div>
                <div className="space-y-2">
                  {candidates.map((candidate) => (
                    <article key={candidate.id} className="rounded-xl border border-border bg-bg-primary p-3">
                      <div className="flex items-start gap-3">
                        <input type="checkbox" checked={selectedIds.has(candidate.id)} onChange={() => toggleCandidate(candidate.id)} className="mt-1 h-4 w-4 accent-accent" />
                        <div className="min-w-0 flex-1 space-y-2">
                          <div className="flex flex-wrap items-center gap-2 text-xs">
                            <span className="rounded border border-border px-2 py-0.5 text-text-secondary">{candidate.suggested_type || '未定题型'}</span>
                            <span className="rounded border border-border px-2 py-0.5 text-text-secondary">难度 {candidate.difficulty}</span>
                            <span className={`rounded border px-2 py-0.5 ${candidate.needs_llm ? 'border-[#e3c98f] bg-[#fff6df] text-[var(--warning)]' : 'border-[#c9d8bd] bg-[#eef5e8] text-[var(--success)]'}`}>置信度 {Math.round(candidate.confidence * 100)}%</span>
                          </div>
                          <p className="line-clamp-3 whitespace-pre-wrap text-sm text-text-primary">{candidate.question_text}</p>
                          <div className="flex flex-wrap gap-2 text-xs text-text-secondary">
                            {(candidate.tags.length ? candidate.tags : ['未识别知识点']).map((tag) => <span key={tag} className="rounded bg-bg-secondary px-2 py-0.5">{tag}</span>)}
                          </div>
                        </div>
                      </div>
                    </article>
                  ))}
                </div>
              </section>
            )}

            <section className="rounded-xl border border-border bg-bg-card shadow-sm p-4">
              <div className="mb-4 flex flex-wrap items-center gap-3">
                <input value={searchKw} onChange={(e) => setSearchKw(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') load(); }} placeholder="搜索题干/答案/解析/标签" className="min-w-[260px] flex-1 rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm outline-none focus:border-accent" />
                <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm outline-none focus:border-accent">
                  <option value="">全部状态</option>
                  {Object.entries(statusText).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                </select>
                <button onClick={load} className="rounded-xl border border-border px-3 py-2 text-sm hover:border-accent">搜索</button>
              </div>

              <div className="space-y-3">
                {records.map((record) => {
                  const expanded = expandedId === record.id;
                  return (
                    <article key={record.id} className="rounded-xl border border-border bg-bg-primary p-4">
                      <button onClick={() => setExpandedId(expanded ? '' : record.id)} className="flex w-full items-start justify-between gap-3 text-left">
                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
                            {expanded ? <ChevronDown className="h-4 w-4 text-accent" /> : <ChevronRight className="h-4 w-4 text-text-secondary" />}
                            <span className="truncate">{titleOf(record)}</span>
                          </div>
                          <div className="mt-2 flex flex-wrap gap-3 text-xs text-text-secondary">
                            <span>{record.subject || activeName}</span>
                            {record.chapter && <span>{record.chapter}</span>}
                            <span>{record.tags.join(', ') || '无标签'}</span>
                            <span>{record.question_type || '未标题型'}</span>
                            <span>练习 {record.practice_count || 0} 次</span>
                          </div>
                        </div>
                        <span className="rounded border border-accent/30 bg-accent/10 px-2 py-0.5 text-xs font-medium text-accent-hover">{statusText[record.status] || record.status}</span>
                      </button>
                      {expanded && <ExerciseDetail record={record} onStatus={(status) => updateStatus(record.id, status)} onPractice={() => selectPractice(record)} />}
                    </article>
                  );
                })}
                {records.length === 0 && <div className="py-12 text-center text-sm text-text-secondary"><ClipboardList className="mx-auto mb-2 h-6 w-6" />暂无习题，请先导入 Word/PDF</div>}
              </div>
            </section>
          </div>
        </main>
      </div>
    </div>
  );
};

const ExerciseDetail = ({ record, onStatus, onPractice }: { record: ExerciseRecord; onStatus: (status: string) => void; onPractice: () => void }) => (
  <div className="mt-4 space-y-4 border-t border-border pt-4">
    <Block title="题干"><ChatMessage role="assistant" content={record.question_text} linkedConcepts={record.linked_concepts || []} /></Block>
    <Block title="答案">{record.answer ? <ChatMessage role="assistant" content={record.answer} /> : <span className="text-sm text-text-secondary">暂无答案</span>}</Block>
    <Block title="解析">{record.explanation ? <ChatMessage role="assistant" content={record.explanation} linkedConcepts={record.linked_concepts || []} /> : <span className="text-sm text-text-secondary">暂无解析</span>}</Block>
    <div className="flex flex-wrap gap-2">
      <button onClick={onPractice} className="rounded border border-border bg-bg-primary px-3 py-1 text-xs hover:border-accent hover:text-accent">设为当前练习</button>
      {Object.entries(statusText).map(([status, label]) => (
        <button key={status} onClick={() => onStatus(status)} className="rounded border border-border bg-bg-primary px-3 py-1 text-xs hover:border-accent hover:text-accent">{label}</button>
      ))}
    </div>
    {record.origin_type !== 'manual' && <div className="text-xs text-text-secondary">来源对象：{record.origin_type} / {record.origin_id}</div>}
  </div>
);

const Block = ({ title, children }: { title: string; children: React.ReactNode }) => (
  <section className="space-y-2">
    <div className="text-xs font-medium text-text-secondary">{title}</div>
    <div className="rounded-xl border border-border bg-bg-secondary p-3">{children}</div>
  </section>
);

const Metric = ({ label, value }: { label: string; value: number }) => (
  <div className="rounded-xl border border-border bg-bg-card shadow-sm p-4 text-center">
    <div className="text-2xl font-semibold text-text-primary">{value}</div>
    <div className="mt-1 text-xs text-text-secondary">{label}</div>
  </div>
);

export default ExercisesPage;
