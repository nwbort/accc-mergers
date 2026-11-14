/**
 * Material 3 Expressive's shape library (Compose's `MaterialShapes`), drawn
 * as SVG paths, so the site can wear the same outlines as the Android app.
 *
 * The app gives each outcome its own shape (`outcomeShape` in its
 * ui/Common.kt): cleared's sunny seal, refused's four-sided cookie, the live
 * statuses' twelve-sided cookie, a ceased matter's gem. Event tiles are the
 * six-sided cookie. Keep `OUTCOME_SHAPES` here in step with that function.
 *
 * Every shape is described as a radius around the centre, r(θ), sampled at
 * the same number of points and joined with a Catmull-Rom spline. Sharing the
 * point count is what lets the loading indicator morph one shape into the
 * next with SVG's own `<animate attributeName="d">`: paths animate only
 * between paths with identical commands. They are not Compose's exact
 * polygons, but the same silhouettes at the sizes the site draws them.
 *
 * Paths are in a 100×100 box centred on (50, 50).
 */

import { MERGER_STATUS } from '../constants/mergerStatus';

const SAMPLES = 72;
const TAU = Math.PI * 2;

// A regular polygon with rounded corners, traced densely (straight sides,
// circular corner arcs) and then read back as a radius by angle.
function polygon(n, rounding = 0.3, rotation = -Math.PI / 2) {
  const corners = Array.from({ length: n }, (_, k) => rotation + (k * TAU) / n);
  const half = Math.PI / n;
  // Each corner's arc is centred far enough in that its outer edge meets the unit circle.
  const rho = rounding * Math.sin(half);
  const centreR = 1 - rho / Math.cos(half);
  const dense = [];
  corners.forEach((a, k) => {
    const cx = Math.cos(a) * centreR;
    const cy = Math.sin(a) * centreR;
    for (let j = 0; j <= 24; j++) {
      const phi = a - half + (j / 24) * 2 * half;
      dense.push([cx + Math.cos(phi) * rho, cy + Math.sin(phi) * rho]);
    }
    const b = corners[(k + 1) % n];
    const next = [Math.cos(b) * centreR + Math.cos(b - half) * rho, Math.sin(b) * centreR + Math.sin(b - half) * rho];
    const last = dense[dense.length - 1];
    for (let j = 1; j < 40; j++) {
      dense.push([last[0] + ((next[0] - last[0]) * j) / 40, last[1] + ((next[1] - last[1]) * j) / 40]);
    }
  });
  const polar = dense.map(([x, y]) => [Math.atan2(y, x), Math.hypot(x, y)]);
  return (t) => {
    let best = polar[0];
    let bestGap = Infinity;
    for (const p of polar) {
      const gap = Math.abs(Math.atan2(Math.sin(p[0] - t), Math.cos(p[0] - t)));
      if (gap < bestGap) {
        bestGap = gap;
        best = p;
      }
    }
    return best[1];
  };
}

// A "cookie": n round lobes with narrower valleys between them.
const cookie = (n, depth, rotation = -Math.PI / 2) => (t) =>
  1 - depth * (1 - Math.abs(Math.cos((n * (t - rotation)) / 2)));

const RADII = {
  circle: () => 1,
  // A soft 8-pointed seal.
  sunny: (t) => 1 + 0.07 * Math.cos(8 * (t + Math.PI / 2)),
  softBurst: (t) => 1 + 0.07 * Math.cos(10 * (t + Math.PI / 2)),
  cookie4: cookie(4, 0.12, Math.PI / 4),
  cookie6: cookie(6, 0.09),
  cookie9: cookie(9, 0.07),
  cookie12: cookie(12, 0.06),
  // Four rounded leaves with deep notches between them.
  clover4: (t) => 0.62 + 0.38 * Math.abs(Math.cos(2 * (t - Math.PI / 4))) ** 0.6,
  square: polygon(4, 0.45, Math.PI / 4),
  pentagon: polygon(5, 0.35),
  // A tall hexagonal gem.
  gem: polygon(6, 0.3),
  // A pill on its side, as the loading indicator's last frame.
  oval: (t) => 1 / Math.sqrt((Math.cos(t) / 1) ** 2 + (Math.sin(t) / 0.66) ** 2),
};

