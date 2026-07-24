import { useCallback, useMemo, useState } from 'react';
import type { ExerciseCandidate } from '../../../types';
import {
  filterCandidates,
  mergeSelectedCandidates as mergeSelected,
  splitCandidateAtBlankLine,
  summarizeCandidates,
  type CandidateFilter,
} from './candidateOperations';


interface UseExerciseImportCandidatesOptions {
  onMessage: (message: string) => void;
}

export function useExerciseImportCandidates({ onMessage }: UseExerciseImportCandidatesOptions) {
  const [candidates, setCandidates] = useState<ExerciseCandidate[]>([]);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [candidateFilter, setCandidateFilter] = useState<CandidateFilter>('all');
  const [editingCandidateId, setEditingCandidateId] = useState('');

  const importSummary = useMemo(() => summarizeCandidates(candidates), [candidates]);
  const filteredCandidates = useMemo(() => filterCandidates(candidates, candidateFilter), [candidateFilter, candidates]);

  const resetImportCandidates = useCallback(() => {
    setCandidates([]);
    setSelectedIds(new Set());
  }, []);

  const replaceCandidates = useCallback((next: ExerciseCandidate[]) => {
    setCandidates(next);
    setSelectedIds(new Set(next.map((item) => item.id)));
  }, []);

  const removeSelectedCandidates = useCallback(() => {
    setCandidates((current) => current.filter((item) => !selectedIds.has(item.id)));
    setSelectedIds(new Set());
  }, [selectedIds]);

  const selectAllCandidates = useCallback(() => {
    setSelectedIds(new Set(candidates.map((item) => item.id)));
  }, [candidates]);

  const clearCandidateSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);
  const updateCandidate = useCallback((id: string, updates: Partial<ExerciseCandidate>) => {
    setCandidates((items) => items.map((item) => item.id === id ? { ...item, ...updates } : item));
  }, []);

  const mergeSelectedCandidates = useCallback(() => {
    const result = mergeSelected(candidates, selectedIds);
    if (!result) {
      onMessage('请至少选择两道相邻候选题进行合并');
      return;
    }
    setCandidates(result.candidates);
    setSelectedIds(new Set([result.merged.id]));
    setEditingCandidateId(result.merged.id);
  }, [candidates, onMessage, selectedIds]);

  const splitCandidate = useCallback((candidate: ExerciseCandidate) => {
    const parts = splitCandidateAtBlankLine(candidate, Date.now().toString(36));
    if (!parts) {
      onMessage('请先在题干编辑框中用空行标出拆分位置');
      setEditingCandidateId(candidate.id);
      return;
    }
    setCandidates((current) => {
      const index = current.findIndex((item) => item.id === candidate.id);
      const next = current.filter((item) => item.id !== candidate.id);
      next.splice(Math.max(0, index), 0, ...parts);
      return next;
    });
    setSelectedIds(new Set(parts.map((item) => item.id)));
    setEditingCandidateId(parts[0].id);
  }, [onMessage]);

  const toggleCandidate = useCallback((id: string) => {
    setSelectedIds((current) => {
      const next = new Set(current);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  return {
    candidates,
    selectedIds,
    candidateFilter,
    setCandidateFilter,
    editingCandidateId,
    setEditingCandidateId,
    importSummary,
    filteredCandidates,
    resetImportCandidates,
    updateCandidate,
    replaceCandidates,
    removeSelectedCandidates,
    selectAllCandidates,
    clearCandidateSelection,
    mergeSelectedCandidates,
    splitCandidate,
    toggleCandidate,
  };
}
