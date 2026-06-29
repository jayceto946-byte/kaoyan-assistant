import React, { useCallback, useEffect, useRef, useState } from 'react';
import { AlertTriangle, CheckCircle2, CircleX, Plus, RefreshCw, Save, Trash2, Wrench, X } from 'lucide-react';
import { get, post } from '../api/client';
import type { SystemHealthResponse, SystemHealthStatus } from '../types';

type SubjectNode = { name: string; children: string[] };
type Tab = 'health' | 'version' | 'subjects' | 'models';

const statusMeta: Record<SystemHealthStatus, { label: string; icon: typeof CheckCircle2; iconClass: string; className: string }> = {
  healthy: { label: '系统正常', icon: CheckCircle2, iconClass: 'text-[var(--success)]', className: 'border-[#bfd4c6] bg-[#edf6f0] text-[var(--success)]' },
  degraded: { label: '部分降级', icon: AlertTriangle, iconClass: 'text-[var(--warning)]', className: 'border-[#dec98b] bg-[#fff7de] text-[var(--warning)]' },
  error: { label: '系统异常', icon: CircleX, iconClass: 'text-[var(--danger)]', className: 'border-red-300 bg-red-50 text-[var(--danger)]' },
};

const componentLabels: Record<string, string> = { vector_store: '向量检索', mistake_book: '错题库', exercise_bank: '习题库' };
const secretKeys = ['DEEPSEEK_API_KEY', 'MOONSHOT_API_KEY', 'OPENAI_API_KEY'];

