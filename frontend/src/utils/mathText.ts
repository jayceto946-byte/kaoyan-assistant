const chineseRe = /[\u4e00-\u9fff\u3000-\u303f\uff00-\uffef]/;

function normalizeLatexText(text: string): string {
  return text
    .replace(/＄/g, '$')
    .replace(/\\\\\s*\[(?:\d+(?:\.\d+)?)(?:pt|em|ex|mm|cm|in)\]/g, '\\\\')
    .replace(/\\\\\[/g, '\\[')
    .replace(/\\\\\]/g, '\\]')
    .replace(/\\\\\(/g, '\\(')
    .replace(/\\\\\)/g, '\\)')
    .replace(/\r\n/g, '\n');
}

function protectMathAndCode(text: string): { text: string; tokens: string[] } {
  const tokens: string[] = [];
  const protect = (match: string) => {
    const token = `@@MATH_PROTECTED_${tokens.length}@@`;
    tokens.push(match);
    return token;
  };
  return {
    text: text
      .replace(/```[\s\S]*?```/g, protect)
      .replace(/\$\$[\s\S]*?\$\$/g, protect)
      .replace(/\$(?!\$)(?:\\.|[^$\\])*?\$/g, protect)
      .replace(/`[^`]*`/g, protect),
    tokens,
  };
}

function restoreProtected(text: string, tokens: string[]): string {
  return tokens.reduce((acc, token, index) => acc.replace(`@@MATH_PROTECTED_${index}@@`, () => token), text);
}
function convertTexDelimiters(text: string): string {
  return text
    .replace(/\\\[((?:.|\n)*?)\\\]/g, (_match, body: string) => '$$\n' + body + '\n$$')
    .replace(/\\\(((?:.|\n)*?)\\\)/g, (_match, body: string) => `$${body}$`);
}
function wrapBareMathEnvironments(text: string): string {
  const { text: unprotected, tokens } = protectMathAndCode(text);
  const envs = 'aligned|align|gathered|gather|cases|matrix|pmatrix|bmatrix|vmatrix|Vmatrix|array|split|equation';
  const envPattern = new RegExp(`(\\\\begin\\{(?:${envs})\\}[\\s\\S]*?\\\\end\\{(?:${envs})\\})`, 'g');
  return restoreProtected(
    unprotected.replace(envPattern, (_match, body: string) => '$$\n' + body + '\n$$'),
    tokens,
  );
}

function isEscaped(text: string, index: number): boolean {
  let slashCount = 0;
  for (let i = index - 1; i >= 0 && text[i] === '\\'; i -= 1) slashCount += 1;
  return slashCount % 2 === 1;
}

function containsChineseOutsideBraces(text: string): boolean {
  let depth = 0;
  for (let i = 0; i < text.length; i += 1) {
    const ch = text[i];
    if (ch === '\\') {
      i += 1;
      continue;
    }
    if (ch === '{') depth += 1;
    else if (ch === '}') depth = Math.max(0, depth - 1);
    else if (depth === 0 && chineseRe.test(ch)) return true;
  }
  return false;
}

function balanceDollarMath(text: string): string {
  let result = '';
  let i = 0;
  let inlineOpen = false;
  let blockOpen = false;

  while (i < text.length) {
    if (text[i] !== '$' || isEscaped(text, i)) {
      result += text[i];
      i += 1;
      continue;
    }

    const isBlock = text[i + 1] === '$';
    const token = isBlock ? '$$' : '$';
    const rest = text.slice(i + token.length);

    if (!inlineOpen && !blockOpen) {
      const closeIndex = rest.search(isBlock ? /(?<!\\)\$\$/ : /(?<!\\)\$/);
      const candidate = closeIndex >= 0 ? rest.slice(0, closeIndex) : rest;
      const first = candidate.trimStart()[0];
      if (first && chineseRe.test(first)) {
        result += token.replace(/\$/g, '\\$');
        i += token.length;
        continue;
      }
      if (containsChineseOutsideBraces(candidate) && closeIndex < 0) {
        result += token.replace(/\$/g, '\\$');
        i += token.length;
        continue;
      }
    }

    if (isBlock) blockOpen = !blockOpen;
    else if (!blockOpen) inlineOpen = !inlineOpen;
    result += token;
    i += token.length;
  }

  if (blockOpen) result += '$$';
  if (inlineOpen) result += '$';
  return result;
}

export function prepareMathMarkdown(text: string): string {
  return balanceDollarMath(wrapBareMathEnvironments(convertTexDelimiters(normalizeLatexText(text))));
}
