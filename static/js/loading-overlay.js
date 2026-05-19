/* ─────────────────────────────────────────────────────────────────────────
   Loading overlay — editorial-tech (Wave 6)

   Triggered on submit of any <form data-confirm-loading>. The Groq inference
   call is synchronous on the server (~10–30 s); this overlay keeps the user
   engaged with a 3-stage stepped progress display in the editorial style.

   Each step has a primary label (Uzbek, user's preference from earlier
   spec) and a mono detail subtitle in the design's voice.
   ───────────────────────────────────────────────────────────────────────── */

(function () {
  'use strict';

  function _t(key, fallback) {
    return (window.i18n && window.i18n[key]) || fallback;
  }

  const STEPS = [
    { labelKey: 'overlayStep1', labelFallback: 'Extracting text…',
      detail: 'parsing pdf · pdfplumber',     hold: 2400  },
    { labelKey: 'overlayStep2', labelFallback: 'AI is analyzing…',
      detail: 'groq lpu · llama-3.3-70b',     hold: 18000 },
    { labelKey: 'overlayStep3', labelFallback: 'Generating summary…',
      detail: 'validating · serializing',     hold: null  }, // sticks until response
  ];

  let timers = [];
  let tickTimer = null;
  let startedAt = 0;

  function buildOverlay() {
    if (document.getElementById('wow-loading-overlay')) return;
    const ov = document.createElement('div');
    ov.id = 'wow-loading-overlay';
    ov.className = 'loading-overlay';
    ov.setAttribute('role', 'status');
    ov.setAttribute('aria-live', 'polite');
    ov.style.display = 'none';
    ov.innerHTML = `
      <div class="loading-card">
        <div class="h-row" style="gap: 10px; margin-bottom: 22px;">
          <span class="pill is-run"><span class="dot"></span>processing</span>
          <span class="eyebrow" id="wow-elapsed">elapsed · 0.0s</span>
        </div>

        <div class="loading-title">${_t('overlayTitle', 'Summarizing your paper…')}</div>
        <p class="loading-sub">${_t('overlaySubtitle', "Don't close this tab. Most jobs finish in 15–25 seconds.")}</p>

        <div class="loading-steps" id="wow-loading-steps">
          ${STEPS.map((s, i) => `
            <div class="loading-step" data-idx="${i}">
              <span class="step-bullet">${(i + 1).toString().padStart(2, '0')}</span>
              <div>
                <div class="step-label">${_t(s.labelKey, s.labelFallback)}</div>
                <div class="step-detail">${s.detail}</div>
              </div>
              <span class="step-state">QUEUED</span>
            </div>
          `).join('')}
        </div>

        <!-- Skeleton Content Simulation -->
        <div style="margin: 24px 0;">
          <div class="skeleton-block w-75"></div>
          <div class="skeleton-block"></div>
          <div class="skeleton-block w-50"></div>
        </div>

        <div class="progress-track"><div class="progress-fill" id="wow-progress" style="width: 4%;"></div></div>
        <div class="progress-meta">
          <span id="wow-pct">4% · 0.0s elapsed</span>
          <span>llama-3.3-70b · groq lpu</span>
        </div>
      </div>
    `;
    document.body.appendChild(ov);
  }

  function setStep(idx, done = false) {
    const items = document.querySelectorAll('#wow-loading-steps .loading-step');
    items.forEach((el, i) => {
      const state = el.querySelector('.step-state');
      const bullet = el.querySelector('.step-bullet');
      el.classList.remove('is-active', 'is-done');
      if (i < idx || (i === idx && done)) {
        el.classList.add('is-done');
        if (state) state.textContent = 'DONE';
        if (bullet) bullet.innerHTML = '<i class="bi bi-check" style="font-size: 12px;"></i>';
      } else if (i === idx) {
        el.classList.add('is-active');
        if (state) state.textContent = 'RUNNING';
        if (bullet) bullet.textContent = (i + 1).toString().padStart(2, '0');
      } else {
        if (state) state.textContent = 'QUEUED';
        if (bullet) bullet.textContent = (i + 1).toString().padStart(2, '0');
      }
    });
  }

  function setProgress(pct) {
    const fill = document.getElementById('wow-progress');
    const pctEl = document.getElementById('wow-pct');
    if (fill) fill.style.width = pct + '%';
    const elapsed = ((Date.now() - startedAt) / 1000).toFixed(1);
    if (pctEl) pctEl.textContent = `${pct}% · ${elapsed}s elapsed`;
  }

  function startTicker() {
    if (tickTimer) clearInterval(tickTimer);
    tickTimer = setInterval(() => {
      const el = document.getElementById('wow-elapsed');
      const elapsed = ((Date.now() - startedAt) / 1000).toFixed(1);
      if (el) el.textContent = `elapsed · ${elapsed}s`;
    }, 100);
  }

  function show() {
    buildOverlay();
    const ov = document.getElementById('wow-loading-overlay');
    if (!ov) return;
    ov.style.display = 'grid';
    document.body.style.overflow = 'hidden';

    startedAt = Date.now();
    startTicker();
    setStep(0);
    setProgress(4);

    // Scheduled progression mimicking the design prototype
    timers.forEach(clearTimeout);
    timers = [
      setTimeout(() => { setProgress(12); },                           400),
      setTimeout(() => { setStep(1); setProgress(34); },               STEPS[0].hold),
      setTimeout(() => { setProgress(62); },                           STEPS[0].hold + 6000),
      setTimeout(() => { setStep(2); setProgress(86); },               STEPS[0].hold + STEPS[1].hold),
      setTimeout(() => { setProgress(94); },                           STEPS[0].hold + STEPS[1].hold + 2000),
    ];
  }

  function hide() {
    const ov = document.getElementById('wow-loading-overlay');
    if (ov) ov.style.display = 'none';
    document.body.style.overflow = '';
    timers.forEach(clearTimeout); timers = [];
    if (tickTimer) { clearInterval(tickTimer); tickTimer = null; }
  }

  function attach() {
    document.querySelectorAll('form[data-confirm-loading]').forEach(form => {
      if (form.dataset.confirmLoadingBound) return;
      form.dataset.confirmLoadingBound = '1';

      form.addEventListener('submit', () => {
        if (form.checkValidity && !form.checkValidity()) return;

        // Lock the submit button to prevent double-fires
        const btn = form.querySelector('[type="submit"]');
        if (btn) {
          btn.disabled = true;
          btn.dataset.origHtml = btn.innerHTML;
          btn.innerHTML = '<span style="display:inline-flex; align-items:center; gap:8px;"><span class="spinner-border spinner-border-sm" role="status" style="width:12px; height:12px; border-width:2px;"></span> ' + _t('overlayWorking', 'Working…') + '</span>';
        }

        show();
      });
    });
  }

  // Restore on back/forward cache
  window.addEventListener('pageshow', (e) => {
    if (e.persisted) {
      hide();
      document.querySelectorAll('form[data-confirm-loading] [type="submit"][data-orig-html]').forEach(btn => {
        btn.disabled = false;
        btn.innerHTML = btn.dataset.origHtml;
        delete btn.dataset.origHtml;
      });
    }
  });

  document.addEventListener('DOMContentLoaded', attach);
})();
