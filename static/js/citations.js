/* ─────────────────────────────────────────────────────────────────────────
   Cite this paper — editorial-tech UI

   Loads APA/MLA/IEEE/BibTeX from GET /papers/<pk>/citations/ on mount.
   Format switching is client-side after the initial fetch.

   Expected DOM (rendered by _citation_panel.html):

   <section data-cite-panel data-paper-id="…"
            data-citations-url="…" data-bib-url="…">
     <div class="cite-tabs">
       <button data-cite-tab="apa"    class="chip is-on">APA</button>
       <button data-cite-tab="mla"    class="chip">MLA</button>
       <button data-cite-tab="ieee"   class="chip">IEEE</button>
       <button data-cite-tab="bibtex" class="chip">BibTeX</button>
     </div>
     <pre data-cite-code></pre>
     <button data-cite-copy>Copy</button>
     <a    data-cite-download>Download .bib</a>
   </section>
   ───────────────────────────────────────────────────────────────────────── */

(function () {
  'use strict';

  function initPanel(panel) {
    if (panel.dataset.citeBound) return;
    panel.dataset.citeBound = '1';

    const url        = panel.dataset.citationsUrl;
    const tabs       = panel.querySelectorAll('[data-cite-tab]');
    const codeEl     = panel.querySelector('[data-cite-code]');
    const copyBtn    = panel.querySelector('[data-cite-copy]');
    const downloadEl = panel.querySelector('[data-cite-download]');

    let citations = null;   // { apa, mla, ieee, bibtex }
    let active    = 'apa';

    function setActive(format) {
      active = format;
      tabs.forEach(t => {
        const on = t.dataset.citeTab === format;
        t.classList.toggle('is-on', on);
        t.setAttribute('aria-selected', on ? 'true' : 'false');
      });
      // Only show the download button when BibTeX is active
      if (downloadEl) downloadEl.style.display = (format === 'bibtex') ? '' : 'none';
      render();
    }

    function render() {
      if (!citations) {
        codeEl.textContent = 'Loading citation…';
        return;
      }
      const text = citations[active] || '';
      codeEl.textContent = text;
    }

    async function load() {
      try {
        const res = await fetch(url, { headers: { 'Accept': 'application/json' } });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        citations = await res.json();
        render();
      } catch (e) {
        codeEl.textContent = 'Could not load citations: ' + e.message;
        codeEl.classList.add('cite-error');
      }
    }

    // Tab switching
    tabs.forEach(t => {
      t.addEventListener('click', () => setActive(t.dataset.citeTab));
    });

    // Copy current format
    if (copyBtn) {
      copyBtn.addEventListener('click', async () => {
        if (!citations) return;
        const text = citations[active] || '';
        const ok = await window.copyToClipboard(text);
        if (ok) {
          const orig = copyBtn.innerHTML;
          copyBtn.innerHTML = '<i class="bi bi-check2"></i> Copied';
          copyBtn.classList.add('is-copied');
          if (typeof window.showToast === 'function') {
            window.showToast(active.toUpperCase() + ' citation copied to clipboard.', 'success');
          }
          setTimeout(() => {
            copyBtn.innerHTML = orig;
            copyBtn.classList.remove('is-copied');
          }, 1800);
        } else if (typeof window.showToast === 'function') {
          window.showToast('Could not copy — please copy manually.', 'danger');
        }
      });
    }

    // Initial state: BibTeX-only button hidden until tab is active
    setActive('apa');
    load();
  }

  function init() {
    document.querySelectorAll('[data-cite-panel]').forEach(initPanel);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
