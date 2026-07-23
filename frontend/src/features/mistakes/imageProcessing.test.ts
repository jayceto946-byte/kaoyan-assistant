import { describe, expect, it } from 'vitest';

import { applySharpen, clamp } from './imageProcessing';

describe('mistake image processing', () => {
  it('clamps values to the supplied range', () => {
    expect(clamp(-1, 0, 255)).toBe(0);
    expect(clamp(300, 0, 255)).toBe(255);
    expect(clamp(42, 0, 255)).toBe(42);
  });

  it('does not mutate pixels when sharpening is disabled', () => {
    const data = new Uint8ClampedArray(3 * 3 * 4).fill(80);
    const imageData = { data, width: 3, height: 3 } as ImageData;
    const before = Array.from(data);

    expect(applySharpen(imageData, 0)).toBe(imageData);
    expect(Array.from(data)).toEqual(before);
  });

  it('applies the same five-point kernel used by the capture workflow', () => {
    const data = new Uint8ClampedArray(3 * 3 * 4);
    for (let pixel = 0; pixel < 9; pixel += 1) {
      data[pixel * 4 + 3] = 255;
    }
    const center = (1 * 3 + 1) * 4;
    data[center] = 100;
    data[center + 1] = 100;
    data[center + 2] = 100;
    const imageData = { data, width: 3, height: 3 } as ImageData;

    applySharpen(imageData, 50);

    expect(Array.from(data.slice(center, center + 4))).toEqual([255, 255, 255, 255]);
  });
});
