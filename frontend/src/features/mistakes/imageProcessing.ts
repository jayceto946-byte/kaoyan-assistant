export type CropState = { x: number; y: number; w: number; h: number };

export type ImageAdjust = {
  brightness: number;
  contrast: number;
  sharpen: number;
  grayscale: boolean;
};

export function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value));
}

export function applySharpen(imageData: ImageData, amount: number) {
  if (amount <= 0) return imageData;
  const strength = amount / 100;
  const { data, width, height } = imageData;
  const copy = new Uint8ClampedArray(data);
  const center = 1 + 4 * strength;
  const side = -strength;
  for (let y = 1; y < height - 1; y += 1) {
    for (let x = 1; x < width - 1; x += 1) {
      const idx = (y * width + x) * 4;
      for (let channel = 0; channel < 3; channel += 1) {
        const value =
          copy[idx + channel] * center +
          copy[idx - 4 + channel] * side +
          copy[idx + 4 + channel] * side +
          copy[idx - width * 4 + channel] * side +
          copy[idx + width * 4 + channel] * side;
        data[idx + channel] = clamp(value, 0, 255);
      }
    }
  }
  return imageData;
}

async function fileToImage(file: File): Promise<HTMLImageElement> {
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.decoding = 'async';
    await new Promise<void>((resolve, reject) => {
      image.onload = () => resolve();
      image.onerror = () => reject(new Error('图片加载失败'));
      image.src = url;
    });
    return image;
  } finally {
    URL.revokeObjectURL(url);
  }
}

export async function renderProcessedImage(
  file: File,
  crop: CropState,
  adjust: ImageAdjust,
): Promise<{ file: File; preview: string }> {
  const image = await fileToImage(file);
  const sx = Math.round((crop.x / 100) * image.naturalWidth);
  const sy = Math.round((crop.y / 100) * image.naturalHeight);
  const sw = Math.round((crop.w / 100) * image.naturalWidth);
  const sh = Math.round((crop.h / 100) * image.naturalHeight);
  const maxSide = 1800;
  const scale = Math.min(1, maxSide / Math.max(sw, sh));
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(sw * scale));
  canvas.height = Math.max(1, Math.round(sh * scale));
  const context = canvas.getContext('2d');
  if (!context) throw new Error('无法处理图片');
  context.filter = `brightness(${adjust.brightness}%) contrast(${adjust.contrast}%)${adjust.grayscale ? ' grayscale(100%)' : ''}`;
  context.drawImage(image, sx, sy, sw, sh, 0, 0, canvas.width, canvas.height);
  const imageData = context.getImageData(0, 0, canvas.width, canvas.height);
  context.putImageData(applySharpen(imageData, adjust.sharpen), 0, 0);
  const blob = await new Promise<Blob>((resolve, reject) => {
    canvas.toBlob(
      (next) => (next ? resolve(next) : reject(new Error('图片导出失败'))),
      'image/jpeg',
      0.9,
    );
  });
  const processed = new File(
    [blob],
    file.name.replace(/\.[^.]+$/, '') + '_scan.jpg',
    { type: 'image/jpeg' },
  );
  return { file: processed, preview: URL.createObjectURL(blob) };
}
