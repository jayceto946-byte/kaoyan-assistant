import React, { useEffect, useRef, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  BookOpenCheck,
  BrainCircuit,
  Camera,
  Check,
  ChevronDown,
  ChevronRight,
  Crop,
  ImagePlus,
  Loader2,
  Pencil,
  Plus,
  Search,
  SlidersHorizontal,
  Sparkles,
  TrendingUp,
  Upload,
  X,
} from 'lucide-react';
import { get, post } from '../api/client';
import ChatMessage from '../components/ChatMessage';
import SubjectInput from '../components/SubjectInput';
import { useChatContext } from '../contexts/ChatContext';
import type { MistakeRecord, MistakeStats, WeakPoint } from '../types';

const TABS = ['录入', '列表', '今日复习', '统计'] as const;
type Tab = (typeof TABS)[number];

type MistakeForm = {
  question_text: string;
  user_answer: string;
  correct_answer: string;
  source: string;
  subject: string;
  chapter: string;
  tags: string;
  difficulty: number;
  ocr_text: string;
  explanation: string;
  mistake_type: string[];
  image_path?: string;
};

type CropState = { x: number; y: number; w: number; h: number };
type ImageAdjust = { brightness: number; contrast: number; sharpen: number; grayscale: boolean };

const EMPTY_FORM: MistakeForm = {
  question_text: '',
  user_answer: '',
  correct_answer: '',
  source: '',
  subject: '数学',
  chapter: '',
  tags: '',
  difficulty: 3,
  ocr_text: '',
  explanation: '',
  mistake_type: [],
  image_path: undefined,
};

const DEFAULT_CROP: CropState = { x: 5, y: 8, w: 90, h: 78 };
const DEFAULT_ADJUST: ImageAdjust = { brightness: 112, contrast: 138, sharpen: 35, grayscale: true };
const MISTAKE_TYPE_OPTIONS = ['概念不清', '公式记错', '计算错误', '思路卡住', '粗心/审题错误'];
const qualityLabels = ['完全不会', '很吃力', '勉强', '基本会', '熟练', '秒杀'];

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

function applySharpen(imageData: ImageData, amount: number) {
  if (amount <= 0) return imageData;
  const strength = amount / 100;
  const { data, width, height } = imageData;
  const copy = new Uint8ClampedArray(data);
  const center = 1 + 4 * strength;
  const side = -strength;
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const idx = (y * width + x) * 4;
      for (let c = 0; c < 3; c += 1) {
        const v =
          copy[idx + c] * center +
          copy[idx - 4 + c] * side +
          copy[idx + 4 + c] * side +
          copy[idx - width * 4 + c] * side +
          copy[idx + width * 4 + c] * side;
        data[idx + c] = clamp(v, 0, 255);
      }
    }
  }
  return imageData;
}

async function fileToImage(file: File): Promise<HTMLImageElement> {
  const url = URL.createObjectURL(file);
  try {
    const img = new Image();
    img.decoding = 'async';
    await new Promise<void>((resolve, reject) => {
      img.onload = () => resolve();
      img.onerror = () => reject(new Error('图片加载失败'));
      img.src = url;
    });
    return img;
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function renderProcessedImage(file: File, crop: CropState, adjust: ImageAdjust): Promise<{ file: File; preview: string }> {
  const img = await fileToImage(file);
  const sx = Math.round((crop.x / 100) * img.naturalWidth);
  const sy = Math.round((crop.y / 100) * img.naturalHeight);
  const sw = Math.round((crop.w / 100) * img.naturalWidth);
  const sh = Math.round((crop.h / 100) * img.naturalHeight);
  const maxSide = 1800;
  const scale = Math.min(1, maxSide / Math.max(sw, sh));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(sw * scale));
  canvas.height = Math.max(1, Math.round(sh * scale));
  const ctx = canvas.getContext('2d');
  if (!ctx) throw new Error('无法处理图片');
  ctx.filter = `brightness(${adjust.brightness}%) contrast(${adjust.contrast}%)${adjust.grayscale ? ' grayscale(100%)' : ''}`;
  ctx.drawImage(img, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
  const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
  ctx.putImageData(applySharpen(imageData, adjust.sharpen), 0, 0);
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob((next) => (next ? resolve(next) : reject(new Error('图片导出失败'))), 'image/jpeg', 0.9);
  });
  const processed = new File([blob], file.name.replace(/\.[^.]+$/, '') + '_scan.jpg', { type: 'image/jpeg' });
  return { file: processed, preview: URL.createObjectURL(blob) };
}

