import React, { useEffect, useRef, useState } from 'react';
import { BookOpen, CheckCircle2, FileText, Loader2, Upload, XCircle } from 'lucide-react';
import ScopeSelector from '../components/ScopeSelector';

type ImportJob = {
  id: string;
  status: 'running' | 'completed' | 'failed' | string;
  stage: string;
  progress: number;
  message: string;
  book_name: string;
  subject?: string;
  result?: {
    name: string;
    chapter_count: number;
    used_mineru: boolean;
    indexed_chunks?: number;
    output_dir?: string;
    subject?: string;
  } | null;
};

const stageLabels: Record<string, string> = {
  queued: '排队',
  started: '准备',
  mineru_submit: '提交 MinerU',
  mineru_running: 'MinerU 解析',
  mineru_download: '下载结果',
  extract: '解压结果包',
  structure: '整理结构',
  indexing: '建立索引',
  completed: '完成',
  failed: '失败',
};

const BooksPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [outputFile, setOutputFile] = useState<File | null>(null);
  const [tocPages, setTocPages] = useState('');
  const [subject, setSubject] = useState('');
  const [requireMineru, setRequireMineru] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [job, setJob] = useState<ImportJob | null>(null);
  const [error, setError] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);
  const outputInputRef = useRef<HTMLInputElement>(null);
  const pollRef = useRef<number | null>(null);

  const stopPolling = () => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    pollRef.current = null;
  };

  useEffect(() => () => {
    if (pollRef.current) window.clearInterval(pollRef.current);
  }, []);

  const pollJob = (jobId: string) => {
    stopPolling();
    pollRef.current = window.setInterval(async () => {
      try {
        const res = await fetch(`/api/books/import-jobs/${jobId}`);
        const data = await res.json();
        if (!data.success) throw new Error(data.message || '获取导入进度失败');
        setJob(data.data);
        if (data.data.status === 'completed' || data.data.status === 'failed') {
          stopPolling();
          setUploading(false);
          if (data.data.status === 'completed') window.dispatchEvent(new Event('books:changed'));
        }
      } catch (err) {
        stopPolling();
        setUploading(false);
        setError(err instanceof Error ? err.message : String(err));
      }
    }, 1200);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const nextFile = e.target.files?.[0] || null;
    setFile(nextFile);
    setJob(null);
    setError('');
  };

  const handleOutputFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const nextFile = e.target.files?.[0] || null;
    setOutputFile(nextFile);
    setJob(null);
    setError('');
  };

  const handleUpload = async () => {
    if (!file || uploading) return;
    setUploading(true);
    setError('');
    setJob(null);

    const formData = new FormData();
    formData.append('file', file);
    formData.append('toc_pages', tocPages);
    formData.append('pre_read', 'false');
    formData.append('require_mineru', String(requireMineru));
    formData.append('subject', subject);

    try {
      const res = await fetch('/api/books/import-job', { method: 'POST', body: formData });
      const data = await res.json();
      if (!data.success) throw new Error(data.message || '启动导入失败');
      setJob(data.data);
      pollJob(data.job_id);
    } catch (err) {
      setUploading(false);
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const handleOutputUpload = async () => {
    if (!outputFile || uploading) return;
    setUploading(true);
    setError('');
    setJob(null);

    const formData = new FormData();
    formData.append('file', outputFile);
    formData.append('book_name', outputFile.name.replace(/\.zip$/i, ''));
    formData.append('subject', subject);

    try {
      const res = await fetch('/api/books/import-mineru-output', { method: 'POST', body: formData });
      const data = await res.json();
      if (!data.success) throw new Error(data.message || '启动输出包导入失败');
      setJob(data.data);
      pollJob(data.job_id);
    } catch (err) {
      setUploading(false);
      setError(err instanceof Error ? err.message : String(err));
    }
  };

  const progress = Math.max(0, Math.min(100, job?.progress ?? 0));
  const isDone = job?.status === 'completed';
  const isFailed = job?.status === 'failed';

  return (
    <div className="flex h-full flex-col overflow-y-auto bg-bg-primary p-6">
      <div className="mx-auto w-full max-w-6xl">
        <div className="mb-6 flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg border border-border bg-bg-card">
              <BookOpen className="h-5 w-5 text-accent" />
            </div>
            <div>
              <h2 className="text-base font-semibold text-text-primary">教材导入</h2>
            </div>
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_360px]">
          <div
            onClick={() => inputRef.current?.click()}
            className="flex min-h-[360px] cursor-pointer flex-col items-center justify-center rounded-[18px] border-2 border-dashed border-border bg-bg-card p-8 text-center transition-colors hover:border-accent/60 hover:bg-[var(--accent-softer)]"
          >
            <Upload className="mb-4 h-10 w-10 text-accent" />
            <p className="text-base font-semibold text-text-primary">{file ? file.name : '选择 PDF 教材'}</p>

            <input ref={inputRef} type="file" accept=".pdf,application/pdf" onChange={handleFileChange} className="hidden" />
          </div>

          <div className="space-y-4">
            <section className="rounded-[18px] border border-border bg-bg-card p-4">
              <div className="mb-4 text-sm font-semibold text-text-primary">导入参数</div>
              <label className="block">
                <span className="mb-1.5 block text-xs text-text-secondary">目录页码范围，可选</span>
                <input
                  value={tocPages}
                  onChange={(e) => setTocPages(e.target.value)}
                  placeholder="如 1-5，仅本地降级解析会使用"
                  className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm outline-none focus:border-accent"
                />
              </label>
              <label className="mt-4 block">
                <span className="mb-1.5 block text-xs text-text-secondary">{'\u6240\u5c5e\u79d1\u76ee'}</span>
                <ScopeSelector
                  subject={subject}
                  onSubjectChange={setSubject}
                  bookMode="hidden"
                  label="所属科目"
                  fullWidth
                  width="wide"
                />
              </label>
              <label className="mt-4 flex items-center gap-2 rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm text-text-primary">
                <input type="checkbox" checked={requireMineru} onChange={(e) => setRequireMineru(e.target.checked)} className="accent-accent" />
                必须使用 MinerU
              </label>
            </section>

            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="flex w-full items-center justify-center gap-2 rounded-full bg-accent px-4 py-3 text-sm font-semibold text-white transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
              {uploading ? '导入中' : '开始导入'}
            </button>

            <section className="rounded-[18px] border border-border bg-bg-card p-4">
              <div className="mb-2 text-sm font-semibold text-text-primary">导入 OCR 输出包</div>
              <p className="mb-3 text-xs leading-5 text-text-secondary">上传外部 MinerU 或租用 GPU 产出的 zip，包含 md、content_list/middle JSON 和图片；本机只负责整理章节并建立索引。</p>
              <button type="button" onClick={() => outputInputRef.current?.click()} className="flex w-full items-center justify-center gap-2 rounded-xl border border-dashed border-border bg-bg-primary px-3 py-3 text-sm text-text-primary hover:border-accent">
                <Upload className="h-4 w-4" /> {outputFile ? outputFile.name : '选择输出 zip'}
              </button>
              <input ref={outputInputRef} type="file" accept=".zip,application/zip" onChange={handleOutputFileChange} className="hidden" />
              <button onClick={handleOutputUpload} disabled={!outputFile || uploading} className="mt-3 flex w-full items-center justify-center gap-2 rounded-xl border border-border bg-bg-primary px-4 py-2.5 text-sm font-semibold text-text-primary transition-colors hover:border-accent hover:text-accent disabled:cursor-not-allowed disabled:opacity-50">
                {uploading ? <Loader2 className="h-4 w-4 animate-spin" /> : <FileText className="h-4 w-4" />}
                {uploading ? '导入中' : '导入输出包'}
              </button>
            </section>

            {(job || error) && (
              <section className="rounded-[18px] border border-border bg-bg-card p-4">
                {error ? (
                  <div className="flex items-center gap-2 text-sm text-red-700"><XCircle className="h-4 w-4" />{error}</div>
                ) : job ? (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-semibold text-text-primary">{job.book_name}</div>
                        <div className="mt-1 text-xs leading-5 text-text-secondary">{stageLabels[job.stage] || job.stage} · {job.message}</div>
                      </div>
                      {isDone ? <CheckCircle2 className="h-5 w-5 text-[var(--success)]" /> : isFailed ? <XCircle className="h-5 w-5 text-[var(--danger)]" /> : <Loader2 className="h-5 w-5 animate-spin text-accent" />}
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-bg-primary">
                      <div className="h-full bg-accent transition-all" style={{ width: `${progress}%` }} />
                    </div>
                    <div className="flex justify-between text-xs text-text-secondary">
                      <span>{progress}%</span>
                      {job.result && <span>{job.result.chapter_count} 章 · {job.result.indexed_chunks || 0} 块</span>}
                    </div>
                  </div>
                ) : null}
              </section>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default BooksPage;
