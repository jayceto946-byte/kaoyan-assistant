import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import { User, Bot, BookOpen, CheckCircle2, ExternalLink, ImagePlus, Loader2, Save, Shuffle, Upload } from 'lucide-react';
import 'katex/dist/katex.min.css';
import type { ChatExerciseCard, ChatReportCard, ChatUtilityCard, ConceptCandidate, LearningReport } from '../types';
import { useChatContext } from '../contexts/ChatContext';
import ConceptPopover from './ConceptPopover';
import SubjectInput from './SubjectInput';
import { ErrorBoundary } from './ErrorBoundary';
import { prepareMathMarkdown } from '../utils/mathText';
import { post } from '../api/client';

interface ChatMessageProps {
  role: 'user' | 'assistant';
  content: string;
  stage?: string;
  linkedConcepts?: ConceptCandidate[];
  reportCard?: ChatReportCard;
  exerciseCard?: ChatExerciseCard;
  utilityCard?: ChatUtilityCard;
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

function protectSegments(text: string): { text: string; tokens: string[] } {
  const tokens: string[] = [];
  const protect = (match: string) => {
    const token = `@@PROTECTED_${tokens.length}@@`;
    tokens.push(match);
    return token;
  };
  return {
    text: text
      .replace(/```[\s\S]*?```/g, protect)
      .replace(/\$\$[\s\S]*?\$\$/g, protect)
      .replace(/`[^`]*`/g, protect)
      .replace(/\$(?!\$)(?:\\.|[^$\\])*?\$/g, protect)
      .replace(/\[[^\]\n]{1,240}\]\([^)]+?\)/g, protect),
    tokens,
  };
}

function restoreSegments(text: string, tokens: string[]): string {
  return tokens.reduce((acc, token, index) => acc.replace(`@@PROTECTED_${index}@@`, token), text);
}

function linkConcepts(markdown: string, concepts: ConceptCandidate[]): string {
  if (!concepts.length) return markdown;
  const { text, tokens } = protectSegments(markdown);
  let linked = text;
  const usedConcepts = new Set<string>();
  const usedTerms = new Set<string>();

  const terms = concepts
    .flatMap((concept) => [concept.name, ...(concept.aliases || [])].map((term) => ({ term, concept })))
    .filter(({ term }) => term && term.length >= 2)
    .sort((a, b) => b.term.length - a.term.length);

  for (const { term, concept } of terms) {
    if (usedConcepts.has(concept.name) || usedTerms.has(term)) continue;
    const pattern = new RegExp(`(?<![\\]\\[])${escapeRegExp(term)}(?!\\]\\()`, 'u');
    if (!pattern.test(linked)) continue;
    const href = `#concept-${encodeURIComponent(concept.name)}`;
    const token = `@@PROTECTED_${tokens.length}@@`;
    tokens.push(`[${term}](${href})`);
    linked = linked.replace(pattern, token);
    usedConcepts.add(concept.name);
    usedTerms.add(term);
  }

  return restoreSegments(linked, tokens);
}

function countUnescapedDoubleDollars(line: string): number {
  let count = 0;
  for (let i = 0; i < line.length - 1; i += 1) {
    if (line[i] !== '$' || line[i + 1] !== '$') continue;
    let slashCount = 0;
    for (let j = i - 1; j >= 0 && line[j] === '\\'; j -= 1) slashCount += 1;
    if (slashCount % 2 === 0) count += 1;
    i += 1;
  }
  return count;
}

function countUnescapedInlineDollars(line: string): number {
  let count = 0;
  for (let i = 0; i < line.length; i += 1) {
    if (line[i] !== '$') continue;
    if (line[i - 1] === '$' || line[i + 1] === '$') continue;
    let slashCount = 0;
    for (let j = i - 1; j >= 0 && line[j] === '\\'; j -= 1) slashCount += 1;
    if (slashCount % 2 === 0) count += 1;
  }
  return count;
}

function splitMarkdownForRender(markdown: string, maxChars = 10000): string[] {
  if (markdown.length <= maxChars) return [markdown];

  const blocks: string[] = [];
  const current: string[] = [];
  let currentLength = 0;
  let inFence = false;
  let inBlockMath = false;
  let inInlineMath = false;

  const flush = () => {
    const block = current.join('\n').trimEnd();
    if (block) blocks.push(block);
    current.length = 0;
    currentLength = 0;
  };

  for (const line of markdown.split('\n')) {
    const trimmed = line.trim();
    const fenceLine = /^```/.test(trimmed);
    if (fenceLine) inFence = !inFence;

    if (!inFence) {
      const blockMathToggles = countUnescapedDoubleDollars(line);
      if (blockMathToggles % 2 === 1) inBlockMath = !inBlockMath;
      if (!inBlockMath) {
        const inlineMathToggles = countUnescapedInlineDollars(line);
        if (inlineMathToggles % 2 === 1) inInlineMath = !inInlineMath;
      }
    }

    current.push(line);
    currentLength += line.length + 1;

    const canSplit = !inFence && !inBlockMath && !inInlineMath;
    if (canSplit && currentLength >= maxChars && trimmed === '') {
      flush();
    }
  }

  flush();
  return blocks.length ? blocks : [markdown];
}

function blockKey(block: string, index: number): string {
  let hash = 0;
  for (let i = 0; i < block.length; i += 1) {
    hash = (hash * 31 + block.charCodeAt(i)) | 0;
  }
  return `${index}:${block.length}:${hash}`;
}

const PlainMarkdownFallback: React.FC<{ content: string }> = ({ content }) => (
  <div className="whitespace-pre-wrap break-words text-sm leading-relaxed text-text-primary">{content}</div>
);


const reportMetrics = [
  ['问答', 'qa_count'],
  ['新错题', 'new_mistakes'],
  ['复习错题', 'reviewed_mistakes'],
  ['新习题', 'new_exercises'],
  ['练习', 'practiced_exercises'],
  ['概念接触', 'concept_exposures'],
] as const;

const ReportList = ({ title, items, empty }: { title: string; items: string[]; empty: string }) => (
  <section>
    <div className="mb-2 text-xs font-medium text-text-secondary">{title}</div>
    <div className="space-y-2">
      {items.length ? items.map((item, index) => <div key={`${item}-${index}`} className="rounded-lg border border-border bg-[var(--surface-subtle)] px-3 py-2 text-sm text-text-primary">{item}</div>) : <div className="rounded-lg border border-dashed border-border px-3 py-4 text-center text-sm text-text-secondary">{empty}</div>}
    </div>
  </section>
);

const ReportCard: React.FC<{ card: ChatReportCard }> = ({ card }) => {
  const [open, setOpen] = useState(false);
  const report: LearningReport = card.report;
  const title = card.kind === 'daily' ? '学习日报' : '学习周报';
  const summary = report.summary || {};
  const topConceptText = report.top_concepts?.length ? report.top_concepts.slice(0, 3).map((item) => item.name).join('、') : '暂无概念记录';
  const weakText = report.weak_points?.length ? report.weak_points.slice(0, 3).map((item) => item.name).join('、') : '暂无新增薄弱点';

  return (
    <div className="space-y-3">
      <div className="rounded-xl border border-border bg-[var(--surface-subtle)] p-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <div className="text-base font-semibold text-text-primary">{title}</div>
            <div className="mt-1 text-xs text-text-secondary">{report.start_date} 至 {report.end_date} · {report.book_name}</div>
          </div>
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            className="rounded-lg border border-border bg-bg-card px-3 py-1.5 text-xs text-text-primary transition-colors hover:border-accent/50 hover:text-accent"
          >
            {open ? '收起完整情况' : '展开完整情况'}
          </button>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3">
          {reportMetrics.map(([label, key]) => (
            <div key={key} className="rounded-lg border border-border bg-bg-card px-3 py-2">
              <div className="text-lg font-semibold text-text-primary">{summary[key] || 0}</div>
              <div className="text-[11px] text-text-secondary">{label}</div>
            </div>
          ))}
        </div>

        <div className="mt-4 grid gap-2 text-sm md:grid-cols-2">
          <div className="rounded-lg border border-border bg-bg-card px-3 py-2">
            <div className="mb-1 text-xs font-medium text-text-secondary">高频概念</div>
            <div className="text-text-primary">{topConceptText}</div>
          </div>
          <div className="rounded-lg border border-border bg-bg-card px-3 py-2">
            <div className="mb-1 text-xs font-medium text-text-secondary">薄弱点</div>
            <div className="text-text-primary">{weakText}</div>
          </div>
        </div>

        {report.suggestions?.length > 0 && (
          <div className="mt-3 rounded-lg border border-accent/20 bg-[var(--accent-softer)] px-3 py-2 text-sm text-text-primary">
            {report.suggestions[0]}
          </div>
        )}
      </div>

      {open && (
        <div className="space-y-3 rounded-xl border border-border bg-bg-card p-4">
          <div className="grid gap-3 md:grid-cols-3">
            <ReportList title="高频概念" items={(report.top_concepts || []).map((item) => `${item.name} · ${item.count}`)} empty="暂无概念记录" />
            <ReportList title="薄弱点" items={(report.weak_points || []).map((item) => `${item.name} · ${item.count}`)} empty="暂无新增错题薄弱点" />
            <ReportList title={card.kind === 'daily' ? '今日建议' : '下周建议'} items={report.suggestions || []} empty="暂无建议" />
          </div>
          <div>
            <div className="mb-2 text-xs font-medium text-text-secondary">最近提问</div>
            <div className="space-y-2">
              {(report.recent_questions || []).length ? report.recent_questions.map((item, idx) => (
                <div key={`${item.time}-${idx}`} className="rounded-lg border border-border bg-[var(--surface-subtle)] px-3 py-2 text-sm">
                  <div className="mb-1 text-[11px] text-text-secondary">{item.time}</div>
                  <div className="text-text-primary">{item.question}</div>
                </div>
              )) : <div className="rounded-lg border border-dashed border-border px-3 py-4 text-center text-sm text-text-secondary">暂无问答记录</div>}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

const SimpleMarkdown: React.FC<{ content: string }> = ({ content }) => (
  <div className="markdown-body text-sm leading-relaxed whitespace-pre-wrap break-words">
    <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]} rehypePlugins={[[rehypeKatex, { strict: false, throwOnError: false, errorColor: 'inherit' }]]}>
      {prepareMathMarkdown(content || '')}
    </ReactMarkdown>
  </div>
);

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

const MistakeQuickCaptureCard: React.FC<{ bookName: string; subject: string }> = ({ bookName, subject }) => {
  const navigate = useNavigate();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState('');
  const [questionText, setQuestionText] = useState('');
  const [userAnswer, setUserAnswer] = useState('');
  const [correctAnswer, setCorrectAnswer] = useState('');
  const [captureSubject, setCaptureSubject] = useState(subject || '数学');
  const [source, setSource] = useState('');
  const [chapter, setChapter] = useState('');
  const [tags, setTags] = useState('');
  const [difficulty, setDifficulty] = useState(3);
  const [explanation, setExplanation] = useState('');
  const [imagePath, setImagePath] = useState('');
  const [loading, setLoading] = useState<'ocr' | 'solve' | 'save' | ''>('');
  const [message, setMessage] = useState('');
  const [savedId, setSavedId] = useState('');

  useEffect(() => () => {
    if (preview) URL.revokeObjectURL(preview);
  }, [preview]);

  const onFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const next = event.target.files?.[0] || null;
    if (preview) URL.revokeObjectURL(preview);
    setFile(next);
    setPreview(next ? URL.createObjectURL(next) : '');
    setMessage('');
    setSavedId('');
  };

  const runImageAction = async (solve = false) => {
    if (!file) {
      setMessage('请先选择一张错题图片。');
      return;
    }
    setLoading(solve ? 'solve' : 'ocr');
    setMessage('');
    setSavedId('');
    if (solve) setExplanation('');
    const fd = new FormData();
    fd.append('file', file);
    if (solve) {
      fd.append('user_answer', userAnswer);
      fd.append('subject', captureSubject || subject);
      fd.append('tags', tags);
    }
    try {
      const res = await fetch(`/api/mistakes/${solve ? 'solve-image' : 'recognize-image'}`, { method: 'POST', body: fd });
      const data = await res.json();
      if (!data.success) {
        setMessage(data.message || '图片处理失败');
        return;
      }
      setMessage(solve ? '解题完成，可以保存到错题本查看完整题目与解答。' : (data.message || '识别完成，请校对 LaTeX 题干。'));
      if (data.image_path) setImagePath(data.image_path);
      if (data.ocr_text) setQuestionText(data.ocr_text);
      if (data.explanation) setExplanation(data.explanation);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading('');
    }
  };

  const saveMistake = async () => {
    if (!questionText.trim()) {
      setMessage('请先识别或手动填写题干。');
      return;
    }
    if (!explanation.trim()) {
      setMessage('请先点击“看图解题”，解题完成后再保存到错题本。');
      return;
    }
    setLoading('save');
    setMessage('');
    const bookQuery = bookName ? `?book_name=${encodeURIComponent(bookName)}` : '';
    try {
      const res = await post(`/mistakes/add${bookQuery}`, {
        question_text: questionText,
        user_answer: userAnswer,
        correct_answer: correctAnswer,
        source,
        subject,
        chapter,
        tags,
        difficulty,
        mistake_type: ['错题速录'],
        image_path: imagePath,
        ocr_text: questionText,
        explanation,
      });
      if (!res?.success) {
        setMessage(res?.message || '保存失败');
        return;
      }
      const nextId = res.id || res.data?.id || '';
      setSavedId(nextId);
      setMessage(res.message || '已保存到错题本。');
      window.dispatchEvent(new Event('mistakes:changed'));
      if (nextId) navigate(`/mistakes?mistake_id=${encodeURIComponent(nextId)}`);
    } catch (err) {
      setMessage(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading('');
    }
  };

  return (
    <div className="rounded-xl border border-border bg-[var(--surface-subtle)] p-4">
      <div className="mb-3 flex items-center gap-2 text-base font-semibold text-text-primary"><ImagePlus className="h-4 w-4 text-accent" />错题速录</div>
      <div className="grid gap-3 lg:grid-cols-[240px_minmax(0,1fr)]">
        <label className="flex min-h-[180px] cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-border bg-bg-card p-3 text-center text-sm text-text-secondary hover:border-accent/50">
          {preview ? <img src={preview} alt="错题预览" className="max-h-[220px] w-full rounded-lg object-contain" /> : <><Upload className="mb-2 h-6 w-6 text-accent" />上传/拍照错题图片</>}
          <input type="file" accept="image/*" capture="environment" onChange={onFileChange} className="hidden" />
        </label>
        <div className="space-y-3">
          <div className="flex flex-wrap gap-2">
            <button type="button" disabled={!file || Boolean(loading)} onClick={() => runImageAction(false)} className="rounded-lg border border-border bg-bg-card px-3 py-1.5 text-xs text-text-primary hover:border-accent/50 disabled:opacity-50">{loading === 'ocr' ? '识别中' : '识别题干'}</button>
            <button type="button" disabled={!file || Boolean(loading)} onClick={() => runImageAction(true)} className="rounded-lg bg-accent px-3 py-1.5 text-xs font-medium text-white hover:bg-accent-hover disabled:opacity-50">{loading === 'solve' ? '解题中' : '看图解题'}</button>
          </div>
          <div className="grid gap-3 xl:grid-cols-2">
            <textarea value={questionText} onChange={(e) => setQuestionText(e.target.value)} placeholder="OCR 题干，可手动校对" className="min-h-[130px] w-full rounded-lg border border-border bg-bg-card px-3 py-2 text-sm outline-none focus:border-accent" />
            <div className="max-h-[180px] overflow-y-auto rounded-lg border border-border bg-bg-card p-3">
              <div className="mb-2 text-xs font-medium text-text-secondary">LaTeX 预览</div>
              {questionText.trim() ? <SimpleMarkdown content={questionText} /> : <div className="text-sm text-text-secondary">识别题干后会在这里渲染公式。</div>}
            </div>
          </div>
          <div className="grid gap-2 md:grid-cols-2">
            <textarea value={userAnswer} onChange={(e) => setUserAnswer(e.target.value)} placeholder="你的答案，可选" className="min-h-[70px] rounded-lg border border-border bg-bg-card px-3 py-2 text-sm outline-none focus:border-accent" />
            <textarea value={correctAnswer} onChange={(e) => setCorrectAnswer(e.target.value)} placeholder="正确答案，可选" className="min-h-[70px] rounded-lg border border-border bg-bg-card px-3 py-2 text-sm outline-none focus:border-accent" />
          </div>
          <div className="grid gap-2 md:grid-cols-5">
            <SubjectInput value={captureSubject} onChange={setCaptureSubject} placeholder="学科，如 线代" className="rounded-lg border border-border bg-bg-card px-3 py-2 text-sm outline-none focus:border-accent" />
            <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="来源" className="rounded-lg border border-border bg-bg-card px-3 py-2 text-sm outline-none focus:border-accent" />
            <input value={chapter} onChange={(e) => setChapter(e.target.value)} placeholder="章节" className="rounded-lg border border-border bg-bg-card px-3 py-2 text-sm outline-none focus:border-accent" />
            <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="标签，逗号分隔" className="rounded-lg border border-border bg-bg-card px-3 py-2 text-sm outline-none focus:border-accent" />
            <label className="flex items-center gap-2 rounded-lg border border-border bg-bg-card px-3 py-2 text-sm text-text-secondary">难度 {difficulty}<input type="range" min={1} max={5} value={difficulty} onChange={(e) => setDifficulty(Number(e.target.value))} className="min-w-0 flex-1 accent-accent" /></label>
          </div>
          {loading === 'solve' && <div className="flex items-center gap-2 rounded-lg border border-border bg-bg-card px-3 py-2 text-xs text-text-secondary"><Loader2 className="h-3.5 w-3.5 animate-spin" />正在解题...</div>}
          {explanation && <div className="flex items-center gap-2 rounded-lg border border-[#c9d8bd] bg-[#eef5e8] px-3 py-2 text-sm text-[var(--success)]"><CheckCircle2 className="h-4 w-4" />解题完成，完整解答将保存到错题本中查看。</div>}
          {explanation && <button type="button" disabled={Boolean(loading) || !questionText.trim()} onClick={saveMistake} className="inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-50">{loading === 'save' ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}{loading === 'save' ? '保存中' : '保存到错题本'}</button>}
          {savedId && <button type="button" onClick={() => navigate(`/mistakes?mistake_id=${encodeURIComponent(savedId)}`)} className="inline-flex items-center gap-2 rounded-lg border border-border bg-bg-card px-3 py-1.5 text-xs text-text-primary hover:border-accent hover:text-accent"><ExternalLink className="h-3.5 w-3.5" />查看错题记录</button>}
          {message && <div className="rounded-lg border border-border bg-bg-card px-3 py-2 text-xs text-text-secondary">{message}</div>}
        </div>
      </div>
    </div>
  );
};const ChatMessage: React.FC<ChatMessageProps> = ({ role, content, stage, linkedConcepts = [], reportCard, exerciseCard, utilityCard }) => {
  const [showSources, setShowSources] = useState(false);
  const [activeConcept, setActiveConcept] = useState<ConceptCandidate | null>(null);
  const { bookName, subject } = useChatContext();

  const references = useMemo(() => {
    if (role !== 'assistant') return [];
    const matches: string[] = [];
    const regex = /\u3010\u6765\u6e90\uff1a(.+?)\u3011/g;
    let m;
    while ((m = regex.exec(content)) !== null) {
      matches.push(m[1]);
    }
    return matches;
  }, [content, role]);

  const cleanContent = useMemo(() => {
    const withoutRefs = content.replace(/\u3010\u6765\u6e90\uff1a(.+?)\u3011/g, '');
    const mathReady = prepareMathMarkdown(withoutRefs);
    return role === 'assistant' ? linkConcepts(mathReady, linkedConcepts) : mathReady;
  }, [content, linkedConcepts, role]);

  const contentBlocks = useMemo(() => splitMarkdownForRender(cleanContent), [cleanContent]);

  const conceptByName = useMemo(() => {
    const map = new Map<string, ConceptCandidate>();
    for (const concept of linkedConcepts) {
      map.set(concept.name, concept);
    }
    return map;
  }, [linkedConcepts]);

  const isUser = role === 'user';
  const isThinking = !isUser && (stage === 'thinking' || stage === 'plan') && !content.trim();

  const markdownComponents = {
    a({ href, children }: { href?: string; children?: React.ReactNode }) {
      if (href?.startsWith('#concept-')) {
        const name = decodeURIComponent(href.replace('#concept-', ''));
        const concept = conceptByName.get(name);
        return (
          <button
            type="button"
            className="concept-link"
            title={'\u67e5\u770b\u77e5\u8bc6\u56fe\u8c31\u6982\u5ff5'}
            onClick={(e) => {
              e.preventDefault();
              if (concept) setActiveConcept(concept);
            }}
          >
            {children}
          </button>
        );
      }
      return (
        <a href={href} className="text-accent underline underline-offset-2" target="_blank" rel="noreferrer">
          {children}
        </a>
      );
    },
    p({ children }: { children?: React.ReactNode }) {
      return <p className="my-1.5">{children}</p>;
    },
    pre({ children }: { children?: React.ReactNode }) {
      return (
        <pre className="my-3 overflow-x-auto rounded-lg border border-border bg-[var(--surface-subtle)] p-3 font-mono text-xs shadow-sm">
          {children}
        </pre>
      );
    },
    code({ className, children, ...props }: { className?: string; children?: React.ReactNode }) {
      const isInline = !className;
      return isInline ? (
        <code
          className="rounded-md border border-border bg-[var(--accent-softer)] px-1.5 py-0.5 font-mono text-xs text-accent"
          {...props}
        >
          {children}
        </code>
      ) : (
        <code className={className} {...props}>
          {children}
        </code>
      );
    },
    ul({ children }: { children?: React.ReactNode }) {
      return <ul className="list-disc pl-5 my-1.5">{children}</ul>;
    },
    ol({ children }: { children?: React.ReactNode }) {
      return <ol className="list-decimal pl-5 my-1.5">{children}</ol>;
    },
    li({ children }: { children?: React.ReactNode }) {
      return <li className="my-0.5">{children}</li>;
    },
    h1({ children }: { children?: React.ReactNode }) {
      return <h1 className="text-lg font-bold my-2">{children}</h1>;
    },
    h2({ children }: { children?: React.ReactNode }) {
      return <h2 className="text-base font-bold my-2">{children}</h2>;
    },
    h3({ children }: { children?: React.ReactNode }) {
      return <h3 className="text-sm font-bold my-1.5">{children}</h3>;
    },
    blockquote({ children }: { children?: React.ReactNode }) {
      return (
        <blockquote className="my-2 border-l-2 border-border pl-3 text-text-secondary">
          {children}
        </blockquote>
      );
    },
    table({ children }: { children?: React.ReactNode }) {
      return (
        <div className="my-2 overflow-x-auto">
          <table className="border-collapse border border-border text-xs">
            {children}
          </table>
        </div>
      );
    },
    th({ children }: { children?: React.ReactNode }) {
      return (
        <th className="border border-border bg-bg-secondary px-2 py-1">
          {children}
        </th>
      );
    },
    td({ children }: { children?: React.ReactNode }) {
      return (
        <td className="border border-border px-2 py-1">
          {children}
        </td>
      );
    },
  };

  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'} mb-5`}>
      <div
        className={`max-w-[min(86%,820px)] rounded-2xl px-4 py-3 shadow-sm ${
          isUser
            ? 'bg-accent text-white'
            : 'border border-border bg-bg-card text-text-primary'
        }`}
      >
        <div className="mb-2 flex items-center gap-2">
          {isUser ? (
            <User className="h-4 w-4" />
          ) : (
            <Bot className="h-4 w-4 text-accent" />
          )}
          <span className="text-xs opacity-70">
            {isUser ? '\u4f60' : 'AI \u52a9\u624b'}
          </span>
        </div>

        {reportCard ? (
          <ReportCard card={reportCard} />
        ) : exerciseCard ? (
          <ExerciseCard card={exerciseCard} bookName={bookName} />
        ) : utilityCard?.kind === 'mistake_quick_capture' ? (
          <MistakeQuickCaptureCard bookName={bookName} subject={subject} />
        ) : isThinking ? (
          <div className="flex items-center gap-2 py-2 text-text-secondary">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-border border-t-accent" />
            <span className="text-sm">{'\u601d\u8003\u4e2d...'}</span>
          </div>
        ) : (
          <div className="markdown-body text-[15px] leading-relaxed whitespace-pre-wrap break-words">
            {contentBlocks.map((block, index) => {
              const key = blockKey(block, index);
              return (
                <ErrorBoundary key={key} resetKey={key} fallback={<PlainMarkdownFallback content={block} />}>
                  <ReactMarkdown
                    remarkPlugins={[remarkGfm, remarkMath]}
                    rehypePlugins={[[rehypeKatex, { strict: false, throwOnError: false, errorColor: 'inherit' }]]}
                    components={markdownComponents}
                  >
                    {block}
                  </ReactMarkdown>
                </ErrorBoundary>
              );
            })}
          </div>
        )}

        {!reportCard && !exerciseCard && !utilityCard && !isThinking && linkedConcepts.length > 0 && (
          <div className="mt-4 flex flex-wrap gap-1.5 border-t border-border pt-3">
            {linkedConcepts.slice(0, 8).map((concept) => (
              <button
                key={concept.concept_id || concept.name}
                type="button"
                onClick={() => setActiveConcept(concept)}
                className="rounded-md border border-border bg-[var(--accent-softer)] px-2 py-1 text-xs text-text-primary transition-colors hover:border-accent hover:text-accent"
              >
                {concept.name}
              </button>
            ))}
          </div>
        )}

        {!reportCard && !exerciseCard && !utilityCard && !isThinking && references.length > 0 && (
          <div className="mt-3 border-t border-border pt-2">
            <button
              onClick={() => setShowSources(!showSources)}
              className="flex items-center gap-1 text-xs text-text-secondary transition-colors hover:text-text-primary"
            >
              <BookOpen className="h-3 w-3" />
              {showSources ? '\u9690\u85cf\u6765\u6e90' : `\u67e5\u770b\u6765\u6e90 (${references.length})`}
            </button>
            {showSources && (
              <div className="mt-2 space-y-1">
                {references.map((ref, idx) => (
                  <div
                    key={idx}
                    className="rounded-md border border-border bg-[var(--surface-subtle)] px-2 py-1 text-xs text-text-secondary"
                  >
                    {ref}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
      {activeConcept && (
        <ConceptPopover concept={activeConcept} bookName={bookName} onClose={() => setActiveConcept(null)} />
      )}
    </div>
  );
};

export default ChatMessage;
