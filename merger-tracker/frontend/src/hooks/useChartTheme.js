import { useMemo } from 'react';
import { useTheme } from '../context/ThemeContext';

/**
 * Theme-dependent Chart.js colours.
 *
 * Chart.js draws to a canvas, so it can't pick up CSS `dark:` variants — the
 * tick/grid/legend/tooltip colours have to be passed in as options. This hook
 * centralises the light/dark palette and returns ready-to-spread option
 * fragments so charts stay consistent and re-theme on toggle.
 *
 * Because the returned object identity changes with the theme, any component
 * that spreads these fragments into its Chart `options` re-renders and Chart.js
 * redraws with the new colours. For charts that memoise their options, include
 * `isDark` (or the fragments) in the dependency list.
 */
export function useChartTheme() {
  const { isDark } = useTheme();

  return useMemo(() => {
    const tick = isDark ? '#9ca3af' : '#6b7280'; // gray-400 / gray-500
    const grid = isDark ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.04)';
    const border = isDark ? 'rgba(255,255,255,0.12)' : 'rgba(0,0,0,0.1)';
    const legend = isDark ? '#e5e7eb' : '#374151'; // gray-200 / gray-700
    const title = isDark ? '#f3f4f6' : '#111827'; // gray-100 / gray-900

    return {
      isDark,
      // Raw colours, for ad-hoc use.
      colors: { tick, grid, border, legend, title },
      // `scales.x` / `scales.y` fragment: tick + grid + border colours.
      axis: {
        ticks: { color: tick },
        grid: { color: grid },
        border: { color: border },
      },
      // `plugins.legend.labels` fragment.
      legendLabels: { color: legend },
      // `plugins.tooltip` fragment tuned for each surface.
      tooltip: isDark
        ? {
            backgroundColor: 'rgba(31,41,55,0.95)', // gray-800
            titleColor: '#f9fafb',
            bodyColor: '#e5e7eb',
            borderColor: 'rgba(255,255,255,0.12)',
            borderWidth: 1,
          }
        : {
            backgroundColor: 'rgba(255,255,255,0.95)',
            titleColor: '#111827',
            bodyColor: '#374151',
            borderColor: 'rgba(0,0,0,0.1)',
            borderWidth: 1,
          },
    };
  }, [isDark]);
}
