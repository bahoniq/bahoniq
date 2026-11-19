/* BahonIQ Instruction Generator - deterministic screenshot analysis helpers.
 * Pure functions are exported for both browser use and Node regression tests.
 */
(function (root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.InstructionImageProcessor = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function () {
  'use strict';

  const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));

  function isAnnotationPixel(r, g, b) {
    const max = Math.max(r, g, b);
    const min = Math.min(r, g, b);
    const saturation = max - min;
    const red = r >= 175 && r - g >= 55 && r - b >= 55;
    const green = g >= 155 && g - r >= 42 && g - b >= 35;
    const orange = r >= 215 && g >= 105 && g <= 205 && b <= 85 && saturation >= 85;
    return red || green || orange;
  }

  function analyseComponent(c, width, height) {
    const bw = c.maxX - c.minX + 1;
    const bh = c.maxY - c.minY + 1;
    const area = bw * bh;
    const density = c.count / Math.max(1, area);
    const imageShare = area / Math.max(1, width * height);
    if (c.count < 22 || bw < 8 || bh < 6 || imageShare > 0.45) return null;

    const edgeTolerance = Math.max(1, Math.round(Math.min(bw, bh) * 0.10));
    const coverages = [
      c.topHits / Math.max(1, bw),
      c.bottomHits / Math.max(1, bw),
      c.leftHits / Math.max(1, bh),
      c.rightHits / Math.max(1, bh),
    ];
    const strongEdges = coverages.filter(v => v >= 0.34).length;
    const averageEdge = coverages.reduce((a, b) => a + b, 0) / 4;
    const aspect = Math.max(bw / bh, bh / bw);

    // A user rectangle is sparse inside, but has long connected edge runs.
    const rectangleLike = strongEdges >= 3 && density <= 0.42 && bw >= 18 && bh >= 12;
    // Arrows / underlines are elongated connected strokes. They are useful, but less certain.
    const strokeLike = aspect >= 2.2 && density >= 0.025 && density <= 0.38 && Math.max(bw, bh) >= 28;
    // Filled interface buttons are intentionally rejected.
    if (!rectangleLike && !strokeLike) return null;

    let confidence = rectangleLike
      ? 0.70 + Math.min(0.24, averageEdge * 0.28 + strongEdges * 0.025)
      : 0.58 + Math.min(0.18, (aspect - 2.2) * 0.035);
    if (density > 0.32) confidence -= 0.12;
    if (imageShare < 0.00008) confidence -= 0.08;

    return {
      x: c.minX, y: c.minY, w: bw, h: bh,
      cx: c.minX + bw / 2, cy: c.minY + bh / 2,
      count: c.count, density, rectangleLike, strokeLike,
      confidence: clamp(confidence, 0, 0.98), edgeTolerance,
    };
  }

  function detectAnnotationsFromRGBA(data, width, height) {
    if (!data || !width || !height || data.length < width * height * 4) {
      return { found: false, confidence: 0, regions: [], reason: 'invalid-image' };
    }
    const size = width * height;
    const mask = new Uint8Array(size);
    for (let i = 0; i < size; i++) {
      const p = i * 4;
      if (isAnnotationPixel(data[p], data[p + 1], data[p + 2])) mask[i] = 1;
    }

    const seen = new Uint8Array(size);
    const queue = new Int32Array(size);
    const candidates = [];
    const dirs = [[1, 0], [-1, 0], [0, 1], [0, -1]];

    for (let start = 0; start < size; start++) {
      if (!mask[start] || seen[start]) continue;
      let head = 0, tail = 0;
      queue[tail++] = start;
      seen[start] = 1;
      let minX = width, minY = height, maxX = 0, maxY = 0, count = 0;
      const pixels = [];

      while (head < tail) {
        const idx = queue[head++];
        const x = idx % width;
        const y = Math.floor(idx / width);
        pixels.push(idx);
        count++;
        minX = Math.min(minX, x); maxX = Math.max(maxX, x);
        minY = Math.min(minY, y); maxY = Math.max(maxY, y);
        for (const [dx, dy] of dirs) {
          const nx = x + dx, ny = y + dy;
          if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue;
          const ni = ny * width + nx;
          if (mask[ni] && !seen[ni]) { seen[ni] = 1; queue[tail++] = ni; }
        }
      }

      const bw = maxX - minX + 1, bh = maxY - minY + 1;
      const tol = Math.max(1, Math.round(Math.min(bw, bh) * 0.10));
      let topHits = 0, bottomHits = 0, leftHits = 0, rightHits = 0;
      for (const idx of pixels) {
        const x = idx % width, y = Math.floor(idx / width);
        if (y - minY <= tol) topHits++;
        if (maxY - y <= tol) bottomHits++;
        if (x - minX <= tol) leftHits++;
        if (maxX - x <= tol) rightHits++;
      }
      const candidate = analyseComponent({ minX, minY, maxX, maxY, count, topHits, bottomHits, leftHits, rightHits }, width, height);
      if (candidate) candidates.push(candidate);
    }

    if (!candidates.length) return { found: false, confidence: 0, regions: [], reason: 'no-confident-annotation' };
    candidates.sort((a, b) => b.confidence - a.confidence || b.count - a.count);
    const usable = candidates.filter(c => c.confidence >= 0.60).slice(0, 6);
    const minX = Math.min(...usable.map(c => c.x));
    const minY = Math.min(...usable.map(c => c.y));
    const maxX = Math.max(...usable.map(c => c.x + c.w));
    const maxY = Math.max(...usable.map(c => c.y + c.h));
    const union = { x: minX, y: minY, w: maxX - minX, h: maxY - minY };
    union.cx = union.x + union.w / 2;
    union.cy = union.y + union.h / 2;
    const spread = Math.max(union.w / width, union.h / height);
    const confidence = usable.length === 1
      ? usable[0].confidence
      : clamp(usable.reduce((s, c) => s + c.confidence, 0) / usable.length - Math.max(0, spread - 0.55) * 0.35, 0, 0.98);
    return { found: true, confidence, regions: usable, union, spread, reason: 'annotation-detected' };
  }

  function chooseMode(detection, imageWidth, imageHeight) {
    if (!detection || !detection.found || detection.confidence < 0.78) return 'full';
    if (detection.regions.length > 1 && detection.spread > 0.58) return 'full';
    const u = detection.union;
    const share = (u.w * u.h) / Math.max(1, imageWidth * imageHeight);
    if (share <= 0.13) return 'zoom';
    return 'context';
  }

  function computeCrop(imageWidth, imageHeight, roi, targetAspect, options = {}) {
    const padding = options.padding ?? 0.22;
    const minContext = options.minContext ?? 0.30;
    if (!roi) return { x: 0, y: 0, w: imageWidth, h: imageHeight };

    let viewW = Math.max(roi.w * (1 + padding * 2), imageWidth * minContext);
    let viewH = Math.max(roi.h * (1 + padding * 2), imageHeight * minContext);
    if (viewW / viewH < targetAspect) viewW = viewH * targetAspect;
    else viewH = viewW / targetAspect;
    if (viewW > imageWidth) { viewW = imageWidth; viewH = viewW / targetAspect; }
    if (viewH > imageHeight) { viewH = imageHeight; viewW = viewH * targetAspect; }

    let x = roi.cx - viewW / 2;
    let y = roi.cy - viewH / 2;
    x = clamp(x, 0, Math.max(0, imageWidth - viewW));
    y = clamp(y, 0, Math.max(0, imageHeight - viewH));
    return { x, y, w: viewW, h: viewH };
  }

  function cropContains(crop, roi, margin = 0) {
    return crop.x <= roi.x - margin && crop.y <= roi.y - margin &&
      crop.x + crop.w >= roi.x + roi.w + margin &&
      crop.y + crop.h >= roi.y + roi.h + margin;
  }

  return { isAnnotationPixel, detectAnnotationsFromRGBA, chooseMode, computeCrop, cropContains };
});
