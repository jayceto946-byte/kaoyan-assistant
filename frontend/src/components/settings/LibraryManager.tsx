import { useMemo, useState } from 'react';
import { Archive, BookOpen, ChevronDown, ChevronRight, FolderOpen, Library, Plus, RefreshCw, Save, Trash2 } from 'lucide-react';

export type LibrarySubject = { name: string; children: string[] };
export type LibraryBook = { name: string; subject?: string; path?: string; has_pdf?: boolean; chapter_count?: number };

type Props = {
  subjects: LibrarySubject[]; books: LibraryBook[]; selectedSubjectIndex: number; selectedChildIndex: number | null;
  onSelect: (subjectIndex: number, childIndex: number | null) => void; onAddSubject: () => void; onAddChild: (subjectIndex: number) => void;
  onRenameSubject: (index: number, name: string) => void; onRenameChild: (index: number, name: string) => void;
  onDeleteSubject: (index: number) => void; onDeleteChild: (index: number) => void; onSaveSubjects: () => void;
  onImportBook: () => void; onRefresh: () => void; onMoveBook: (name: string, target: string) => void;
  onSwitchBook: (name: string) => void; onArchiveBook: (name: string) => void;
};

const pathFor = (parent = '', child = '') => child ? `${parent}/${child}` : parent;
const belongsTo = (book: LibraryBook, parent: string, child = '') => {
  const value = (book.subject || '').trim();
  if (!parent) return !value;
  if (child) return value === pathFor(parent, child) || value === child;
  return value === parent || value.startsWith(`${parent}/`);
};

