/* ─────────────────────────────────────────────────────────────────────────
   Loading overlay (Wave 6)

   Activates on submit of any <form data-confirm-loading>.
   Used by upload + summarize forms, where Groq inference is synchronous
   inside the request thread (~10–30 s). Shows a full-screen blurred
   overlay with three progress steps and an indeterminate violet bar.

   Visible until the navigation completes (page reload / redirect from
   form_valid → success page).
   ───────────────────────────────────────────────────────────────────────── */

(function () {
  'use strict';

  const STEPS = [
    { id: 'step-1', text: 'Matn ajratilmoqda…',     hold: 2500 },
    { id: 'step-2', text: 'AI tahlil qilmoqda…',    hold: 18000 },
    { id: 'step-3', text: 'Xulosa yaratilmoqda…',   hold: null  }, // stays until response
  ];

  function buildOverlay() {
    if (document.getElementById('wow-loading-overlay')) return;
    const ov = document.createElement('div');
    ov.id = 'wow-loading-overlay';
    ov.className = 'wow-overlay';
    ov.innerHTML = `
      <div class="wow-overlay-inner" role="status" aria-live="polite">
        <h3>Summarising your paper</h3>
        <p class="ov-sub">groq · llama-3.3-70b · usually 10–30 s</p>
        <div class="wow-progress" aria-hidden="true"></div>
        <ul class="wow-steps" id="wow-loading-steps">
          <li data-step="step-1"><span class="step-dot">1</span><span>Matn ajratilmoqda…</span></li>
          <li data-step="step-2"><span class="step-dot">2</span><span>AI tahlil qilmoqda…</span></li>
          <li data-step="step-3"><span class="step-dot">3</span><span>Xulosa yaratilmoqda…</span></li>
        </ul>
      </div>
    `;
    document.body.appendChild(ov);
  }

  function advance(stepIdx) {
    const items = document.querySelectorAll('#wow-loading-steps li');
    items.forEach((el, i) => {
      el.classList.remove('is-active', 'is-done');
      if (i < stepIdx) el.classList.add('is-done');
      if (i === stepIdx) el.classList.add('is-active');
    });
  }

  function show() {
    buildOverlay();
    const ov = document.getElementById('wow-loading-overlay');
    ov.classList.add('is-active');
    document.body.style.overflow = 'hidden';

    advance(0);
    let t1 = setTimeout(() => advance(1), STEPS[0].hold);
    let t2 = setTimeout(() => advance(2), STEPS[0].hold + STEPS[1].hold);
    ov._timers = [t1, t2];
  }

  function attach() {
    document.querySelectorAll('form[data-confirm-loading]').forEach(form => {
      // Avoid double-binding (Bootstrap re-render etc.)
      if (form.dataset.confirmLoadingBound) return;
      form.dataset.confirmLoadingBound = '1';

      form.addEventListener('submit', (e) => {
        // Don't trigger overlay if form is invalid (HTML5 validation will block submit)
        if (form.checkValidity && !form.checkValidity()) return;

        // Disable the submit button to prevent double-submission
        const btn = form.querySelector('[type="submit"]');
        if (btn) {
          btn.disabled = true;
          btn.dataset.origHtml = btn.innerHTML;
          btn.innerHTML = '<span style="display:inline-flex; align-items:center; gap:6px;"><span class="spinner-border spinner-border-sm" role="status" style="width:12px; height:12px; border-width:2px;"></span> Working…</span>';
        }

        show();
        // Keep the overlay visible through the navigation.
        // window.pageshow on the next page will clean up if bfcache restores.
      });
    });
  }

  // Hide overlay if user comes back via back/forward cache
  window.addEventListener('pageshow', (e) => {
    if (e.persisted) {
      const ov = document.getElementById('wow-loading-overlay');
      if (ov) {
        ov.classList.remove('is-active');
        (ov._timers || []).forEach(clearTimeout);
        document.body.style.overflow = '';
      }
      // Restore any disabled submit buttons
      document.querySelectorAll('form[data-confirm-loading] [type="submit"][data-orig-html]').forEach(btn => {
        btn.disabled = false;
        btn.innerHTML = btn.dataset.origHtml;
        delete btn.dataset.origHtml;
      });
    }
  });

  document.addEventListener('DOMContentLoaded', attach);
})();
