import { describe, expect, it } from 'vitest';
import { buildTextbookScopeOptions, scopeContainsBook } from './src/utils/textbookScopes';

describe('buildTextbookScopeOptions', () => {
  it('merges core and reference books into one logical subject range', () => {
    const scopes = buildTextbookScopeOptions([
      { name: '传感器短书', subject: '专业课/传感器', book_role: 'core' },
      { name: '传感器长书', subject: '专业课/传感器', book_role: 'reference' },
      { name: '误差理论与数据处理', subject: '专业课/误差理论', book_role: 'core' },
    ]);

    expect(scopes).toHaveLength(2);
    expect(scopes[0]).toMatchObject({ name: '传感器短书', displayName: '传感器' });
    expect(scopeContainsBook(scopes[0], '传感器长书')).toBe(true);
    expect(scopes[1].name).toBe('误差理论与数据处理');
  });

  it('keeps invalid reference-only groups visible instead of hiding data', () => {
    const scopes = buildTextbookScopeOptions([
      { name: '资料甲', subject: '专业课/信号', book_role: 'reference' },
      { name: '资料乙', subject: '专业课/信号', book_role: 'reference' },
    ]);

    expect(scopes.map((item) => item.name)).toEqual(['资料甲', '资料乙']);
  });
});