export default function LibraryManager(props: Props) {
  const { subjects, books, selectedSubjectIndex, selectedChildIndex, onSelect } = props;
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const subject = selectedSubjectIndex >= 0 ? subjects[selectedSubjectIndex] || null : null;
  const child = subject && selectedChildIndex !== null ? subject.children[selectedChildIndex] || '' : '';
  const target = subject ? pathFor(subject.name, child) : '';
  const currentBooks = useMemo(() => subject ? books.filter((book) => belongsTo(book, subject.name, child)) : books.filter((book) => !(book.subject || '').trim()), [books, subject, child]);
  const parentHasBooks = subject ? books.some((book) => belongsTo(book, subject.name)) : false;
  const selectedHasBooks = subject && child ? books.some((book) => belongsTo(book, subject.name, child)) : parentHasBooks;

  const select = (subjectIndex: number, childIndex: number | null) => {
    onSelect(subjectIndex, childIndex);
    if (subjectIndex >= 0) setExpanded((value) => ({ ...value, [subjectIndex]: true }));
  };

  return <section className="space-y-3">
    <header className="flex flex-wrap items-center justify-between gap-3">
      <div><h2 className="type-section-title text-text-primary">资料库</h2><p className="mt-1 text-xs text-text-secondary">统一管理学科、科目和教材归属。分类调整不会移动教材文件或索引。</p></div>
      <div className="flex gap-2">
        <button onClick={props.onImportBook} className="inline-flex items-center gap-2 rounded-lg border border-border bg-bg-card px-3 py-2 text-sm hover:border-accent"><BookOpen className="h-4 w-4" />导入教材</button>
        <button onClick={props.onSaveSubjects} className="inline-flex items-center gap-2 rounded-lg bg-accent px-3 py-2 text-sm font-medium text-white hover:bg-accent-hover"><Save className="h-4 w-4" />保存目录</button>
      </div>
    </header>

    <div className="grid min-h-[520px] overflow-hidden rounded-xl border border-border bg-bg-card lg:grid-cols-[280px_minmax(0,1fr)]">
      <aside className="border-b border-border bg-bg-secondary/55 p-3 lg:border-b-0 lg:border-r">
        <div className="mb-3 flex items-center justify-between px-1"><span className="flex items-center gap-2 text-sm font-semibold"><Library className="h-4 w-4 text-accent" />学习资料</span><button onClick={props.onAddSubject} className="flex h-8 w-8 items-center justify-center rounded-lg text-text-secondary hover:bg-bg-card hover:text-accent" title="添加一级学科"><Plus className="h-4 w-4" /></button></div>
        <div className="space-y-1">
          {subjects.map((item, index) => {
            const open = expanded[index] ?? selectedSubjectIndex === index;
            const active = selectedSubjectIndex === index && selectedChildIndex === null;
            const count = books.filter((book) => belongsTo(book, item.name)).length;
            return <div key={`${item.name}-${index}`}>
              <div className={`flex items-center rounded-lg ${active ? 'bg-[var(--accent-soft)] text-accent' : 'hover:bg-bg-card'}`}>
                <button onClick={() => setExpanded((value) => ({ ...value, [index]: !open }))} className="flex h-9 w-8 items-center justify-center text-text-secondary" aria-label={open ? '折叠' : '展开'}>{open ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}</button>
                <button onClick={() => select(index, null)} className="flex min-w-0 flex-1 items-center gap-2 py-2 pr-2 text-left text-sm font-medium"><FolderOpen className="h-4 w-4" /><span className="truncate">{item.name}</span><span className="ml-auto text-[11px] text-text-secondary">{count}</span></button>
              </div>
              {open && <div className="ml-5 mt-1 space-y-1 border-l border-border pl-2">
                {item.children.map((childName, childIndex) => <button key={`${childName}-${childIndex}`} onClick={() => select(index, childIndex)} className={`flex w-full items-center rounded-lg px-3 py-2 text-left text-sm ${selectedSubjectIndex === index && selectedChildIndex === childIndex ? 'bg-[var(--accent-soft)] text-accent' : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'}`}><span className="min-w-0 flex-1 truncate">{childName}</span><span className="text-[11px]">{books.filter((book) => belongsTo(book, item.name, childName)).length}</span></button>)}
                <button onClick={() => { select(index, null); props.onAddChild(index); }} className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-xs text-text-secondary hover:bg-bg-card hover:text-accent"><Plus className="h-3.5 w-3.5" />添加科目</button>
              </div>}
            </div>;
          })}
          <button onClick={() => select(-1, null)} className={`mt-2 flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm ${selectedSubjectIndex < 0 ? 'bg-[var(--accent-soft)] text-accent' : 'text-text-secondary hover:bg-bg-card hover:text-text-primary'}`}><Archive className="h-4 w-4" /><span className="flex-1">未分类</span><span className="text-[11px]">{books.filter((book) => !(book.subject || '').trim()).length}</span></button>
        </div>
      </aside>

      <main className="min-w-0 p-4 sm:p-5">
        <div className="flex items-start justify-between gap-3 border-b border-border pb-4">
          <div><div className="text-xs text-text-secondary">{subject ? subject.name : '资料库'}</div><h3 className="mt-1 text-lg font-semibold">{child || subject?.name || '未分类教材'}</h3><div className="mt-1 text-xs text-text-secondary">{currentBooks.length} 本教材{target ? ` · ${target}` : ''}</div></div>
          <button onClick={props.onRefresh} className="inline-flex items-center gap-1.5 rounded-lg border border-border px-3 py-2 text-xs text-text-secondary hover:border-accent"><RefreshCw className="h-3.5 w-3.5" />刷新</button>
        </div>

        {subject && <div className="mt-4 rounded-lg border border-border bg-bg-secondary/55 p-3">
          <div className="flex flex-wrap items-end gap-3">
            <label className="min-w-[220px] flex-1 text-xs font-medium text-text-secondary">{child ? '科目名称' : '学科名称'}<input value={child || subject.name} disabled={selectedHasBooks} onChange={(event) => selectedChildIndex === null ? props.onRenameSubject(selectedSubjectIndex, event.target.value) : props.onRenameChild(selectedChildIndex, event.target.value)} className="mt-1.5 w-full rounded-lg border border-border bg-bg-card px-3 py-2 text-sm text-text-primary disabled:cursor-not-allowed disabled:bg-bg-primary disabled:text-text-secondary" /></label>
            <button disabled={selectedHasBooks} onClick={() => selectedChildIndex === null ? props.onDeleteSubject(selectedSubjectIndex) : props.onDeleteChild(selectedChildIndex)} className="inline-flex items-center gap-1.5 rounded-lg border border-[var(--danger-border)] px-3 py-2 text-xs text-[var(--danger)] disabled:cursor-not-allowed disabled:opacity-40"><Trash2 className="h-3.5 w-3.5" />删除分类</button>
          </div>
          {selectedHasBooks && <p className="mt-2 text-xs text-text-secondary">该分类仍有教材。为保护现有归属，移动教材后才能重命名或删除。</p>}
        </div>}

        <div className="mt-4 space-y-2">
          {currentBooks.map((book) => <BookRow key={book.name} book={book} subjects={subjects} onMove={(targetValue) => props.onMoveBook(book.name, targetValue)} onSwitch={() => props.onSwitchBook(book.name)} onArchive={() => props.onArchiveBook(book.name)} />)}
          {!currentBooks.length && <div className="rounded-lg border border-dashed border-border bg-bg-primary px-4 py-10 text-center"><BookOpen className="mx-auto h-6 w-6 text-text-secondary" /><div className="mt-2 text-sm font-medium">这里还没有教材</div><div className="mt-1 text-xs text-text-secondary">可以从其他分类移动教材，或导入新教材。</div></div>}
        </div>

      </main>
    </div>
  </section>;
}

