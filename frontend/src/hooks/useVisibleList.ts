import { useCallback, useEffect, useMemo, useState } from 'react';

export function useVisibleList<T>(items: T[], pageSize = 30, resetKey: unknown = '') {
  const [visibleCount, setVisibleCount] = useState(pageSize);

  useEffect(() => {
    setVisibleCount(pageSize);
  }, [items.length, pageSize, resetKey]);

  const visibleItems = useMemo(() => items.slice(0, visibleCount), [items, visibleCount]);
  const hasMore = visibleCount < items.length;
  const showMore = useCallback(() => {
    setVisibleCount((count) => Math.min(items.length, count + pageSize));
  }, [items.length, pageSize]);

  return {
    visibleItems,
    visibleCount: Math.min(visibleCount, items.length),
    totalCount: items.length,
    hasMore,
    showMore,
  };
}
