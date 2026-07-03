import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { AlertTriangle, ArrowRightLeft, BookOpen, CheckCircle2, CircleX, Plus, RefreshCw, Save, Trash2, Wrench, X } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { createPortal } from 'react-dom';
import { del, get, patch, post } from '../api/client';
import { useSystemHealth } from '../hooks/useSystemHealth';
import { useChatContext } from '../contexts/ChatContext';
import type { SystemHealthStatus } from '../types';

type SubjectNode = { name: string; children: string[] };
type ManagedBook = { name: string; subject?: string; path?: string; has_pdf?: boolean; chapter_count?: number; size?: number };
type Tab = 'health' | 'version' | 'books' | 'subjects' | 'models';

const statusMeta: Record<SystemHealthStatus, { label: string; icon: typeof CheckCircle2; iconClass: string; className: string }> = {
  healthy: { label: '系统正常', icon: CheckCircle2, iconClass: 'text-[var(--success)]', className: 'border-[#bfd4c6] bg-[#edf6f0] text-[var(--success)]' },
  degraded: { label: '部分降级', icon: AlertTriangle, iconClass: 'text-[var(--warning)]', className: 'border-[#dec98b] bg-[#fff7de] text-[var(--warning)]' },
  error: { label: '系统异常', icon: CircleX, iconClass: 'text-[var(--danger)]', className: 'border-red-300 bg-red-50 text-[var(--danger)]' },
};

const componentLabels: Record<string, string> = { vector_store: '向量检索', mistake_book: '错题库', exercise_bank: '习题库' };
const secretKeys = ['DEEPSEEK_API_KEY', 'MOONSHOT_API_KEY', 'OPENAI_API_KEY'];
const SETTINGS_TABS: Array<{ id: Tab; label: string }> = [
  { id: 'health', label: '服务器健康' },
  { id: 'version', label: '版本更新' },
  { id: 'books', label: '教材管理' },
  { id: 'subjects', label: '学科管理' },
  { id: 'models', label: '模型配置' },
];

function subjectPath(parent?: string, child?: string) {
  const p = (parent || '').trim();
  const c = (child || '').trim();
  if (!p) return c;
  return c ? `${p}/${c}` : p;
}

function bookBelongsTo(book: ManagedBook, parent: string, child = '') {
  const value = (book.subject || '').trim();
  if (!parent) return !value;
  if (child) return value === subjectPath(parent, child) || value === child;
  return value === parent || value.startsWith(`${parent}/`);
}

