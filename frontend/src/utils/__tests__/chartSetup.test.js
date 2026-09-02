/* global process */
import { readFileSync, readdirSync } from 'node:fs';
import { resolve, join } from 'node:path';
import { describe, it, expect } from 'vitest';

import { Chart as ChartJS } from 'chart.js';
import '../chartSetup.js';

// Vitest runs with the frontend project dir as cwd.
const frontendRoot = process.cwd();

function sourceFiles(dir, acc = []) {
  for (const entry of readdirSync(resolve(frontendRoot, dir), { withFileTypes: true })) {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== '__tests__') sourceFiles(path, acc);
    } else if (/\.jsx?$/.test(entry.name)) {
      acc.push(path);
    }
  }
  return acc;
}

// Chart.js registration is a global singleton that was once declared per page,
// so a chart rendered on a page that had not registered its scales threw at
// runtime — and no test caught it, because jsdom's canvas has no 2d context, so
// Chart.js never initialises far enough to resolve a scale. Rendering a chart
// in jsdom therefore cannot detect a missing registration at all. These two
// tests guard the two halves of the invariant directly instead: that the shared
// module registers what the site's charts ask for, and that every module
// drawing a chart pulls that module in.
describe('chartSetup', () => {
  it('registers every scale and element the site\'s charts use', () => {
    // category + linear: every axis on the line, bar and scatter charts.
    // arc: the dashboard's phase 2 doughnut. line/point: the trend and ECDF
    // charts. bar: monthly volume and the industry comparison.
    for (const scale of ['category', 'linear']) {
      expect(ChartJS.registry.scales.get(scale), `scale "${scale}"`).toBeTruthy();
    }
    for (const element of ['arc', 'bar', 'line', 'point']) {
      expect(ChartJS.registry.elements.get(element), `element "${element}"`).toBeTruthy();
    }
  });

  it('registers the Filler plugin the area fills depend on', () => {
    // The caseload and turnaround charts use `fill: true`; without Filler the
    // area silently renders as a bare line rather than throwing.
    expect(ChartJS.registry.plugins.get('filler')).toBeTruthy();
  });

  it('is imported by every module that renders a chart', () => {
    const drawsCharts = [...sourceFiles('src/pages'), ...sourceFiles('src/components')]
      .filter(path => readFileSync(resolve(frontendRoot, path), 'utf8').includes("from 'react-chartjs-2'"));

    // If this is empty the filter has drifted and the test is guarding nothing.
    expect(drawsCharts.length).toBeGreaterThan(0);

    for (const path of drawsCharts) {
      const src = readFileSync(resolve(frontendRoot, path), 'utf8');
      expect(src, `${path} renders a chart, so it must import utils/chartSetup`)
        .toMatch(/import ['"][^'"]*utils\/chartSetup['"]/);
      expect(src, `${path} should not register Chart.js pieces of its own — add them to utils/chartSetup instead`)
        .not.toMatch(/ChartJS\.register\(/);
    }
  });
});
