/* Academic Summarizer — Dashboard charts
   Reads chart data from <script id="dash-chart-data" type="application/json">
   (rendered server-side via {{ chart_data|json_script }}). All three charts
   re-render when the user toggles theme so the palette stays coherent. */
'use strict';

(function () {

  const ENDPOINT_ID = 'dash-chart-data';

  function readData() {
    const el = document.getElementById(ENDPOINT_ID);
    if (!el) return null;
    try { return JSON.parse(el.textContent); }
    catch (e) { console.warn('dashboard: bad chart data', e); return null; }
  }

  // Pull live values from the CSS theme so chart colors track --bg / --ink / --accent.
  // Note: --accent et al. are OKLCH in this theme — fine as solid stroke/fill,
  // but you cannot concatenate a hex-alpha suffix onto them. Use the explicit
  // rgba() fills below (ACCENT_FILL / ACCENT_FILL_STRONG) for any transparent
  // overlay so the same value reads on both light and dark backgrounds.
  function readTheme() {
    const css = getComputedStyle(document.documentElement);
    const v = (name, fb) => (css.getPropertyValue(name).trim() || fb);
    return {
      ink:    v('--ink',    '#111'),
      ink2:   v('--ink-2',  '#555'),
      ink3:   v('--ink-3',  '#888'),
      rule:   v('--rule',   '#e5e5e5'),
      accent: v('--accent', '#7c3aed'),
      ok:     v('--ok',     '#22c55e'),
      warn:   v('--warn',   '#f59e0b'),
      err:    v('--err',    '#ef4444'),
      bgElev: v('--bg-elev', '#fff'),
    };
  }

  // Soft violet at ~15% opacity — readable area fill in both themes
  const ACCENT_FILL        = 'rgba(124, 58, 237, 0.15)';
  const ACCENT_FILL_STRONG = 'rgba(124, 58, 237, 0.80)';

  // Apply our defaults to Chart.js once per render cycle
  function applyGlobalDefaults(theme) {
    if (!window.Chart) return;
    Chart.defaults.font.family = "Geist, system-ui, -apple-system, sans-serif";
    Chart.defaults.font.size   = 11;
    Chart.defaults.color       = theme.ink2;
    Chart.defaults.borderColor = theme.rule;
  }

  // Format an ISO date as "Mon dd" for x-axis ticks
  function fmtDate(iso) {
    const d = new Date(iso + 'T00:00:00');
    return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
  }

  function buildActivityChart(canvas, data, theme) {
    return new Chart(canvas.getContext('2d'), {
      type: 'line',
      data: {
        labels: data.activity_30d.map(d => fmtDate(d.date)),
        datasets: [{
          label: (window.i18n && window.i18n.dashboardChartPapers) || 'Papers',
          data: data.activity_30d.map(d => d.count),
          borderColor: theme.accent,
          backgroundColor: ACCENT_FILL,
          borderWidth: 2,
          tension: 0.35,
          fill: true,
          pointRadius: 0,
          pointHoverRadius: 4,
          pointHoverBackgroundColor: theme.accent,
          pointHoverBorderColor: theme.bgElev,
          pointHoverBorderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 700, easing: 'easeOutCubic' },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: theme.ink,
            titleColor: theme.bgElev,
            bodyColor: theme.bgElev,
            padding: 10,
            borderColor: theme.rule,
            borderWidth: 1,
            displayColors: false,
          },
        },
        scales: {
          x: {
            grid: { display: false },
            ticks: {
              autoSkip: true, maxTicksLimit: 8,
              color: theme.ink3, font: { size: 10 },
            },
          },
          y: {
            beginAtZero: true,
            grid: { color: theme.rule, drawBorder: false },
            ticks: {
              precision: 0, color: theme.ink3, font: { size: 10 },
            },
          },
        },
      },
    });
  }

  function buildLanguageChart(canvas, data, theme) {
    const d = data.language_distribution;
    const labels = ['EN', 'RU', 'UZ'];
    const values = [d.en || 0, d.ru || 0, d.uz || 0];
    // Use accent + two analogous-ish hues that still read on the page
    const palette = [theme.accent, theme.ok, theme.warn];
    return new Chart(canvas.getContext('2d'), {
      type: 'doughnut',
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: palette,
          borderColor: theme.bgElev,
          borderWidth: 2,
          hoverOffset: 6,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: '62%',
        animation: { duration: 700, easing: 'easeOutCubic' },
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              boxWidth: 10, boxHeight: 10, padding: 14,
              color: theme.ink2, font: { size: 11 },
            },
          },
          tooltip: {
            backgroundColor: theme.ink,
            titleColor: theme.bgElev,
            bodyColor: theme.bgElev,
            padding: 10,
            displayColors: false,
            callbacks: {
              label: (ctx) => `${ctx.label}: ${ctx.parsed} paper${ctx.parsed === 1 ? '' : 's'}`,
            },
          },
        },
      },
    });
  }

  function buildTagsChart(canvas, data, theme) {
    const labels = data.top_tags.map(t => t.name);
    const values = data.top_tags.map(t => t.count);
    return new Chart(canvas.getContext('2d'), {
      type: 'bar',
      data: {
        labels,
        datasets: [{
          label: (window.i18n && window.i18n.dashboardChartPapers) || 'Papers',
          data: values,
          backgroundColor: ACCENT_FILL_STRONG,
          borderColor: theme.accent,
          borderWidth: 1,
          borderRadius: 4,
          barThickness: 18,
        }],
      },
      options: {
        indexAxis: 'y',
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 700, easing: 'easeOutCubic' },
        plugins: {
          legend: { display: false },
          tooltip: {
            backgroundColor: theme.ink,
            titleColor: theme.bgElev,
            bodyColor: theme.bgElev,
            padding: 10,
            displayColors: false,
          },
        },
        scales: {
          x: {
            beginAtZero: true,
            grid: { color: theme.rule, drawBorder: false },
            ticks: { precision: 0, color: theme.ink3, font: { size: 10 } },
          },
          y: {
            grid: { display: false },
            ticks: { color: theme.ink2, font: { size: 11 } },
          },
        },
      },
    });
  }

  // ── Animated Stat Counters ──────────────────────────────────────────
  function animateStats() {
    const stats = document.querySelectorAll('.stat-value[data-value]');
    stats.forEach(el => {
      const target = parseFloat(el.getAttribute('data-value'));
      if (isNaN(target)) return;
      const duration = 1200; // 1.2s
      const start = 0;
      const startTime = performance.now();

      function update(currentTime) {
        const elapsed = currentTime - startTime;
        const progress = Math.min(elapsed / duration, 1);
        const easeOut = 1 - Math.pow(1 - progress, 3); // Ease out cubic
        const current = start + (target - start) * easeOut;
        
        if (target % 1 === 0) {
          el.childNodes[0].textContent = Math.floor(current);
        } else {
          el.childNodes[0].textContent = current.toFixed(1);
        }

        if (progress < 1) {
          requestAnimationFrame(update);
        } else {
          el.childNodes[0].textContent = target; // Ensure final value is exact
        }
      }
      requestAnimationFrame(update);
    });
  }

  // ── lifecycle ──────────────────────────────────────────────────────
  let charts = [];

  function destroyAll() {
    charts.forEach(c => { try { c.destroy(); } catch (_) {} });
    charts = [];
  }

  function renderAll() {
    if (!window.Chart) return;
    const data = readData();
    if (!data) return;
    const theme = readTheme();
    applyGlobalDefaults(theme);
    destroyAll();

    const a = document.getElementById('chart-activity');
    const l = document.getElementById('chart-languages');
    const t = document.getElementById('chart-tags');
    if (a) charts.push(buildActivityChart(a, data, theme));
    if (l) charts.push(buildLanguageChart(l, data, theme));
    if (t && data.top_tags.length) charts.push(buildTagsChart(t, data, theme));
  }

  function init() {
    renderAll();
    animateStats();

    // Re-render on theme toggle so colors track --ink / --rule / --accent
    const observer = new MutationObserver((mutations) => {
      if (mutations.some(m => m.attributeName === 'data-theme')) {
        // Defer one frame so getComputedStyle picks up new values
        requestAnimationFrame(renderAll);
      }
    });
    observer.observe(document.documentElement, { attributes: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
