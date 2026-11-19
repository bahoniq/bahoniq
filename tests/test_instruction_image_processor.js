const assert = require('assert');
const P = require('../web_app/static/instruction_image_processor.js');

function image(w, h, bg = [235, 239, 244, 255]) {
  const d = new Uint8ClampedArray(w * h * 4);
  for (let i = 0; i < w * h; i++) d.set(bg, i * 4);
  return { w, h, d };
}
function px(im, x, y, c = [245, 20, 30, 255]) {
  if (x < 0 || y < 0 || x >= im.w || y >= im.h) return;
  im.d.set(c, (y * im.w + x) * 4);
}
function rect(im, x, y, w, h, t = 3, c) {
  for (let n = 0; n < t; n++) {
    for (let xx = x; xx < x + w; xx++) { px(im, xx, y + n, c); px(im, xx, y + h - 1 - n, c); }
    for (let yy = y; yy < y + h; yy++) { px(im, x + n, yy, c); px(im, x + w - 1 - n, yy, c); }
  }
}
function line(im, x1, y1, x2, y2, t = 3) {
  const steps = Math.max(Math.abs(x2 - x1), Math.abs(y2 - y1));
  for (let i = 0; i <= steps; i++) {
    const x = Math.round(x1 + (x2 - x1) * i / steps), y = Math.round(y1 + (y2 - y1) * i / steps);
    for (let dx = -t; dx <= t; dx++) for (let dy = -t; dy <= t; dy++) px(im, x + dx, y + dy);
  }
}
function detect(im) { return P.detectAnnotationsFromRGBA(im.d, im.w, im.h); }
function expectFound(name, im) {
  const r = detect(im); assert(r.found, `${name}: annotation not found`); return r;
}

let im = image(800, 400); rect(im, 20, 20, 130, 70); expectFound('top-left', im);
im = image(800, 400); rect(im, 640, 310, 130, 65); expectFound('bottom-right', im);
im = image(800, 400); rect(im, 350, 180, 70, 32); expectFound('small button', im);
im = image(800, 400); rect(im, 90, 170, 610, 38); expectFound('long row', im);
im = image(800, 400); line(im, 120, 300, 430, 120); expectFound('arrow/line', im);
im = image(800, 400); rect(im, 180, 140, 100, 50); rect(im, 300, 145, 110, 48); assert(expectFound('near boxes', im).regions.length >= 2);
im = image(800, 400); rect(im, 20, 30, 90, 45); rect(im, 680, 320, 90, 45); assert.strictEqual(P.chooseMode(expectFound('far boxes', im), 800, 400), 'full');
im = image(800, 400); assert(!detect(im).found, 'empty image must use fallback');
im = image(400, 800); rect(im, 280, 650, 90, 80); expectFound('portrait', im);
im = image(1400, 300); rect(im, 20, 100, 160, 70); expectFound('very wide', im);
im = image(180, 90); rect(im, 15, 15, 80, 45, 2); expectFound('low resolution', im);

// Filled red UI button must not be interpreted as a drawn outline.
im = image(800, 400);
for (let y = 150; y < 205; y++) for (let x = 300; x < 500; x++) px(im, x, y);
assert(!detect(im).found, 'filled UI button must be rejected');

const roi = { x: 710, y: 330, w: 60, h: 38, cx: 740, cy: 349 };
const crop = P.computeCrop(800, 400, roi, 1299 / 623);
assert(P.cropContains(crop, roi), 'crop must contain the entire annotation');
assert(Math.abs(crop.w / crop.h - 1299 / 623) < 0.002, 'target aspect ratio must be preserved');
assert(crop.x >= 0 && crop.y >= 0 && crop.x + crop.w <= 800.01 && crop.y + crop.h <= 400.01, 'crop must stay inside image');

console.log('15 screenshot processing regression cases passed');