// Per-shape stretch: the gem stands taller than it is wide.
const STRETCH = { gem: [0.8, 1] };

function points(name) {
  const r = RADII[name];
  const [sx, sy] = STRETCH[name] || [1, 1];
  const pts = [];
  for (let i = 0; i < SAMPLES; i++) {
    const t = (i / SAMPLES) * TAU - Math.PI / 2;
    const radius = r(t);
    pts.push([Math.cos(t) * radius * sx, Math.sin(t) * radius * sy]);
  }
  // Fit the shape to the box, so every shape fills it the same way.
  const extent = Math.max(...pts.map(([x, y]) => Math.max(Math.abs(x), Math.abs(y))));
  return pts.map(([x, y]) => [50 + (x / extent) * 50, 50 + (y / extent) * 50]);
}

const fmt = (n) => Math.round(n * 100) / 100;

// Closed Catmull-Rom spline through the points, as cubic Béziers.
function toPath(pts) {
  const n = pts.length;
  let d = `M${fmt(pts[0][0])} ${fmt(pts[0][1])}`;
  for (let i = 0; i < n; i++) {
    const p0 = pts[(i - 1 + n) % n];
    const p1 = pts[i];
    const p2 = pts[(i + 1) % n];
    const p3 = pts[(i + 2) % n];
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += `C${fmt(c1[0])} ${fmt(c1[1])} ${fmt(c2[0])} ${fmt(c2[1])} ${fmt(p2[0])} ${fmt(p2[1])}`;
  }
  return `${d}Z`;
}

const cache = new Map();

/** The SVG path (100×100 box) of a named shape; unknown names are a circle. */
export function shapePath(name) {
  const key = RADII[name] ? name : 'circle';
  if (!cache.has(key)) cache.set(key, toPath(points(key)));
  return cache.get(key);
}

/**
 * A shape as a CSS `clip-path` for a box `size` pixels square, for clipping
 * an element that already has its fill (a tile with its `bg-*` class).
 * `path()` takes pixels, not percentages, so the box size has to be fixed.
 */
export function shapeClipPath(name, size) {
  const key = `${name}@${size}`;
  if (!cache.has(key)) {
    const scale = size / 100;
    const scaled = shapePath(name).replace(/-?\d+(\.\d+)?/g, (n) => fmt(Number(n) * scale));
    cache.set(key, `path('${scaled}')`);
  }
  return cache.get(key);
}

export const SHAPE_NAMES = Object.keys(RADII);

/** The shapes the loading indicator morphs through, in order. */
export const LOADING_SEQUENCE = ['softBurst', 'cookie9', 'pentagon', 'oval', 'sunny', 'cookie4', 'cookie12'];

/**
 * Each outcome's shape, as the app's `outcomeShape`: the same outline marks
 * the same outcome on a phone and on the site.
 */
const OUTCOME_SHAPES = {
  [MERGER_STATUS.APPROVED]: 'sunny',
  [MERGER_STATUS.NOT_OPPOSED]: 'sunny',
  [MERGER_STATUS.APPROVED_WITH_CONDITIONS]: 'sunny',
  [MERGER_STATUS.NOT_APPROVED]: 'cookie4',
  [MERGER_STATUS.DECLINED]: 'cookie4',
  [MERGER_STATUS.UNDER_ASSESSMENT]: 'cookie12',
  [MERGER_STATUS.REFERRED_TO_PHASE_2]: 'cookie12',
  [MERGER_STATUS.ASSESSMENT_SUSPENDED]: 'square',
  [MERGER_STATUS.ASSESSMENT_CEASED]: 'gem',
};

export function outcomeShape(label) {
  return OUTCOME_SHAPES[label] || 'circle';
}
