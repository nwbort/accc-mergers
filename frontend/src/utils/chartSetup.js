/**
 * Single Chart.js registration point for the whole site. Import for its side
 * effect from any module that renders a chart:
 *
 *     import '../utils/chartSetup';
 *
 * Chart.js registration is a global, cumulative singleton, but it used to be
 * declared per page — Analysis registered the scales and elements its charts
 * needed, Dashboard registered the arc element its doughnut needed. That works
 * only for as long as every chart lives on the page that registered for it, and
 * it fails in two ways once one doesn't:
 *
 * 1. A shared chart component rendered on a page that never registered its
 *    pieces throws (`"category" is not a registered scale`) and takes the whole
 *    route down through the error boundary. This is what happened when
 *    TurnaroundTrendChart moved to /state-of-play.
 * 2. Worse, it can appear to work. Because registration is global and routes
 *    are lazy-loaded, a page with an incomplete set still renders if the user
 *    happened to visit a page that registered the missing piece first — so the
 *    bug reproduces only on a cold direct load of that route.
 *
 * Registering the union here removes both. react-chartjs-2's typed components
 * (`Line`, `Bar`, `Doughnut`) register their own *controller*, so only scales,
 * elements and plugins need listing. There is no bundle cost: vite.config.js
 * already emits chart.js as one shared `chart` chunk, so the whole library
 * ships to any page with a chart no matter how little of it is registered.
 *
 * Adding a chart type that needs a piece not listed here (a radial scale, say)
 * means adding it here, not in the page.
 */
import {
  Chart as ChartJS,
  ArcElement,
  BarElement,
  CategoryScale,
  Filler,
  Legend,
  LinearScale,
  LineElement,
  PointElement,
  Title,
  Tooltip,
} from 'chart.js';

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  BarElement,
  ArcElement,
  Filler,
  Title,
  Tooltip,
  Legend
);
