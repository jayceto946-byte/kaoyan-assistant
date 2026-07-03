import { describe, expect, it } from 'vitest';
import { prepareMathMarkdown } from './src/utils/mathText';

describe('prepareMathMarkdown', () => {
  it('converts TeX display delimiters to dollar math blocks', () => {
    expect(prepareMathMarkdown('A \\[x^2+1\\] B')).toContain('$$\nx^2+1\n$$');
  });

  it('wraps bare math environments without touching existing inline math', () => {
    const result = prepareMathMarkdown('has $x+1$ and \\begin{cases}x>0\\end{cases}');

    expect(result).toContain('$x+1$');
    expect(result).toContain('$$\n\\begin{cases}x>0\\end{cases}\n$$');
  });

  it('escapes accidental dollar signs before Chinese prose', () => {
    expect(prepareMathMarkdown('\u4ef7\u683c\u662f $\u672a\u77e5')).toBe('\u4ef7\u683c\u662f \\$\u672a\u77e5');
  });
});