const SystemHealth: React.FC<{ bookName?: string }> = ({ bookName = '' }) => {
  const [health, setHealth] = useState<SystemHealthResponse | null>(null);
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState<Tab>('health');
  const [loading, setLoading] = useState(false);
  const [version, setVersion] = useState<any>(null);
  const [settings, setSettings] = useState<any>(null);
  const [subjects, setSubjects] = useState<SubjectNode[]>([]);
  const [envDraft, setEnvDraft] = useState<Record<string, string>>({});
  const [desktopUpdate, setDesktopUpdate] = useState<any>(null);
  const [message, setMessage] = useState('');
  const requestId = useRef(0);

  const loadHealth = useCallback(async () => {
    const currentRequest = ++requestId.current;
    setLoading(true);
    try {
      const query = bookName ? `?book_name=${encodeURIComponent(bookName)}` : '';
      const nextHealth = await get(`/system/health${query}`, 45000);
      if (currentRequest === requestId.current) setHealth(nextHealth);
    } catch {
      if (currentRequest === requestId.current) {
        setHealth({ status: 'error', book_name: bookName, components: { backend: { status: 'error', message: '无法连接后端健康检查', details: {} } } });
      }
    } finally {
      if (currentRequest === requestId.current) setLoading(false);
    }
  }, [bookName]);

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
      DEEPSEEK_API_KEY: '',
      MOONSHOT_API_KEY: '',
      OPENAI_API_KEY: '',
    });
  }, []);

  const loadVersion = useCallback(async () => {
    const res = await get('/system/version', 15000);
    if (res?.success) setVersion(res.data);
  }, []);

  useEffect(() => {
    loadHealth();
    const timer = window.setInterval(loadHealth, 30_000);
    return () => window.clearInterval(timer);
  }, [loadHealth]);

  useEffect(() => {
    if (!open) return;
    loadSettings().catch(() => setMessage('设置加载失败'));
    loadVersion().catch(() => undefined);
  }, [open, loadSettings, loadVersion]);

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

  const status = health?.status || 'degraded';
  const meta = statusMeta[status];
  const StatusIcon = meta.icon;

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
    const res = await post('/system/settings/subjects', { subjects: next }, 20000);
    setMessage(res?.message || (res?.success ? '已保存' : '保存失败'));
    if (res?.success) setSubjects(res.data || next);
  };

  const addSubject = () => setSubjects((prev) => [...prev, { name: '新学科', children: [] }]);
  const addChild = (index: number) => setSubjects((prev) => prev.map((item, i) => i === index ? { ...item, children: [...item.children, '新子科目'] } : item));
  const updateSubjectName = (index: number, name: string) => setSubjects((prev) => prev.map((item, i) => i === index ? { ...item, name } : item));
  const updateChildName = (index: number, childIndex: number, name: string) => setSubjects((prev) => prev.map((item, i) => i === index ? { ...item, children: item.children.map((child, ci) => ci === childIndex ? name : child) } : item));
  const deleteSubject = (index: number) => setSubjects((prev) => prev.filter((_, i) => i !== index));
  const deleteChild = (index: number, childIndex: number) => setSubjects((prev) => prev.map((item, i) => i === index ? { ...item, children: item.children.filter((_, ci) => ci !== childIndex) } : item));

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
      <button type="button" onClick={() => setOpen(true)} className={`inline-flex h-8 w-8 items-center justify-center rounded-lg border shadow-sm transition-colors ${meta.className}`} aria-label="设置" title="设置">
        {loading && !health ? <RefreshCw className="h-4 w-4 animate-spin" /> : <Wrench className="h-4 w-4" />}
      </button>

      {open && (
        <div className="fixed inset-0 z-[1200] flex items-center justify-center bg-black/35 p-4">
          <div className="flex max-h-[88vh] w-full max-w-5xl flex-col overflow-hidden rounded-xl border border-border bg-bg-primary shadow-2xl">
            <div className="flex items-center justify-between border-b border-border bg-bg-card px-5 py-4">
              <div className="flex items-center gap-2 text-base font-semibold text-text-primary"><Wrench className="h-5 w-5 text-accent" />设置</div>
              <button onClick={() => setOpen(false)} className="rounded-lg p-1 text-text-secondary hover:bg-bg-secondary hover:text-text-primary"><X className="h-5 w-5" /></button>
            </div>
            <div className="grid min-h-0 flex-1 grid-cols-[180px_minmax(0,1fr)]">
              <aside className="border-r border-border bg-bg-secondary/80 p-3">
                {(['health', 'version', 'subjects', 'models'] as Tab[]).map((item) => (
                  <button key={item} onClick={() => setTab(item)} className={`mb-1 w-full rounded-lg px-3 py-2 text-left text-sm ${tab === item ? 'bg-[var(--accent-soft)] text-accent' : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'}`}>
                    {item === 'health' ? '服务器健康' : item === 'version' ? '版本更新' : item === 'subjects' ? '学科管理' : '模型配置'}
                  </button>
                ))}
              </aside>
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
                        const itemMeta = statusMeta[item.status];
                        const ItemIcon = itemMeta.icon;
                        return <div key={key} className="rounded-xl border border-border bg-bg-card p-4"><ItemIcon className={`mb-2 h-5 w-5 ${itemMeta.iconClass}`} /><div className="text-sm font-medium text-text-primary">{componentLabels[key] || '后端服务'}</div><div className="mt-1 text-xs leading-5 text-text-secondary">{item.message}</div></div>;
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

                {tab === 'subjects' && (
                  <section className="space-y-4">
                    <div className="flex justify-between gap-3"><div className="text-sm text-text-secondary">管理一级学科与二级科目，输入框会把这些作为建议。</div><button onClick={addSubject} className="inline-flex items-center gap-2 rounded-lg border border-border px-3 py-1.5 text-sm hover:border-accent"><Plus className="h-4 w-4" />一级学科</button></div>
                    <div className="space-y-3">
                      {subjects.map((item, index) => (
                        <div key={`${item.name}-${index}`} className="rounded-xl border border-border bg-bg-card p-4">
                          <div className="flex gap-2"><input value={item.name} onChange={(e) => updateSubjectName(index, e.target.value)} className="flex-1 rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm outline-none focus:border-accent" /><button onClick={() => addChild(index)} className="rounded-lg border border-border px-3 text-sm hover:border-accent">加二级</button><button onClick={() => deleteSubject(index)} className="rounded-lg border border-border px-2 text-[var(--danger)] hover:border-red-300"><Trash2 className="h-4 w-4" /></button></div>
                          <div className="mt-3 grid gap-2 md:grid-cols-2">
                            {item.children.map((child, childIndex) => <div key={`${child}-${childIndex}`} className="flex gap-2"><input value={child} onChange={(e) => updateChildName(index, childIndex, e.target.value)} className="flex-1 rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm outline-none focus:border-accent" /><button onClick={() => deleteChild(index, childIndex)} className="rounded-lg border border-border px-2 text-[var(--danger)] hover:border-red-300"><Trash2 className="h-4 w-4" /></button></div>)}
                          </div>
                        </div>
                      ))}
                    </div>
                    <button onClick={() => saveSubjects()} className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"><Save className="h-4 w-4" />保存学科</button>
                  </section>
                )}

                {tab === 'models' && (
                  <section className="space-y-4">
                    <div className="rounded-lg border border-border bg-bg-card p-3 text-xs leading-5 text-text-secondary">API Key 只写入本机 .env；界面只显示是否已配置，不回显密钥。保存后新请求会读取新配置，已有长任务可能需要重启后端。</div>
                    <div className="grid gap-3 md:grid-cols-2">
                      <Field label="推理后端"><select value={envDraft.LLM_BACKEND || 'deepseek'} onChange={(e) => setEnvDraft({ ...envDraft, LLM_BACKEND: e.target.value })} className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm"><option value="deepseek">DeepSeek</option><option value="moonshot">Moonshot/Kimi</option><option value="openai">OpenAI</option><option value="ollama">Ollama</option></select></Field>
                      <Field label="DeepSeek 模型"><input value={envDraft.DEEPSEEK_MODEL_NAME || ''} onChange={(e) => setEnvDraft({ ...envDraft, DEEPSEEK_MODEL_NAME: e.target.value })} className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label={`DeepSeek API Key（${settings?.env?.DEEPSEEK_API_KEY?.configured ? '已配置' : '未配置'}）`}><input type="password" value={envDraft.DEEPSEEK_API_KEY || ''} onChange={(e) => setEnvDraft({ ...envDraft, DEEPSEEK_API_KEY: e.target.value })} placeholder="留空则不修改" className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label="DeepSeek Base URL"><input value={envDraft.DEEPSEEK_API_BASE || ''} onChange={(e) => setEnvDraft({ ...envDraft, DEEPSEEK_API_BASE: e.target.value })} className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label={`OCR/Kimi API Key（${settings?.env?.MOONSHOT_API_KEY?.configured ? '已配置' : '未配置'}）`}><input type="password" value={envDraft.MOONSHOT_API_KEY || ''} onChange={(e) => setEnvDraft({ ...envDraft, MOONSHOT_API_KEY: e.target.value })} placeholder="留空则不修改" className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label="OCR/Kimi 模型"><input value={envDraft.KIMI_VISION_MODEL || ''} onChange={(e) => setEnvDraft({ ...envDraft, KIMI_VISION_MODEL: e.target.value })} className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label={`OpenAI API Key（${settings?.env?.OPENAI_API_KEY?.configured ? '已配置' : '未配置'}）`}><input type="password" value={envDraft.OPENAI_API_KEY || ''} onChange={(e) => setEnvDraft({ ...envDraft, OPENAI_API_KEY: e.target.value })} placeholder="留空则不修改" className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                      <Field label="通用模型名"><input value={envDraft.LLM_MODEL_NAME || ''} onChange={(e) => setEnvDraft({ ...envDraft, LLM_MODEL_NAME: e.target.value })} className="w-full rounded-lg border border-border bg-bg-primary px-3 py-2 text-sm" /></Field>
                    </div>
                    <button onClick={saveEnv} className="inline-flex items-center gap-2 rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent-hover"><Save className="h-4 w-4" />保存模型配置</button>
                  </section>
                )}
              </main>
            </div>
          </div>
        </div>
      )}
    </>
  );
};

const Field = ({ label, children }: { label: string; children: React.ReactNode }) => (
  <label className="block space-y-1.5 text-sm text-text-primary"><span className="text-xs font-medium text-text-secondary">{label}</span>{children}</label>
);

export default SystemHealth;