const SystemHealth: React.FC<{ bookName?: string }> = ({ bookName = '' }) => {
  const { health, loading, loadHealth } = useSystemHealth(bookName);
  const { setBookName, setSubject } = useChatContext();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>('health');
  const [version, setVersion] = useState<any>(null);
  const [settings, setSettings] = useState<any>(null);
  const [subjects, setSubjects] = useState<SubjectNode[]>([]);
  const [books, setBooks] = useState<ManagedBook[]>([]);
  const [bookDrafts, setBookDrafts] = useState<Record<string, string>>({});
  const [envDraft, setEnvDraft] = useState<Record<string, string>>({});
  const [desktopUpdate, setDesktopUpdate] = useState<any>(null);
  const [message, setMessage] = useState('');
  const [selectedSubjectIndex, setSelectedSubjectIndex] = useState(0);
  const [selectedChildIndex, setSelectedChildIndex] = useState<number | null>(null);

  const loadSettings = useCallback(async () => {
    const res = await get('/system/settings', 20000);
    if (!res?.success) return;
    setSettings(res.data);
    setSubjects(res.data.subjects || []);
    const env = res.data.env || {};
    setEnvDraft({
      LLM_BACKEND: env.LLM_BACKEND?.value || 'deepseek',
      DEEPSEEK_API_BASE: env.DEEPSEEK_API_BASE?.value || 'https://api.deepseek.com/v1',
      DEEPSEEK_MODEL_NAME: env.DEEPSEEK_MODEL_NAME?.value || 'deepseek-v4-pro',
      MOONSHOT_API_BASE: env.MOONSHOT_API_BASE?.value || 'https://api.moonshot.cn/v1',
      KIMI_VISION_MODEL: env.KIMI_VISION_MODEL?.value || 'kimi-k2.5',
      OPENAI_API_BASE: env.OPENAI_API_BASE?.value || 'https://api.openai.com/v1',
      LLM_MODEL_NAME: env.LLM_MODEL_NAME?.value || '',
      MINERU_API_URL: env.MINERU_API_URL?.value || '',
      MINERU_CLI_COMMAND: env.MINERU_CLI_COMMAND?.value || '',
      DEEPSEEK_API_KEY: '',
      MOONSHOT_API_KEY: '',
      OPENAI_API_KEY: '',
    });
  }, []);

  const loadVersion = useCallback(async () => {
    const res = await get('/system/version', 15000);
    if (res?.success) setVersion(res.data);
  }, []);

  const loadBooks = useCallback(async () => {
    const res = await get('/books/list', 20000);
    if (!res?.success) return;
    const nextBooks: ManagedBook[] = res.data || [];
    setBooks(nextBooks);
    setBookDrafts(Object.fromEntries(nextBooks.map((book) => [book.name, book.subject || ''])));
  }, []);

  useEffect(() => {
    if (!open) return;
    loadSettings().catch(() => setMessage('设置加载失败'));
    loadVersion().catch(() => undefined);
    loadBooks().catch(() => undefined);
  }, [open, loadSettings, loadVersion, loadBooks]);

  useEffect(() => {
    if (!open || !window.kaoyanDesktop?.getUpdateStatus) return;
    let mounted = true;
    window.kaoyanDesktop.getUpdateStatus().then((status) => { if (mounted) setDesktopUpdate(status); }).catch(() => undefined);
    const unsubscribe = window.kaoyanDesktop.onUpdateStatus?.((status) => setDesktopUpdate(status));
    return () => {
      mounted = false;
      unsubscribe?.();
    };
  }, [open]);

  useEffect(() => {
    if (!subjects.length) {
      setSelectedSubjectIndex(0);
      setSelectedChildIndex(null);
      return;
    }
    if (selectedSubjectIndex >= subjects.length) {
      setSelectedSubjectIndex(Math.max(0, subjects.length - 1));
      setSelectedChildIndex(null);
      return;
    }
    const childCount = subjects[selectedSubjectIndex]?.children?.length || 0;
    if (selectedChildIndex !== null && selectedChildIndex >= childCount) setSelectedChildIndex(null);
  }, [subjects, selectedSubjectIndex, selectedChildIndex]);

  const status = health?.status || 'degraded';
  const meta = statusMeta[status];
  const StatusIcon = meta.icon;
  const selectedSubject = subjects[selectedSubjectIndex] || null;
  const selectedChild = selectedSubject && selectedChildIndex !== null ? selectedSubject.children[selectedChildIndex] || '' : '';
  const targetSubject = subjectPath(selectedSubject?.name, selectedChild);

  const booksAtTarget = useMemo(() => books.filter((book) => selectedSubject && bookBelongsTo(book, selectedSubject.name, selectedChild)), [books, selectedSubject, selectedChild]);
  const otherBooks = useMemo(() => books.filter((book) => !booksAtTarget.some((item) => item.name === book.name)), [books, booksAtTarget]);

  const saveEnv = async () => {
    setMessage('');
    const payload: Record<string, string> = {};
    for (const [key, value] of Object.entries(envDraft)) {
      if (secretKeys.includes(key) && !value.trim()) continue;
      payload[key] = value;
    }
    const res = await post('/system/settings/env', payload, 20000);
    setMessage(res?.message || (res?.success ? '已保存' : '保存失败'));
    if (res?.success) await loadSettings();
  };

  const saveSubjects = async (next = subjects) => {
    setMessage('');
    const cleaned = next
      .map((item) => ({ name: item.name.trim(), children: item.children.map((child) => child.trim()).filter(Boolean) }))
      .filter((item) => item.name);
    const res = await post('/system/settings/subjects', { subjects: cleaned }, 20000);
    setMessage(res?.message || (res?.success ? '已保存学科' : '学科保存失败'));
    if (res?.success) setSubjects(res.data || cleaned);
  };

  const addSubject = () => {
    const nextIndex = subjects.length;
    setSubjects((prev) => [...prev, { name: `新学科 ${nextIndex + 1}`, children: [] }]);
    setSelectedSubjectIndex(nextIndex);
    setSelectedChildIndex(null);
  };

  const addChild = () => {
    if (!selectedSubject) return;
    const childIndex = selectedSubject.children.length;
    setSubjects((prev) => prev.map((item, index) => index === selectedSubjectIndex ? { ...item, children: [...item.children, `新科目 ${childIndex + 1}`] } : item));
    setSelectedChildIndex(childIndex);
  };

  const updateSubjectName = (index: number, name: string) => setSubjects((prev) => prev.map((item, i) => i === index ? { ...item, name } : item));
  const updateChildName = (childIndex: number, name: string) => setSubjects((prev) => prev.map((item, i) => i === selectedSubjectIndex ? { ...item, children: item.children.map((child, ci) => ci === childIndex ? name : child) } : item));

  const deleteSubject = (index: number) => {
    if (!window.confirm('删除学科只会移除分类建议，不会删除教材文件、向量库或学习记录。继续吗？')) return;
    setSubjects((prev) => prev.filter((_, i) => i !== index));
    setSelectedSubjectIndex(0);
    setSelectedChildIndex(null);
  };

  const deleteChild = (childIndex: number) => {
    if (!window.confirm('删除二级科目只会移除分类建议，不会删除教材文件、向量库或学习记录。继续吗？')) return;
    setSubjects((prev) => prev.map((item, index) => index === selectedSubjectIndex ? { ...item, children: item.children.filter((_, i) => i !== childIndex) } : item));
    setSelectedChildIndex(null);
  };

  const saveBookSubject = async (name: string, overrideSubject?: string) => {
    setMessage('');
    const nextSubject = overrideSubject ?? bookDrafts[name] ?? '';
    const res = await patch(`/books/${encodeURIComponent(name)}`, { subject: nextSubject }, 20000);
    setMessage(res?.message || (res?.success ? '教材学科已保存' : '教材保存失败'));
    if (res?.success) {
      await loadBooks();
      window.dispatchEvent(new Event('books:changed'));
    }
  };

  const moveBookToTarget = async (name: string) => {
    if (!targetSubject) {
      setMessage('请先选择一个一级学科或二级科目。');
      return;
    }
    await saveBookSubject(name, targetSubject);
  };

  const deleteManagedBook = async (name: string) => {
    if (!window.confirm('这会把教材从管理列表隐藏，但不会删除本地文件、章节索引、向量库或学习记录。继续吗？')) return;
    setMessage('');
    const res = await del(`/books/${encodeURIComponent(name)}`, 20000);
    setMessage(res?.message || (res?.success ? '教材已隐藏' : '教材删除失败'));
    if (res?.success) {
      await loadBooks();
      window.dispatchEvent(new Event('books:changed'));
    }
  };

  const switchManagedBook = async (name: string) => {
    setMessage('');
    const res = await get(`/books/switch/${encodeURIComponent(name)}`, 20000);
    if (!res?.success) {
      setMessage(res?.message || '切换教材失败');
      return;
    }
    setBookName(res.data?.name || name);
    if (res.data?.subject) setSubject(res.data.subject);
    setMessage('已设为当前对话教材');
  };

  const openBookImport = () => {
    setOpen(false);
    navigate('/books');
  };

  const reloadVectorStore = async () => {
    setMessage('正在重载向量库...');
    const res = await post('/system/vector-store/reload', {}, 90000);
    setMessage(res?.message || (res?.success ? '向量库已重载' : '向量库重载失败'));
    await loadHealth();
  };

  const updateApp = async () => {
    setMessage('');
    if (window.kaoyanDesktop?.checkForUpdates) {
      const res = await window.kaoyanDesktop.checkForUpdates();
      setDesktopUpdate(res);
      setMessage(res?.message || '更新检查完成');
      return;
    }
    const res = await post('/system/update', {}, 60000);
    setMessage(res?.message || '更新检查完成');
  };

  const downloadUpdate = async () => {
    setMessage('');
    const res = await window.kaoyanDesktop?.downloadUpdate?.();
    if (res) {
      setDesktopUpdate(res);
      setMessage(res.message || '开始下载更新');
    }
  };

  const installUpdate = async () => {
    setMessage('');
    const res = await window.kaoyanDesktop?.installUpdate?.();
    if (res) {
      setDesktopUpdate(res);
      setMessage(res.message || '正在安装更新');
    }
  };
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className={`inline-flex h-8 w-8 items-center justify-center rounded-lg border transition-colors ${meta.className}`} aria-label="设置" title="设置">
        {loading && !health ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Wrench className="h-4 w-4" />}
      </button>

      {open && createPortal(
        <div className="fixed inset-0 z-[1200] flex items-center justify-center bg-black/35 p-4">
          <div className="flex max-h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-border bg-bg-primary">
            <div className="flex items-center justify-between border-b border-border bg-bg-card px-5 py-4">
              <div className="flex items-center gap-2 text-base font-semibold text-text-primary"><Wrench className="h-5 w-5 text-accent" />设置</div>
              <button onClick={() => setOpen(false)} className="rounded-lg p-1 text-text-secondary hover:bg-bg-secondary hover:text-text-primary"><X className="h-5 w-5" /></button>
            </div>
            <div className="grid min-h-0 flex-1 grid-cols-[180px_minmax(0,1fr)]">
              <SettingsSidebar tab={tab} onTabChange={setTab} />
              <main className="min-h-0 overflow-y-auto p-5">
                {message && <div className="mb-4 rounded-lg border border-border bg-bg-card px-3 py-2 text-sm text-text-secondary">{message}</div>}

                {tab === 'health' && (
                  <section className="space-y-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm font-medium text-text-primary"><StatusIcon className={`h-4 w-4 ${meta.iconClass}`} />{meta.label}</div>
                      <button onClick={loadHealth} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-sm hover:border-accent"><RefreshCw className={`h-4 w-4 ${loading ? 'animate-spin' : ''}`} />重新检查</button>
                    </div>
                    <div className="grid gap-3 md:grid-cols-3">
                      {health && Object.entries(health.components).map(([key, item]) => {
                        const itemMeta = statusMeta[item.status] || statusMeta.degraded;
                        const ItemIcon = itemMeta.icon;
                        return (
                          <div key={key} className="rounded-xl border border-border bg-bg-card p-4">
                            <ItemIcon className={`mb-2 h-5 w-5 ${itemMeta.iconClass}`} />
                            <div className="text-sm font-medium text-text-primary">{componentLabels[key] || '后端服务'}</div>
                            <div className="mt-1 text-xs leading-5 text-text-secondary">{item.message}</div>
                            {key === 'vector_store' && (
                              <button type="button" onClick={reloadVectorStore} className="mt-3 inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary hover:border-accent hover:text-text-primary">
                                <RefreshCw className="h-3.5 w-3.5" />重载向量库
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </section>
                )}

                {tab === 'version' && (
                  <section className="space-y-4">
                    <div className="rounded-xl border border-border bg-bg-card p-4 text-sm text-text-primary">
                      <div>当前版本：{desktopUpdate?.currentVersion || version?.version || '未知'}</div>
                      <div className="mt-2 text-text-secondary">分支：{version?.branch || '未知'} / 提交：{version?.commit || '未知'}</div>
                      <div className="mt-2 text-xs text-text-secondary">{desktopUpdate?.message || version?.message || '正在读取版本信息...'}</div>
                    </div>
                    {desktopUpdate?.updateInfo?.version && <div className="rounded-xl border border-[#bfd4c6] bg-[#edf6f0] p-4 text-sm text-[var(--success)]">可更新到：{desktopUpdate.updateInfo.version}</div>}
                    {desktopUpdate?.status === 'downloading' && (
                      <div className="rounded-xl border border-border bg-bg-card p-4">
                        <div className="mb-2 flex justify-between text-xs text-text-secondary"><span>下载进度</span><span>{Math.round(desktopUpdate?.progress?.percent || 0)}%</span></div>
                        <div className="h-2 overflow-hidden rounded-full bg-bg-secondary"><div className="h-full rounded-full bg-accent" style={{ width: `${Math.round(desktopUpdate?.progress?.percent || 0)}%` }} /></div>
                      </div>
                    )}
                    <div className="flex flex-wrap gap-2">
                      <button onClick={loadVersion} className="rounded-lg border border-border px-3 py-2 text-sm hover:border-accent">读取版本</button>
                      <button onClick={updateApp} className="rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover">检查更新</button>
                      {desktopUpdate?.status === 'available' && <button onClick={downloadUpdate} className="rounded-lg border border-border px-3 py-2 text-sm hover:border-accent">下载更新</button>}
                      {desktopUpdate?.status === 'downloaded' && <button onClick={installUpdate} className="rounded-lg border border-border px-3 py-2 text-sm hover:border-accent">重启安装</button>}
                    </div>
                  </section>
                )}

                {tab === 'books' && (
                  <section className="space-y-4">
                    <div className="rounded-lg border border-border bg-bg-card p-3 text-xs leading-5 text-text-secondary">
                      教材归属也可以在“学科管理”的三列视图里调整。这里保留快速编辑入口；隐藏教材不会删除本地文件、章节索引、向量库或学习记录。
                    </div>
                    <div className="space-y-3">
                      {books.map((book) => (
                        <BookManageRow
                          key={book.name}
                          book={book}
                          draftSubject={bookDrafts[book.name] || ''}
                          onDraftSubject={(value) => setBookDrafts((prev) => ({ ...prev, [book.name]: value }))}
                          onSave={() => saveBookSubject(book.name)}
                          onSwitch={() => switchManagedBook(book.name)}
                          onDelete={() => deleteManagedBook(book.name)}
                        />
                      ))}
                      {books.length === 0 && <div className="rounded-xl border border-dashed border-border py-10 text-center text-sm text-text-secondary">暂无教材，请先到教材导入页添加。</div>}
                    </div>
                  </section>
                )}

                {tab === 'subjects' && (
                  <section className="space-y-4">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="text-sm text-text-secondary">管理一级学科、二级科目和教材归属。教材移动只更新分类元数据，不改名、不搬文件、不删除学习历史。</div>
                      <div className="flex flex-wrap gap-2">
                        <button onClick={addSubject} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-sm hover:border-accent"><Plus className="h-4 w-4" />一级学科</button>
                        <button onClick={openBookImport} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-sm hover:border-accent"><BookOpen className="h-4 w-4" />添加教材</button>
                        <button onClick={() => saveSubjects()} className="inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-hover"><Save className="h-4 w-4" />保存学科</button>
                      </div>
                    </div>

                    <div className="grid min-h-[470px] gap-3 lg:grid-cols-[minmax(190px,0.75fr)_minmax(210px,0.85fr)_minmax(360px,1.4fr)]">
                      <section className="rounded-xl border border-border bg-bg-card p-3">
                        <ColumnTitle title="一级学科" count={subjects.length} />
                        <div className="mt-3 space-y-2">
                          {subjects.map((item, index) => (
                            <div key={`${item.name}-${index}`} className={`rounded-lg border p-2 ${selectedSubjectIndex === index ? 'border-accent/45 bg-[var(--accent-soft)]' : 'border-border bg-bg-primary'}`}>
                              <button type="button" onClick={() => { setSelectedSubjectIndex(index); setSelectedChildIndex(null); }} className="mb-2 w-full text-left text-xs font-medium text-text-secondary">选择</button>
                              <div className="flex gap-2">
                                <input value={item.name} onChange={(e) => updateSubjectName(index, e.target.value)} className="min-w-0 flex-1 rounded-lg border border-border bg-bg-card px-2 py-1.5 text-sm outline-none focus:border-accent" />
                                <button onClick={() => deleteSubject(index)} className="rounded-lg border border-border px-2 text-[var(--danger)] hover:border-red-300" title="删除一级学科"><Trash2 className="h-4 w-4" /></button>
                              </div>
                            </div>
                          ))}
                          {subjects.length === 0 && <EmptyHint text="还没有学科，先添加一个一级学科。" />}
                        </div>
                      </section>

                      <section className="rounded-xl border border-border bg-bg-card p-3">
                        <div className="flex items-center justify-between gap-2">
                          <ColumnTitle title="二级科目" count={selectedSubject?.children?.length || 0} />
                          <button onClick={addChild} disabled={!selectedSubject} className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-xs text-text-secondary hover:border-accent hover:text-text-primary disabled:opacity-50"><Plus className="h-3.5 w-3.5" />添加</button>
                        </div>
                        <div className="mt-3 space-y-2">
                          {selectedSubject && (
                            <button type="button" onClick={() => setSelectedChildIndex(null)} className={`w-full rounded-lg border px-3 py-2 text-left text-sm ${selectedChildIndex === null ? 'border-accent/45 bg-[var(--accent-soft)] text-accent' : 'border-border bg-bg-primary text-text-primary hover:border-accent/35'}`}>
                              全部{selectedSubject.name}
                              <span className="mt-1 block text-xs text-text-secondary">显示该一级学科下的全部教材</span>
                            </button>
                          )}
                          {selectedSubject?.children.map((child, childIndex) => (
                            <div key={`${child}-${childIndex}`} className={`rounded-lg border p-2 ${selectedChildIndex === childIndex ? 'border-accent/45 bg-[var(--accent-soft)]' : 'border-border bg-bg-primary'}`}>
                              <button type="button" onClick={() => setSelectedChildIndex(childIndex)} className="mb-2 w-full text-left text-xs font-medium text-text-secondary">选择</button>
                              <div className="flex gap-2">
                                <input value={child} onChange={(e) => updateChildName(childIndex, e.target.value)} className="min-w-0 flex-1 rounded-lg border border-border bg-bg-card px-2 py-1.5 text-sm outline-none focus:border-accent" />
                                <button onClick={() => deleteChild(childIndex)} className="rounded-lg border border-border px-2 text-[var(--danger)] hover:border-red-300" title="删除二级科目"><Trash2 className="h-4 w-4" /></button>
                              </div>
                            </div>
                          ))}
                          {!selectedSubject && <EmptyHint text="先选择或添加一级学科。" />}
                        </div>
                      </section>

                      <section className="rounded-xl border border-border bg-bg-card p-3">
                        <div className="flex items-start justify-between gap-2">
                          <div>
                            <ColumnTitle title="教材" count={booksAtTarget.length} />
                            <div className="mt-1 text-xs text-text-secondary">当前位置：{targetSubject || '未选择'}</div>
                          </div>
                          <button onClick={loadBooks} className="inline-flex items-center gap-1 rounded-lg border border-border px-2.5 py-1.5 text-xs text-text-secondary hover:border-accent hover:text-text-primary"><RefreshCw className="h-3.5 w-3.5" />刷新</button>
                        </div>
                        <div className="mt-3 space-y-2">
                          {booksAtTarget.map((book) => (
                            <BookPlacementRow key={book.name} book={book} active onSwitch={() => switchManagedBook(book.name)} onMove={() => moveBookToTarget(book.name)} onDelete={() => deleteManagedBook(book.name)} />
                          ))}
                          {booksAtTarget.length === 0 && <EmptyHint text="当前位置还没有教材。可以从下方其他教材移动过来。" />}
                        </div>
                        <div className="mt-4 border-t border-border pt-3">
                          <div className="mb-2 text-xs font-medium text-text-secondary">其他教材</div>
                          <div className="space-y-2">
                            {otherBooks.map((book) => (
                              <BookPlacementRow key={book.name} book={book} active={false} onSwitch={() => switchManagedBook(book.name)} onMove={() => moveBookToTarget(book.name)} onDelete={() => deleteManagedBook(book.name)} />
                            ))}
                            {otherBooks.length === 0 && <div className="text-xs text-text-secondary">没有其他教材。</div>}
                          </div>
                        </div>
                      </section>
                    </div>
                  </section>
                )}

                {tab === 'models' && (
                  <section className="space-y-4">
                    <div className="rounded-lg border border-border bg-bg-card p-3 text-xs leading-5 text-text-secondary">API Key 只写入本地 .env；界面只显示是否已配置，不回显密钥。保存后新请求会读取新配置，已有长任务可能需要重启后端。</div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <Field label="推理后端"><select value={envDraft.LLM_BACKEND || 'deepseek'} onChange={(e) => setEnvDraft({ ...envDraft, LLM_BACKEND: e.target.value })} className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm"><option value="deepseek">DeepSeek</option><option value="moonshot">Moonshot/Kimi</option><option value="openai">OpenAI</option><option value="ollama">Ollama</option></select></Field>
                      <Field label="DeepSeek 模型"><input value={envDraft.DEEPSEEK_MODEL_NAME || ''} onChange={(e) => setEnvDraft({ ...envDraft, DEEPSEEK_MODEL_NAME: e.target.value })} className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label={`DeepSeek API Key（${settings?.env?.DEEPSEEK_API_KEY?.configured ? '已配置' : '未配置'}）`}><input type="password" value={envDraft.DEEPSEEK_API_KEY || ''} onChange={(e) => setEnvDraft({ ...envDraft, DEEPSEEK_API_KEY: e.target.value })} placeholder="留空则不修改" className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label="DeepSeek Base URL"><input value={envDraft.DEEPSEEK_API_BASE || ''} onChange={(e) => setEnvDraft({ ...envDraft, DEEPSEEK_API_BASE: e.target.value })} className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label={`OCR/Kimi API Key（${settings?.env?.MOONSHOT_API_KEY?.configured ? '已配置' : '未配置'}）`}><input type="password" value={envDraft.MOONSHOT_API_KEY || ''} onChange={(e) => setEnvDraft({ ...envDraft, MOONSHOT_API_KEY: e.target.value })} placeholder="留空则不修改" className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label="OCR/Kimi 模型"><input value={envDraft.KIMI_VISION_MODEL || ''} onChange={(e) => setEnvDraft({ ...envDraft, KIMI_VISION_MODEL: e.target.value })} className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label="MinerU API URL（推荐外部服务）"><input value={envDraft.MINERU_API_URL || ''} onChange={(e) => setEnvDraft({ ...envDraft, MINERU_API_URL: e.target.value })} placeholder="Example: http://gpu-host:8000" className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label="本地 MinerU CLI（高级，可选）"><input value={envDraft.MINERU_CLI_COMMAND || ''} onChange={(e) => setEnvDraft({ ...envDraft, MINERU_CLI_COMMAND: e.target.value })} placeholder="Example: mineru -p {input} -o {output}" className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label={`OpenAI API Key（${settings?.env?.OPENAI_API_KEY?.configured ? '已配置' : '未配置'}）`}><input type="password" value={envDraft.OPENAI_API_KEY || ''} onChange={(e) => setEnvDraft({ ...envDraft, OPENAI_API_KEY: e.target.value })} placeholder="留空则不修改" className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label="通用模型名"><input value={envDraft.LLM_MODEL_NAME || ''} onChange={(e) => setEnvDraft({ ...envDraft, LLM_MODEL_NAME: e.target.value })} className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                    </div>
                    <button onClick={saveEnv} className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"><Save className="h-4 w-4" />保存模型配置</button>
                  </section>
                )}
              </main>
            </div>
          </div>
        </div>,
        document.body,
      )}
    </>
  );
};

const SettingsSidebar = ({ tab, onTabChange }: { tab: Tab; onTabChange: (tab: Tab) => void }) => (
  <aside className="border-r border-border bg-bg-secondary/80 p-3">
    {SETTINGS_TABS.map((item) => (
      <button key={item.id} onClick={() => onTabChange(item.id)} className={`mb-1 w-full rounded-lg px-3 py-2 text-left text-sm ${tab === item.id ? 'bg-[var(--accent-soft)] text-accent' : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'}`}>
        {item.label}
      </button>
    ))}
  </aside>
);

const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <label className="block space-y-1.5 text-sm text-text-primary"><span className="text-xs font-medium text-text-secondary">{label}</span>{children}</label>
);

const ColumnTitle = ({ title, count }: { title: string; count: number }) => (
  <div className="flex items-center justify-between gap-2">
    <div className="text-sm font-semibold text-text-primary">{title}</div>
    <span className="rounded-md border border-border bg-bg-primary px-1.5 py-0.5 text-[11px] text-text-secondary">{count}</span>
  </div>
);

const EmptyHint = ({ text }: { text: string }) => (
  <div className="rounded-lg border border-dashed border-border bg-bg-primary px-3 py-4 text-center text-xs text-text-secondary">{text}</div>
);

const BookMeta = ({ book }: { book: ManagedBook }) => (
  <div className="mt-1 space-y-0.5 text-[11px] leading-5 text-text-secondary">
    <div>{book.has_pdf ? 'PDF' : 'OCR/Markdown'} · {book.chapter_count || 0} 章 · {book.subject || '未分类'}</div>
    {book.path && <div className="truncate">{book.path}</div>}
  </div>
);

const BookManageRow = ({ book, draftSubject, onDraftSubject, onSave, onSwitch, onDelete }: { book: ManagedBook; draftSubject: string; onDraftSubject: (value: string) => void; onSave: () => void; onSwitch: () => void; onDelete: () => void }) => (
  <div className="rounded-xl border border-border bg-bg-card p-4">
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-sm font-medium text-text-primary"><BookOpen className="h-4 w-4 text-accent" /> <span className="truncate">{book.name}</span></div>
        <BookMeta book={book} />
      </div>
      <div className="flex flex-wrap gap-2">
        <button onClick={onSwitch} className="rounded-lg border border-border px-3 py-1.5 text-xs text-text-secondary hover:border-accent hover:text-text-primary">设为当前</button>
        <button onClick={onDelete} className="rounded-lg border border-red-200 px-3 py-1.5 text-xs text-[var(--danger)] hover:border-red-300">隐藏</button>
      </div>
    </div>
    <div className="mt-3 flex flex-col gap-2 sm:flex-row">
      <Field label="所属学科（例：数学/高数）">
        <input value={draftSubject} onChange={(e) => onDraftSubject(e.target.value)} className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" />
      </Field>
      <button onClick={onSave} className="inline-flex items-center justify-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover sm:self-end"><Save className="h-4 w-4" />保存</button>
    </div>
  </div>
);

const BookPlacementRow = ({ book, active, onSwitch, onMove, onDelete }: { book: ManagedBook; active: boolean; onSwitch: () => void; onMove: () => void; onDelete: () => void }) => (
  <div className={`rounded-lg border p-3 ${active ? 'border-accent/25 bg-[var(--accent-softer)]' : 'border-border bg-bg-primary'}`}>
    <div className="flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="flex items-center gap-2 text-sm font-medium text-text-primary"><BookOpen className="h-4 w-4 text-accent" /><span className="truncate">{book.name}</span></div>
        <BookMeta book={book} />
      </div>
      <div className="flex flex-shrink-0 flex-wrap justify-end gap-1.5">
        {!active && <button onClick={onMove} className="inline-flex items-center gap-1 rounded-lg border border-border bg-bg-card px-2 py-1.5 text-xs text-text-secondary hover:border-accent hover:text-text-primary"><ArrowRightLeft className="h-3.5 w-3.5" />移动</button>}
        <button onClick={onSwitch} className="rounded-lg border border-border bg-bg-card px-2 py-1.5 text-xs text-text-secondary hover:border-accent hover:text-text-primary">当前</button>
        <button onClick={onDelete} className="rounded-lg border border-red-200 bg-bg-card px-2 py-1.5 text-xs text-[var(--danger)] hover:border-red-300"><Trash2 className="h-3.5 w-3.5" /></button>
      </div>
    </div>
  </div>
);

export default SystemHealth;
