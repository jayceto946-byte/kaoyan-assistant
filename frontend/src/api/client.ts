import type { ConceptCandidate } from '../types';

const API_BASE = '/api';
const DEFAULT_TIMEOUT_MS = 20000;

type ChatEvent = {
  stage: string;
  chunk?: string;
  done?: boolean;
  intent?: string;
  chapters?: string[];
  fast_path?: boolean;
  content_count?: number;
  message?: string;
  conversation_id?: string;
  rewritten_question?: string;
  state?: { linked_concepts?: ConceptCandidate[] };
};

async function fetchWithTimeout(input: RequestInfo | URL, init: RequestInit = {}, timeoutMs = DEFAULT_TIMEOUT_MS) {
  const ctrl = new AbortController();
  const timer = window.setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: init.signal || ctrl.signal });
  } finally {
    window.clearTimeout(timer);
  }
}

export async function get(path: string, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<any> {
  const res = await fetchWithTimeout(`${API_BASE}${path}`, {}, timeoutMs);
  if (!res.ok) throw new Error(`GET ${path} failed: ${res.status}`);
  return res.json();
}

export async function post(path: string, body: unknown, timeoutMs = DEFAULT_TIMEOUT_MS): Promise<any> {
  const res = await fetchWithTimeout(`${API_BASE}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, timeoutMs);
  if (!res.ok) throw new Error(`POST ${path} failed: ${res.status}`);
  return res.json();
}
export function chatStream(
  question: string,
  bookName: string = '',
  subject: string = '',
  conversationId: string = '',
  onEvent: (event: ChatEvent) => void,
  onError?: (err: Error) => void
): () => void {
  const ctrl = new AbortController();

  (async () => {
    try {
      const res = await fetch(`${API_BASE}/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question, book_name: bookName, subject, conversation_id: conversationId }),
        signal: ctrl.signal,
      });

      if (!res.ok || !res.body) throw new Error(`SSE failed: ${res.status}`);

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';
        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          const json = trimmed.slice(6);
          if (json === '[DONE]') continue;
          try {
            onEvent(JSON.parse(json));
          } catch {
            // ignore malformed SSE data
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      if (err instanceof Error && err.name === 'AbortError') return;
      if (onError && err instanceof Error) onError(err);
    }
  })();

  return () => ctrl.abort();
}

export async function chatAsk(
  question: string,
  bookName: string = '',
  subject: string = '',
  conversationId: string = ''
): Promise<{ content: string; intent: string; chapters: string[]; linked_concepts?: ConceptCandidate[]; conversation_id?: string; rewritten_question?: string }> {
  const res = await fetch(`${API_BASE}/chat/ask`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, book_name: bookName, subject, conversation_id: conversationId }),
  });
  if (!res.ok) throw new Error(`chatAsk failed: ${res.status}`);
  return res.json();
}