function deriveMistakeTitle(record: MistakeRecord) {
  const raw = record.question_text || record.ocr_text || record.source || '未命名错题';
  const cleaned = raw
    .replace(/\$\$[\s\S]*?\$\$/g, ' ')
    .replace(/\$(?:\\.|[^$\\])*?\$/g, ' ')
    .replace(/\\[a-zA-Z]+(?:\{[^}]*\})?/g, ' ')
    .replace(/[\[\]{}()*_#>`~|=+\\]/g, ' ')
    .split('\n')
    .map((line) => line.replace(/^\s*(题目|例题|解|证明|已知|求|问)[:：、.\s]*/g, '').trim())
    .find((line) => line.length >= 6);
  const title = cleaned || raw.replace(/\s+/g, ' ').trim();
  return title.length > 43 ? `${title.slice(0, 43)}...` : title;
}
const MistakesPage: React.FC = () => {
  const { bookName } = useChatContext();
  const [searchParams] = useSearchParams();
  const focusMistakeId = searchParams.get('mistake_id') || '';
  const bookQuery = bookName ? `?book_name=${encodeURIComponent(bookName)}` : '';
  const [activeTab, setActiveTab] = useState<Tab>('录入');
  const [records, setRecords] = useState<MistakeRecord[]>([]);
  const [dueRecords, setDueRecords] = useState<MistakeRecord[]>([]);
  const [stats, setStats] = useState<MistakeStats | null>(null);
  const [weakPoints, setWeakPoints] = useState<WeakPoint[]>([]);
  const [pageLoading, setPageLoading] = useState(false);
  const [pageError, setPageError] = useState('');
  const [subjectFilter, setSubjectFilter] = useState('');
  const [form, setForm] = useState<MistakeForm>(EMPTY_FORM);
  const [rawFile, setRawFile] = useState<File | null>(null);
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [rawPreview, setRawPreview] = useState('');
  const [imagePreview, setImagePreview] = useState('');
  const [cropOpen, setCropOpen] = useState(false);
  const [crop, setCrop] = useState<CropState>(DEFAULT_CROP);
  const [adjust, setAdjust] = useState<ImageAdjust>(DEFAULT_ADJUST);
  const [uploadMessage, setUploadMessage] = useState('');
  const [ocrLoading, setOcrLoading] = useState(false);
  const [solveLoading, setSolveLoading] = useState(false);
  const [explanation, setExplanation] = useState('');
  const [expandedId, setExpandedId] = useState('');
  const [expandedReviewId, setExpandedReviewId] = useState('');
  const [reviewMessage, setReviewMessage] = useState('');
  const [savedRecord, setSavedRecord] = useState<MistakeRecord | null>(null);
  const [dragActive, setDragActive] = useState(false);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editDraft, setEditDraft] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const explanationRef = useRef('');

  const setField = <K extends keyof MistakeForm>(key: K, value: MistakeForm[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const loadList = async () => {
    try {
      const res = await post(`/mistakes/list${bookQuery}`, { subject: '', search_kw: '', limit: 50 });
      if (res?.success) setRecords(res.data || []);
    } catch (e) {
      console.error('loadList error:', e);
    }
  };

  const loadDue = async () => {
    try {
      const res = await get(`/mistakes/due${bookQuery}`);
      if (res?.success) setDueRecords(res.data || []);
    } catch (e) {
      console.error('loadDue error:', e);
    }
  };

  const loadStats = async () => {
    setPageLoading(true);
    setPageError('');
    try {
      const statsRes = await get(`/mistakes/stats${bookQuery}`);
      setStats(statsRes && typeof statsRes.total === 'number' ? statsRes : null);
      const weakRes = await get(`/mistakes/weak-points${bookQuery}`);
      setWeakPoints(weakRes?.success ? weakRes.data || [] : []);
    } catch (e) {
      setPageError('加载统计数据失败');
      setStats(null);
      setWeakPoints([]);
    } finally {
      setPageLoading(false);
    }
  };

  useEffect(() => {
    loadList();
    loadDue();
  }, [bookQuery, subjectFilter]);

  useEffect(() => {
    if (activeTab === '统计') loadStats();
  }, [activeTab]);

  useEffect(() => {
    if (!focusMistakeId) return;
    setActiveTab('列表');
    setExpandedId(focusMistakeId);
    if (records.some((record) => record.id === focusMistakeId)) return;
    let cancelled = false;
    const loadFocusedMistake = async () => {
      try {
        const res = await get(`/mistakes/${encodeURIComponent(focusMistakeId)}${bookQuery}`);
        if (!cancelled && res?.success && res.data) {
          const record = res.data as MistakeRecord;
          setRecords((prev) => [record, ...prev.filter((item) => item.id !== record.id)]);
        }
      } catch (e) {
        console.error('loadFocusedMistake error:', e);
      }
    };
    loadFocusedMistake();
    return () => {
      cancelled = true;
    };
  }, [focusMistakeId, bookQuery, records]);

  useEffect(() => {
    return () => {
      if (rawPreview) URL.revokeObjectURL(rawPreview);
      if (imagePreview) URL.revokeObjectURL(imagePreview);
    };
  }, [rawPreview, imagePreview]);

  const acceptFile = (file: File) => {
    if (!file.type.startsWith('image/')) {
      setUploadMessage('请上传图片文件');
      return;
    }
    if (rawPreview) URL.revokeObjectURL(rawPreview);
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setRawFile(file);
    setImageFile(null);
    setRawPreview(URL.createObjectURL(file));
    setImagePreview('');
    setCrop(DEFAULT_CROP);
    setAdjust(DEFAULT_ADJUST);
    setCropOpen(true);
    setUploadMessage('');
    setExplanation('');
    explanationRef.current = '';
    setSavedRecord(null);
    setField('question_text', '');
    setField('ocr_text', '');
    setField('explanation', '');
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const nextFile = e.target.files?.[0];
    if (nextFile) acceptFile(nextFile);
  };

  const applyImageProcessing = async () => {
    if (!rawFile) return;
    setUploadMessage('正在生成 OCR 工作图...');
    const processed = await renderProcessedImage(rawFile, crop, adjust);
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setImageFile(processed.file);
    setImagePreview(processed.preview);
    setCropOpen(false);
    setUploadMessage('已生成 OCR 工作图，可以识别题干或看图解题。');
  };

  const resetForm = () => {
    setForm(EMPTY_FORM);
    setRawFile(null);
    setImageFile(null);
    setUploadMessage('');
    setExplanation('');
    explanationRef.current = '';
    setSavedRecord(null);
    setEditorOpen(false);
    setEditDraft('');
    if (rawPreview) URL.revokeObjectURL(rawPreview);
    if (imagePreview) URL.revokeObjectURL(imagePreview);
    setRawPreview('');
    setImagePreview('');
    if (inputRef.current) inputRef.current.value = '';
  };

  const uploadForOcr = async (solve = false) => {
    if (!imageFile) {
      setUploadMessage('请先裁剪并生成 OCR 工作图');
      return;
    }
    setOcrLoading(!solve);
    setSolveLoading(solve);
    setUploadMessage('');
    if (!solve) {
      setExplanation('');
      explanationRef.current = '';
      setField('explanation', '');
    }

    const fd = new FormData();
    fd.append('file', imageFile);
    if (solve) {
      fd.append('user_answer', form.user_answer);
    }

    try {
      const res = await fetch(`/api/mistakes/${solve ? 'solve-image' : 'recognize-image'}`, { method: 'POST', body: fd });
      const data = await res.json();
      setUploadMessage(data.message || (data.success ? '处理完成' : '处理失败'));
      if (data.image_path) setField('image_path', data.image_path);
      if (data.ocr_text) {
        setField('question_text', data.ocr_text);
        setField('ocr_text', data.ocr_text);
      }
      if (data.explanation) {
        explanationRef.current = data.explanation;
        setExplanation(data.explanation);
        setField('explanation', data.explanation);
      }
    } catch (e) {
      setUploadMessage(`图片处理失败: ${String(e)}`);
    } finally {
      setOcrLoading(false);
      setSolveLoading(false);
    }
  };

  const handleAdd = async () => {
    if (!form.question_text.trim()) return;
    const currentExplanation = form.explanation || explanation || explanationRef.current;
    const payload = { ...form, explanation: currentExplanation };
    try {
      const res = await post(`/mistakes/add${bookQuery}`, payload);
      if (!res?.success) {
        setUploadMessage(res?.message || '保存失败');
        return;
      }
      setUploadMessage(res.message || '已保存，解答已写入错题记录。');
      setForm((prev) => ({ ...prev, explanation: currentExplanation }));
      explanationRef.current = currentExplanation;
      if (currentExplanation) setExplanation(currentExplanation);
      const nextRecord = res.data ? { ...res.data, explanation: res.data.explanation || currentExplanation } : null;
      if (nextRecord) {
        setSavedRecord(nextRecord);
        setRecords((prev) => [nextRecord, ...prev.filter((item) => item.id !== nextRecord.id)]);
        setDueRecords((prev) => [nextRecord, ...prev.filter((item) => item.id !== nextRecord.id)]);
        setExpandedId(nextRecord.id);
        setExpandedReviewId(nextRecord.id);
      }
      await loadDue();
    } catch (e) {
      setUploadMessage(`保存失败: ${String(e)}`);
    }
  };

  const handleReview = async (id: string, quality: number) => {
    setReviewMessage('');
    const res = await post(`/mistakes/review${bookQuery}`, { id, quality });
    if (!res?.success) {
      setReviewMessage(res?.message || '复习记录失败');
      return;
    }
    const updated = res.data as MistakeRecord | undefined;
    if (updated) {
      setRecords((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setDueRecords((prev) => prev.map((item) => (item.id === updated.id ? updated : item)));
      setReviewMessage(res.message || `已记录复习，下次复习：${updated.next_review || '待计算'}`);
    } else {
      setReviewMessage(res.message || '已记录复习');
    }
    await loadDue();
    await loadStats();
  };

  const openQuestionEditor = () => {
    setEditDraft(form.question_text);
    setEditorOpen(true);
  };

  const confirmQuestionEdit = () => {
    setField('question_text', editDraft);
    setEditorOpen(false);
  };

  const toggleMistakeType = (type: string, checked: boolean) => {
    setForm((prev) => ({
      ...prev,
      mistake_type: checked ? [...prev.mistake_type, type] : prev.mistake_type.filter((item) => item !== type),
    }));
  };

  const renderQuestionPreview = () => (
    <section className="rounded-xl border border-border bg-bg-secondary/95 p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-text-primary">LaTeX 题干预览</div>
        <button
          onClick={openQuestionEditor}
          disabled={!form.question_text.trim()}
          className="flex items-center gap-1.5 rounded-xl border border-border bg-bg-primary px-3 py-1.5 text-sm text-text-primary hover:border-accent disabled:opacity-45"
        >
          <Pencil className="h-4 w-4" /> 修改
        </button>
      </div>
      {form.question_text.trim() ? (
        <ChatMessage role="assistant" content={form.question_text} />
      ) : (
        <div className="rounded-xl border border-dashed border-border bg-bg-primary px-4 py-10 text-center text-sm text-text-secondary">
          识别题干后会在这里显示 LaTeX 预览。需要改 OCR 文本时点右上角“修改”。
        </div>
      )}
    </section>
  );

  const renderExplanation = () => {
    if (!explanation && !solveLoading) return null;
    return (
      <section className="space-y-3 rounded-xl border border-border bg-bg-secondary/95 p-4">
        <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
          <BrainCircuit className="h-4 w-4 text-accent" /> 解题讲解
        </div>
        {solveLoading ? (
          <div className="flex items-center gap-2 py-6 text-sm text-text-secondary">
            <Loader2 className="h-4 w-4 animate-spin" /> 正在生成讲解...
          </div>
        ) : (
          <ChatMessage role="assistant" content={explanation} />
        )}
      </section>
    );
  };

  const renderMetadataAndSave = () => {
    const currentExplanation = form.explanation || explanation || explanationRef.current;
    if (!currentExplanation && !savedRecord) return null;
    return (
      <section className="space-y-4 rounded-xl border border-border bg-bg-card shadow-sm p-4">
        <div className="text-sm font-medium text-text-primary">归档信息</div>
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <input placeholder="来源，如 2024 真题 / 教材 P45" value={form.source} onChange={(e) => setField('source', e.target.value)} className="rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none placeholder-text-secondary focus:border-accent" />
          <SubjectInput placeholder="学科，如 线代 / 微积分" value={form.subject} onChange={(value) => setField('subject', value)} suggestions={records.map((item) => item.subject || '')} className="rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none placeholder-text-secondary focus:border-accent" />
          <input placeholder="章节，可选" value={form.chapter} onChange={(e) => setField('chapter', e.target.value)} className="rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none placeholder-text-secondary focus:border-accent" />
          <input placeholder="知识点标签，逗号分隔" value={form.tags} onChange={(e) => setField('tags', e.target.value)} className="rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none placeholder-text-secondary focus:border-accent md:col-span-2" />
          <label className="flex items-center gap-3 rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary">
            <span className="flex-shrink-0 text-text-secondary">难度 {form.difficulty}</span>
            <input type="range" min={1} max={5} value={form.difficulty} onChange={(e) => setField('difficulty', Number(e.target.value))} className="w-full accent-accent" />
          </label>
        </div>
        <div className="space-y-2">
          <div className="text-sm font-medium text-text-primary">标记错因</div>
          <div className="flex flex-wrap gap-3">
            {MISTAKE_TYPE_OPTIONS.map((type) => (
              <label key={type} className="flex cursor-pointer items-center gap-1.5 text-sm text-text-primary">
                <input type="checkbox" checked={form.mistake_type.includes(type)} onChange={(e) => toggleMistakeType(type, e.target.checked)} className="accent-accent" />
                {type}
              </label>
            ))}
          </div>
        </div>
        {savedRecord && (
          <div className="rounded-lg border border-[#c9d8bd] bg-[#eef5e8] px-3 py-2 text-sm text-[var(--success)]">
            已保存成功，解答会在“列表”和“今日复习”中随错题一起展开显示。
          </div>
        )}
        <div className="flex justify-end gap-2">
          {savedRecord && (
            <button onClick={resetForm} className="flex items-center gap-2 rounded-xl border border-border px-4 py-2 text-sm text-text-primary hover:border-accent">
              <Plus className="h-4 w-4" /> 下一题
            </button>
          )}
          <button onClick={handleAdd} disabled={!form.question_text.trim()} className="flex items-center gap-2 rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-45">
            <Check className="h-4 w-4" /> {savedRecord ? '再次保存' : '保存错题'}
          </button>
        </div>
      </section>
    );
  };

  const renderSavedRecordDetail = (record: MistakeRecord, showCorrectAnswer = false) => (
    <div className="mt-4 space-y-4 border-t border-border pt-4">
      <section className="space-y-2">
        <div className="text-xs font-medium text-text-secondary">LaTeX 题干</div>
        <div className="rounded-xl border border-border bg-bg-secondary p-3">
          <ChatMessage role="assistant" content={record.question_text} linkedConcepts={record.linked_concepts || []} />
        </div>
      </section>
      <section className="space-y-2">
        <div className="text-xs font-medium text-text-secondary">对应概念</div>
        <div className="flex flex-wrap gap-2 rounded-xl border border-border bg-bg-secondary p-3">
          {record.linked_concepts?.length ? (
            record.linked_concepts.map((concept) => (
              <span key={concept.concept_id || concept.name} className="rounded border border-accent/30 bg-accent/10 px-2 py-1 text-xs font-medium text-accent-hover">
                {concept.name}
              </span>
            ))
          ) : (
            <span className="text-sm text-text-secondary">暂无对应概念</span>
          )}
        </div>
      </section>
      {showCorrectAnswer && (
        <section className="space-y-2">
          <div className="text-xs font-medium text-text-secondary">正确答案</div>
          <div className="rounded-xl border border-border bg-bg-secondary p-3">
            {record.correct_answer ? <ChatMessage role="assistant" content={record.correct_answer} linkedConcepts={record.linked_concepts || []} /> : <div className="text-sm text-text-secondary">暂无正确答案</div>}
          </div>
        </section>
      )}
      <section className="space-y-2">
        <div className="text-xs font-medium text-text-secondary">已保存解答</div>
        <div className="rounded-xl border border-border bg-bg-secondary p-3">
          {record.explanation ? <ChatMessage role="assistant" content={record.explanation} linkedConcepts={record.linked_concepts || []} /> : <div className="text-sm text-text-secondary">暂无已保存解答</div>}
        </div>
      </section>
    </div>
  );
  const renderQuestionEditor = () => {
    if (!editorOpen) return null;
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
        <div className="w-full max-w-4xl rounded-xl border border-border bg-bg-primary p-4 shadow-xl">
          <div className="mb-3 flex items-center justify-between">
            <div className="text-sm font-medium text-text-primary">修改 OCR 题干</div>
            <button onClick={() => setEditorOpen(false)} className="rounded p-1 text-text-secondary hover:text-text-primary"><X className="h-5 w-5" /></button>
          </div>
          <textarea
            value={editDraft}
            onChange={(e) => setEditDraft(e.target.value)}
            className="min-h-[320px] w-full rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none focus:border-accent"
          />
          <div className="mt-4 flex justify-end gap-2">
            <button onClick={() => setEditorOpen(false)} className="rounded-xl border border-border px-4 py-2 text-sm text-text-secondary hover:border-accent hover:text-text-primary">取消</button>
            <button onClick={confirmQuestionEdit} className="rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">确认</button>
          </div>
        </div>
      </div>
    );
  };

  const renderCropModal = () => {
    if (!cropOpen || !rawPreview) return null;
    return (
      <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 p-4">
        <div className="grid max-h-[92vh] w-full max-w-6xl grid-cols-1 gap-4 overflow-y-auto rounded-xl border border-border bg-bg-primary p-4 shadow-xl lg:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2 text-sm font-medium text-text-primary"><Crop className="h-4 w-4 text-accent" /> 裁剪错题区域</div>
              <button onClick={() => setCropOpen(false)} className="rounded p-1 text-text-secondary hover:text-text-primary"><X className="h-5 w-5" /></button>
            </div>
            <div className="relative mx-auto max-h-[70vh] max-w-full overflow-hidden rounded border border-border bg-bg-secondary">
              <img src={rawPreview} alt="原图" className="max-h-[70vh] w-full object-contain" style={{ filter: `brightness(${adjust.brightness}%) contrast(${adjust.contrast}%)${adjust.grayscale ? ' grayscale(100%)' : ''}` }} />
              <div className="absolute border-2 border-accent bg-accent/10 shadow-[0_0_0_9999px_rgba(0,0,0,0.35)]" style={{ left: `${crop.x}%`, top: `${crop.y}%`, width: `${crop.w}%`, height: `${crop.h}%` }} />
            </div>
          </div>
          <div className="space-y-4 rounded-xl border border-border bg-bg-card shadow-sm p-4">
            <div className="flex items-center gap-2 text-sm font-medium text-text-primary"><SlidersHorizontal className="h-4 w-4 text-accent" /> 扫描增强</div>
            <Range label="左边界" value={crop.x} min={0} max={90} onChange={(v) => setCrop((c) => ({ ...c, x: v, w: Math.min(c.w, 100 - v) }))} />
            <Range label="上边界" value={crop.y} min={0} max={90} onChange={(v) => setCrop((c) => ({ ...c, y: v, h: Math.min(c.h, 100 - v) }))} />
            <Range label="宽度" value={crop.w} min={10} max={100 - crop.x} onChange={(v) => setCrop((c) => ({ ...c, w: v }))} />
            <Range label="高度" value={crop.h} min={10} max={100 - crop.y} onChange={(v) => setCrop((c) => ({ ...c, h: v }))} />
            <div className="border-t border-border pt-3" />
            <Range label="亮度" value={adjust.brightness} min={70} max={150} onChange={(v) => setAdjust((a) => ({ ...a, brightness: v }))} suffix="%" />
            <Range label="对比度" value={adjust.contrast} min={80} max={200} onChange={(v) => setAdjust((a) => ({ ...a, contrast: v }))} suffix="%" />
            <Range label="锐化" value={adjust.sharpen} min={0} max={100} onChange={(v) => setAdjust((a) => ({ ...a, sharpen: v }))} suffix="%" />
            <label className="flex items-center gap-2 text-sm text-text-primary"><input type="checkbox" checked={adjust.grayscale} onChange={(e) => setAdjust((a) => ({ ...a, grayscale: e.target.checked }))} className="accent-accent" />黑白扫描效果</label>
            <button onClick={applyImageProcessing} className="w-full rounded-xl bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover">使用该区域</button>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center border-b border-border bg-bg-secondary px-4">
        {TABS.map((tab) => (
          <button key={tab} onClick={() => setActiveTab(tab)} className={`border-b-2 px-4 py-3 text-sm font-medium transition-colors ${activeTab === tab ? 'border-accent text-accent' : 'border-transparent text-text-secondary hover:text-text-primary'}`}>{tab}</button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {activeTab === '录入' && (
          <div className="mx-auto max-w-6xl space-y-5">
            <div className="grid grid-cols-1 gap-5 lg:grid-cols-[360px_minmax(0,1fr)]">
              <div className="space-y-3">
                <div
                  onClick={() => inputRef.current?.click()}
                  onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
                  onDragLeave={() => setDragActive(false)}
                  onDrop={(e) => { e.preventDefault(); setDragActive(false); const file = e.dataTransfer.files?.[0]; if (file) acceptFile(file); }}
                  className={`cursor-pointer rounded-lg border-2 border-dashed bg-bg-card p-5 text-center transition-colors ${dragActive ? 'border-accent' : 'border-border hover:border-accent/60'}`}
                >
                  {imagePreview || rawPreview ? (
                    <img src={imagePreview || rawPreview} alt="错题预览" className="mx-auto max-h-[340px] w-full rounded border border-border bg-bg-primary object-contain" />
                  ) : (
                    <div className="flex min-h-[240px] flex-col items-center justify-center text-text-secondary">
                      <ImagePlus className="mb-3 h-10 w-10" />
                      <div className="text-sm font-medium text-text-primary">拖拽图片到这里，或点击上传/拍照</div>
                      <div className="mt-1 text-xs">电脑端支持拖拽，手机端可调用相机</div>
                    </div>
                  )}
                  <input ref={inputRef} type="file" accept="image/*" capture="environment" onChange={handleFileChange} className="hidden" />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={() => inputRef.current?.click()} className="flex items-center justify-center gap-2 rounded-xl border border-border bg-bg-card shadow-sm px-3 py-2 text-sm text-text-primary hover:border-accent"><Camera className="h-4 w-4" /> 上传/拍照</button>
                  <button onClick={() => rawFile && setCropOpen(true)} disabled={!rawFile} className="flex items-center justify-center gap-2 rounded-xl border border-border bg-bg-card shadow-sm px-3 py-2 text-sm text-text-primary hover:border-accent disabled:opacity-45"><Crop className="h-4 w-4" /> 重新裁剪</button>
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <button onClick={() => uploadForOcr(false)} disabled={!imageFile || ocrLoading || solveLoading} className="flex items-center justify-center gap-2 rounded-xl border border-border bg-bg-card shadow-sm px-3 py-2 text-sm text-text-primary hover:border-accent disabled:opacity-45">{ocrLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />} 识别题干</button>
                  <button onClick={() => uploadForOcr(true)} disabled={!imageFile || ocrLoading || solveLoading} className="flex items-center justify-center gap-2 rounded-xl bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover disabled:opacity-45">{solveLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} 看图解题</button>
                </div>
                {uploadMessage && <div className="rounded-xl border border-border bg-bg-secondary px-3 py-2 text-sm text-text-secondary">{uploadMessage}</div>}
              </div>

              <div className="space-y-4">
                <div className="flex items-center justify-between gap-3">
                  <h2 className="flex items-center gap-2 text-lg font-semibold"><Plus className="h-5 w-5 text-accent" /> 录入错题</h2>
                  <button onClick={resetForm} className="rounded-xl border border-border px-3 py-1.5 text-sm text-text-secondary hover:border-accent hover:text-text-primary">清空</button>
                </div>
                {renderQuestionPreview()}
                <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                  <textarea placeholder="用户答案，可选" value={form.user_answer} onChange={(e) => setField('user_answer', e.target.value)} className="min-h-[80px] rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none placeholder-text-secondary focus:border-accent" />
                  <textarea placeholder="正确答案，可选" value={form.correct_answer} onChange={(e) => setField('correct_answer', e.target.value)} className="min-h-[80px] rounded-xl border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary outline-none placeholder-text-secondary focus:border-accent" />
                </div>
              </div>
            </div>
            {renderExplanation()}
            {renderMetadataAndSave()}
          </div>
        )}

        {activeTab === '列表' && (
          <div className="mx-auto max-w-5xl space-y-4">
            <div className="flex flex-wrap items-center justify-between gap-3 text-text-secondary">
              <div className="flex items-center gap-2"><Search className="h-4 w-4" /><span className="text-sm">共 {records.length} 条错题</span></div>
              <div className="flex flex-wrap items-center gap-2">
                <SubjectInput value={subjectFilter} onChange={setSubjectFilter} suggestions={records.map((item) => item.subject || '')} placeholder="全部学科" className="h-9 rounded-xl border border-border bg-bg-primary px-3 text-sm text-text-primary outline-none focus:border-accent" />
                {subjectFilter && <button onClick={() => setSubjectFilter('')} className="rounded-xl border border-border px-3 py-1.5 text-sm hover:border-accent hover:text-text-primary">全部</button>}
                <button onClick={() => setActiveTab('录入')} className="flex items-center gap-2 rounded-xl border border-border px-3 py-1.5 text-sm hover:border-accent hover:text-text-primary"><Plus className="h-4 w-4" /> 新增</button>
              </div>
            </div>            <div className="space-y-3">
              {records.map((record) => {
                const expanded = expandedId === record.id;
                return (
                  <div key={record.id} className="rounded-xl border border-border bg-bg-card shadow-sm p-4 transition-colors hover:border-accent/50">
                    <button type="button" onClick={() => setExpandedId(expanded ? '' : record.id)} className="flex w-full items-start justify-between gap-3 text-left">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
                          {expanded ? <ChevronDown className="h-4 w-4 text-accent" /> : <ChevronRight className="h-4 w-4 text-text-secondary" />}
                          <span className="truncate">{deriveMistakeTitle(record)}</span>
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-text-secondary">
                          <span>{record.subject || '未分类'}</span>
                          {record.chapter && <span>{record.chapter}</span>}
                          <span>{record.tags.join(', ') || '无标签'}</span>
                          <span className="text-accent">难度 {record.difficulty}</span>
                        </div>
                      </div>
                      <span className="flex-shrink-0 text-xs text-text-secondary">{record.id}</span>
                    </button>
                    {expanded && renderSavedRecordDetail(record)}
                  </div>
                );
              })}
              {records.length === 0 && <div className="py-12 text-center text-text-secondary">还没有错题，先上传或手动录入一题。</div>}
            </div>
          </div>
        )}
        {activeTab === '今日复习' && (
          <div className="mx-auto max-w-5xl space-y-4">
            <div className="flex items-center gap-2 text-text-secondary"><BookOpenCheck className="h-4 w-4" /><span className="text-sm">今日待复习 {dueRecords.length} 道</span></div>
            {reviewMessage && <div className="rounded-lg border border-[#c9d8bd] bg-[#eef5e8] px-3 py-2 text-sm text-[var(--success)]">{reviewMessage}</div>}
            <div className="space-y-3">
              {dueRecords.map((record) => {
                const expanded = expandedReviewId === record.id;
                return (
                  <div key={record.id} className="rounded-xl border border-border bg-bg-card shadow-sm p-4 transition-colors hover:border-accent/50">
                    <button type="button" onClick={() => setExpandedReviewId(expanded ? '' : record.id)} className="flex w-full items-start justify-between gap-3 text-left">
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2 text-sm font-medium text-text-primary">
                          {expanded ? <ChevronDown className="h-4 w-4 text-accent" /> : <ChevronRight className="h-4 w-4 text-text-secondary" />}
                          <span className="truncate">{deriveMistakeTitle(record)}</span>
                        </div>
                        <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-text-secondary">
                          <span>{record.subject || '未分类'}</span>
                          {record.chapter && <span>{record.chapter}</span>}
                          <span>{record.tags.join(', ') || '无标签'}</span>
                          <span className="text-accent">难度 {record.difficulty}</span>
                        </div>
                      </div>
                      <span className="flex-shrink-0 text-xs text-text-secondary">间隔: {record.interval ?? 1} 天</span>
                    </button>
                    {expanded && renderSavedRecordDetail(record, true)}
                    <div className="mt-4 flex flex-wrap items-center gap-2 border-t border-border pt-4">
                      {[1, 2, 3, 4, 5].map((quality) => (
                        <button key={quality} onClick={() => handleReview(record.id, quality)} className="rounded border border-border bg-bg-primary px-3 py-1 text-xs transition-colors hover:border-accent hover:text-accent">
                          {quality} {qualityLabels[quality]}
                        </button>
                      ))}
                    </div>
                  </div>
                );
              })}
              {dueRecords.length === 0 && <div className="py-12 text-center text-text-secondary">今日暂无待复习错题</div>}
            </div>
          </div>
        )}

        {activeTab === '统计' && (
          <div className="max-w-3xl space-y-6">
            {pageLoading && <div className="flex items-center justify-center gap-2 py-8 text-text-secondary"><Loader2 className="h-5 w-5 animate-spin" /> 加载统计中...</div>}
            {pageError && <div className="rounded-lg border border-red-300 bg-red-50 p-3 text-sm text-[var(--danger)]">{pageError}</div>}
            {!pageLoading && !pageError && stats && <><div className="grid grid-cols-1 gap-4 sm:grid-cols-3"><Metric label="总错题数" value={stats.total ?? 0} tone="text-accent" /><Metric label="今日待复习" value={stats.due_today ?? 0} tone="text-[var(--danger)]" /><Metric label="错因类型" value={stats.by_type ? Object.keys(stats.by_type).length : 0} tone="text-[var(--success)]" /></div><div className="rounded-xl border border-border bg-bg-card shadow-sm p-4"><h3 className="mb-3 flex items-center gap-2 text-sm font-medium"><TrendingUp className="h-4 w-4 text-accent" /> 薄弱点 TOP 列表</h3><div className="space-y-2">{weakPoints.map((w, i) => <div key={`${w.type}-${w.name}`} className="flex items-center justify-between gap-3 text-sm"><span className="min-w-0 truncate text-text-primary">{i + 1}. <strong>{w.name || '未命名'}</strong><span className="ml-1 text-text-secondary">({w.type || '类型未知'})</span></span><span className="flex-shrink-0 font-medium text-accent">{w.count ?? 0} 次</span></div>)}{weakPoints.length === 0 && <div className="text-sm text-text-secondary">暂无薄弱点数据</div>}</div></div></>}
            {!pageLoading && !pageError && !stats && <div className="py-12 text-center text-text-secondary">暂无统计数据</div>}
          </div>
        )}
      </div>
      {renderCropModal()}
      {renderQuestionEditor()}
    </div>
  );
};

function Range({ label, value, min, max, suffix = '%', onChange }: { label: string; value: number; min: number; max: number; suffix?: string; onChange: (value: number) => void }) {
  return (
    <label className="block space-y-1 text-sm text-text-primary">
      <div className="flex items-center justify-between"><span>{label}</span><span className="text-xs text-text-secondary">{value}{suffix}</span></div>
      <input type="range" min={min} max={max} value={value} onChange={(e) => onChange(Number(e.target.value))} className="w-full accent-accent" />
    </label>
  );
}

function Metric({ label, value, tone }: { label: string; value: number; tone: string }) {
  return <div className="rounded-xl border border-border bg-bg-card shadow-sm p-4 text-center"><div className={`text-2xl font-bold ${tone}`}>{value}</div><div className="mt-1 text-xs text-text-secondary">{label}</div></div>;
}

export default MistakesPage;
