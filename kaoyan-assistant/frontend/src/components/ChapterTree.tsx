import React, { useState } from 'react';
import { ChevronDown, ChevronRight, BookOpen, FileText } from 'lucide-react';

export interface ChapterNode {
  title: string;
  page?: number;
  end_page?: number;
  subsections?: ChapterNode[];
}

interface Props {
  chapters: ChapterNode[];
}

const SKIP_KEYWORDS = ['参考文献', '附录', '目录', '前言'];

function pageText(node: ChapterNode) {
  if (!node.page) return '';
  return node.end_page && node.end_page !== node.page ? `p${node.page}-${node.end_page}` : `p${node.page}`;
}

const ChapterTree: React.FC<Props> = ({ chapters }) => {
  const [open, setOpen] = useState<Set<number>>(() => new Set(chapters.map((_, index) => index)));

  if (!chapters || chapters.length === 0) {
    return <div className="rounded-lg border border-dashed border-border bg-bg-card p-4 text-sm text-text-secondary">暂无目录</div>;
  }

  const toggle = (index: number) => {
    setOpen((prev) => {
      const next = new Set(prev);
      if (next.has(index)) next.delete(index);
      else next.add(index);
      return next;
    });
  };

  return (
    <div className="space-y-1 p-2">
      {chapters.map((chapter, index) => {
        const skip = SKIP_KEYWORDS.some((keyword) => chapter.title.includes(keyword));
        if (skip) return null;
        const subsections = chapter.subsections || [];
        const expanded = open.has(index);
        return (
          <div key={`${chapter.title}-${chapter.page || index}`} className="rounded-md border border-transparent">
            <button
              type="button"
              onClick={() => subsections.length && toggle(index)}
              className="flex w-full items-start gap-2 rounded-lg border border-transparent bg-transparent px-2.5 py-2 text-left text-sm transition-colors hover:border-border hover:bg-bg-card"
            >
              <span className="mt-0.5 text-text-secondary">
                {subsections.length ? (expanded ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />) : <BookOpen className="h-3.5 w-3.5" />}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block leading-snug text-text-primary">{chapter.title}</span>
                {pageText(chapter) && <span className="mt-0.5 block text-[11px] text-text-secondary">{pageText(chapter)}</span>}
              </span>
            </button>

            {expanded && subsections.length > 0 && (
              <div className="ml-4 mt-1 space-y-1 border-l border-border/80 pl-2">
                {subsections.map((section, sectionIndex) => (
                  <div
                    key={`${section.title}-${section.page || sectionIndex}`}
                    className="flex items-start gap-2 rounded-md px-2 py-1.5 text-xs text-text-secondary transition-colors hover:bg-bg-card hover:text-text-primary"
                  >
                    <FileText className="mt-0.5 h-3 w-3 flex-shrink-0 text-text-secondary" />
                    <span className="min-w-0 flex-1 leading-snug">{section.title}</span>
                    {pageText(section) && <span className="flex-shrink-0 text-[11px]">{pageText(section)}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
};

export default ChapterTree;
