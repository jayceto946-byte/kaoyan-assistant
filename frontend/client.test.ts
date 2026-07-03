import { afterEach, describe, expect, it, vi } from 'vitest';
import { consumeSseChunk, consumeSseLine, flushSseBuffer, type ChatEvent } from './src/api/client';

describe('SSE parsing', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('keeps partial data in the buffer until a newline completes the event', () => {
    const events: ChatEvent[] = [];
    const first = consumeSseChunk('data: {"stage":"generate","chunk":"hel', '', (event) => events.push(event));

    expect(first.buffer).toBe('data: {"stage":"generate","chunk":"hel');
    expect(first.sawTerminalEvent).toBe(false);
    expect(events).toEqual([]);

    const second = consumeSseChunk('lo"}\n\n', first.buffer, (event) => events.push(event));

    expect(second.buffer).toBe('');
    expect(second.sawTerminalEvent).toBe(false);
    expect(events).toEqual([{ stage: 'generate', chunk: 'hello' }]);
  });

  it('detects done and error terminal events', () => {
    const events: ChatEvent[] = [];

    expect(consumeSseLine('data: {"stage":"done"}', (event) => events.push(event))).toBe(true);
    expect(consumeSseLine('data: {"stage":"error","message":"bad"}', (event) => events.push(event))).toBe(true);

    expect(events.map((event) => event.stage)).toEqual(['done', 'error']);
  });

  it('flushes a residual final line after the stream closes', () => {
    const events: ChatEvent[] = [];

    const sawTerminal = flushSseBuffer('data: {"stage":"done"}', (event) => events.push(event));

    expect(sawTerminal).toBe(true);
    expect(events).toEqual([{ stage: 'done' }]);
  });

  it('warns and skips malformed JSON payloads', () => {
    const warn = vi.spyOn(console, 'warn').mockImplementation(() => undefined);
    const events: ChatEvent[] = [];

    const sawTerminal = consumeSseLine('data: {not-json}', (event) => events.push(event));

    expect(sawTerminal).toBe(false);
    expect(events).toEqual([]);
    expect(warn).toHaveBeenCalled();
  });
});