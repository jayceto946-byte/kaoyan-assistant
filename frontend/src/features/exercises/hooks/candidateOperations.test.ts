import { describe, expect, it } from 'vitest';
import type { ExerciseCandidate } from '../../../types';
import {
  filterCandidates,
  mergeSelectedCandidates,
  splitCandidateAtBlankLine,
  summarizeCandidates,
} from './candidateOperations';

function candidate(id: string, questionText = `题目 ${id}`): ExerciseCandidate {
  return {
    id,
    question_text: questionText,
    answer: `答案 ${id}`,
    explanation: '',
    source: 'test',
    subject: '数学',
    chapter: '第一章',
    suggested_type: '计算题',
    difficulty: 3,
    tags: [id],
    linked_concepts: [],
    confidence: 0.9,
    reasons: [],
    needs_llm: false,
    needs_review: false,
    validation_issues: [],
  };
}

describe('exercise candidate operations', () => {
  it('summarizes and filters validation state', () => {
    const items = [
      candidate('a'),
      { ...candidate('b'), needs_llm: true, validation_issues: ['边界待确认'] },
      { ...candidate('c'), duplicate_of: 'existing' },
    ];

    expect(summarizeCandidates(items)).toMatchObject({ total: 3, needsLlm: 1, issues: 1, duplicates: 1 });
    expect(filterCandidates(items, 'issues').map((item) => item.id)).toEqual(['b']);
    expect(filterCandidates(items, 'duplicates').map((item) => item.id)).toEqual(['c']);
  });

  it('merges adjacent candidates at their original position', () => {
    const items = [candidate('a'), candidate('b'), candidate('c')];
    const result = mergeSelectedCandidates(items, new Set(['b', 'c']));

    expect(result?.candidates.map((item) => item.id)).toEqual(['a', 'b']);
    expect(result?.merged.question_text).toBe('题目 b\n\n题目 c');
    expect(result?.merged.tags).toEqual(['b', 'c']);
  });

  it('rejects non-adjacent candidate merges', () => {
    const items = [candidate('a'), candidate('b'), candidate('c')];
    expect(mergeSelectedCandidates(items, new Set(['a', 'c']))).toBeNull();
  });

  it('splits only at an explicit blank line', () => {
    expect(splitCandidateAtBlankLine(candidate('a', '没有分隔'), 'fixed')).toBeNull();

    const parts = splitCandidateAtBlankLine(candidate('a', '第一问\n\n第二问'), 'fixed');
    expect(parts?.map((item) => item.id)).toEqual(['a-fixed-1', 'a-fixed-2']);
    expect(parts?.map((item) => item.question_text)).toEqual(['第一问', '第二问']);
    expect(parts?.[0].answer).toBe('');
  });
});
