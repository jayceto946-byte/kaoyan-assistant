import { useEffect, useId, useMemo, useState } from 'react';
import { get } from '../api/client';

export const COMMON_SUBJECTS = ['数学', '英语', '政治', '专业课', '线代', '微积分', '概率论', '高数', '数据结构', '操作系统', '未分类'];

type SubjectNode = { name: string; children?: string[] };

function unique(values: string[]) {
  return Array.from(new Set(values.map((item) => item.trim()).filter(Boolean)));
}

export default function SubjectInput({
  value,
  onChange,
  suggestions = [],
  placeholder = '选择或输入学科',
  className = '',
}: {
  value: string;
  onChange: (value: string) => void;
  suggestions?: string[];
  placeholder?: string;
  className?: string;
}) {
  const id = useId();
  const [managedSubjects, setManagedSubjects] = useState<string[]>([]);

  useEffect(() => {
    let cancelled = false;
    get('/system/settings/subjects', 15000)
      .then((res) => {
        if (cancelled || !res?.success) return;
        const tree = (res.data || []) as SubjectNode[];
        setManagedSubjects(tree.flatMap((node) => [node.name, ...(node.children || [])]));
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, []);

  const options = useMemo(() => unique([...COMMON_SUBJECTS, ...managedSubjects, ...suggestions]), [managedSubjects, suggestions]);

  return (
    <>
      <input
        value={value}
        onChange={(e) => onChange(e.target.value)}
        list={id}
        placeholder={placeholder}
        className={className || 'rounded-lg border border-border bg-bg-card px-3 py-2 text-sm outline-none focus:border-accent'}
      />
      <datalist id={id}>
        {options.map((item) => <option key={item} value={item} />)}
      </datalist>
    </>
  );
}