function BookRow({ book, subjects, onMove, onSwitch, onArchive }: { book: LibraryBook; subjects: LibrarySubject[]; onMove: (target: string) => void; onSwitch: () => void; onArchive: () => void }) {
  return (
    <article className="flex flex-wrap items-start gap-3 rounded-lg border border-border bg-bg-card px-3 py-3 hover:border-accent/35">
      <div className="flex h-9 w-9 flex-shrink-0 items-center justify-center rounded-lg bg-[var(--accent-softer)] text-accent">
        <BookOpen className="h-4 w-4" />
      </div>
      <div className="min-w-[180px] flex-1">
        <div className="truncate text-sm font-medium">{book.name}</div>
        <div className="mt-1 text-xs text-text-secondary">{book.has_pdf ? 'PDF' : 'OCR/Markdown'} · {book.chapter_count || 0} 章</div>
      </div>
      <label className="min-w-[220px] text-[11px] font-medium text-text-secondary">
        归属到
        <select
          value={book.subject || ''}
          onChange={(event) => { if (event.target.value !== (book.subject || '')) onMove(event.target.value); }}
          className="mt-1 block h-9 w-full rounded-lg border border-border bg-bg-card pl-2.5 pr-8 text-xs text-text-primary outline-none focus:border-accent"
        >
          <option value="">未分类</option>
          {subjects.map((subject) => (
            <optgroup key={subject.name} label={subject.name}>
              <option value={subject.name}>{subject.name}（未细分）</option>
              {subject.children.map((child) => (
                <option key={child} value={subject.name + '/' + child}>{subject.name} / {child}</option>
              ))}
            </optgroup>
          ))}
        </select>
      </label>
      <div className="flex flex-shrink-0 gap-1.5 self-end">
        <button onClick={onSwitch} className="rounded-lg border border-border px-2.5 py-1.5 text-xs text-text-secondary hover:border-accent">设为当前</button>
        <button onClick={onArchive} className="rounded-lg border border-border px-2.5 py-1.5 text-xs text-text-secondary hover:border-[var(--danger-border)] hover:text-[var(--danger)]">隐藏</button>
      </div>
    </article>
  );
}
