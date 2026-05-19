/* Academic Summarizer — Main JS v2 */
'use strict';

/* ---- Theme: applied immediately to avoid flash ---- */
(function () {
  const stored = localStorage.getItem('as-theme');
  const preferred = stored || (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.setAttribute('data-theme', preferred);
})();

function applyTheme(theme) {
  document.documentElement.setAttribute('data-theme', theme);
  const icon = document.getElementById('theme-icon');
  if (icon) icon.className = theme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';
  localStorage.setItem('as-theme', theme);
}

/* ---- DOM Ready ---- */
document.addEventListener('DOMContentLoaded', () => {

  /* Sync icon with current theme */
  const currentTheme = document.documentElement.getAttribute('data-theme') || 'light';
  const icon = document.getElementById('theme-icon');
  if (icon) icon.className = currentTheme === 'dark' ? 'bi bi-sun-fill' : 'bi bi-moon-fill';

  /* Theme toggle button */
  const themeToggle = document.getElementById('theme-toggle');
  if (themeToggle) {
    themeToggle.addEventListener('click', () => {
      const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
      applyTheme(next);
    });
  }

  /* Follow OS preference changes if user hasn't manually set a theme */
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', e => {
    if (!localStorage.getItem('as-theme')) applyTheme(e.matches ? 'dark' : 'light');
  });

  /* ---- Auto-dismiss alerts ---- */
  document.querySelectorAll('.alert.alert-dismissible').forEach(el => {
    setTimeout(() => bootstrap.Alert.getOrCreateInstance(el)?.close(), 6000);
  });

  /* ---- Bootstrap Tooltips ---- */
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map(function (tooltipTriggerEl) {
    return new bootstrap.Tooltip(tooltipTriggerEl);
  });

  /* ---- Navbar search: debounce-and-submit (300 ms) ---- */
  document.querySelectorAll('form[data-debounce-search]').forEach(form => {
    const input = form.querySelector('input[name="query"]');
    if (!input) return;
    let timer = null;
    let last = input.value;
    input.addEventListener('input', () => {
      const cur = input.value;
      clearTimeout(timer);
      timer = setTimeout(() => {
        if (cur === last) return;
        last = cur;
        form.submit();
      }, 300);
    });
    // Enter still submits immediately (native form behavior preserved)
  });

  /* ---- ⌘K / Ctrl+K → Command Palette ---- */
  const paletteModalEl = document.getElementById('commandPalette');
  const paletteModal = paletteModalEl ? new bootstrap.Modal(paletteModalEl) : null;
  const paletteInput = document.getElementById('palette-input');
  const paletteResults = document.getElementById('palette-results');
  let paletteSelectedIndex = -1;

  const commands = [
    { icon: 'bi-house', label: window.i18n.home || 'Home', url: '/' },
    { icon: 'bi-speedometer2', label: window.i18n.dashboard || 'Dashboard', url: '/dashboard/' },
    { icon: 'bi-files', label: window.i18n.papers || 'Papers', url: '/papers/' },
    { icon: 'bi-cloud-upload', label: window.i18n.upload || 'Upload', url: '/papers/upload/' },
    { icon: 'bi-clock-history', label: window.i18n.history || 'History', url: '/summarizer/history/' },
    { icon: 'bi-box-arrow-right', label: window.i18n.logout || 'Sign out', url: '/logout/', method: 'POST' }
  ];

  function renderPaletteResults(filter = '') {
    if (!paletteResults) return;
    const filtered = commands.filter(c => 
      c.label.toLowerCase().includes(filter.toLowerCase())
    );
    paletteResults.innerHTML = filtered.map((c, i) => `
      <div class="palette-item ${i === paletteSelectedIndex ? 'is-selected' : ''}" data-index="${i}" data-url="${c.url}" data-method="${c.method || 'GET'}">
        <i class="bi ${c.icon}"></i>
        <span>${c.label}</span>
        <div class="spacer"></div>
        <span class="shortcut">↵</span>
      </div>
    `).join('');

    paletteResults.querySelectorAll('.palette-item').forEach(item => {
      item.addEventListener('click', () => executeCommand(item.dataset.url, item.dataset.method));
    });
  }

  function executeCommand(url, method) {
    if (method === 'POST') {
      const form = document.createElement('form');
      form.method = 'POST';
      form.action = url;
      const csrf = document.querySelector('[name=csrfmiddlewaretoken]');
      if (csrf) {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'csrfmiddlewaretoken';
        input.value = csrf.value;
        form.appendChild(input);
      }
      document.body.appendChild(form);
      form.submit();
    } else {
      window.location.href = url;
    }
  }

  document.addEventListener('keydown', (e) => {
    // ⌘K / Ctrl+K
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      if (paletteModal) {
        paletteModal.show();
        setTimeout(() => paletteInput.focus(), 150);
        paletteSelectedIndex = 0;
        renderPaletteResults();
      }
    }
    // ?
    if (e.key === '?' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
      const shortcutsModalEl = document.getElementById('shortcutsModal');
      if (shortcutsModalEl) {
        const shortcutsModal = new bootstrap.Modal(shortcutsModalEl);
        shortcutsModal.show();
      }
    }
    // ESC to close palette if focused on input
    if (e.key === 'Escape' && document.activeElement === paletteInput) {
      paletteModal?.hide();
    }
    // Arrow navigation in palette
    if (paletteModalEl?.classList.contains('show')) {
      const items = paletteResults.querySelectorAll('.palette-item');
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        paletteSelectedIndex = (paletteSelectedIndex + 1) % items.length;
        renderPaletteResults(paletteInput.value);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        paletteSelectedIndex = (paletteSelectedIndex - 1 + items.length) % items.length;
        renderPaletteResults(paletteInput.value);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const selected = paletteResults.querySelector('.palette-item.is-selected');
        if (selected) executeCommand(selected.dataset.url, selected.dataset.method);
      }
    }
  });

  if (paletteInput) {
    paletteInput.addEventListener('input', () => {
      paletteSelectedIndex = 0;
      renderPaletteResults(paletteInput.value);
    });
  }

  /* ---- Reading Progress Bar ---- */
  const progressBar = document.getElementById('reading-progress');
  if (progressBar) {
    window.addEventListener('scroll', () => {
      const winScroll = document.body.scrollTop || document.documentElement.scrollTop;
      const height = document.documentElement.scrollHeight - document.documentElement.clientHeight;
      const scrolled = (winScroll / height) * 100;
      progressBar.style.width = scrolled + '%';
    });
  }

  /* ---- Drag & Drop Upload ---- */
  const dropZone      = document.getElementById('drop-zone');
  const fileInput     = document.getElementById('pdf-file-input');
  const dropDefault   = document.getElementById('drop-default');
  const filePreview   = document.getElementById('file-preview');
  const previewName   = document.getElementById('file-preview-name');
  const previewSize   = document.getElementById('file-preview-size');
  const clearFileBtn  = document.getElementById('clear-file');
  const uploadForm    = document.getElementById('upload-form');
  const progressSteps = document.getElementById('progress-steps');

  if (dropZone && fileInput) {
    dropZone.addEventListener('click', e => {
      if (!e.target.closest('#clear-file') && !e.target.closest('#file-preview')) {
        fileInput.click();
      }
    });

    ['dragenter', 'dragover'].forEach(evt =>
      dropZone.addEventListener(evt, e => { e.preventDefault(); dropZone.classList.add('drag-over'); })
    );

    ['dragleave', 'dragend'].forEach(evt =>
      dropZone.addEventListener(evt, e => { e.preventDefault(); dropZone.classList.remove('drag-over'); })
    );

    dropZone.addEventListener('drop', e => {
      e.preventDefault();
      dropZone.classList.remove('drag-over');
      const file = e.dataTransfer.files[0];
      if (!file) return;
      if (!file.name.toLowerCase().endsWith('.pdf')) {
        showToast(window.i18n.onlyPdfAccepted, 'warning');
        return;
      }
      if (file.size > 50 * 1024 * 1024) {
        showToast(window.i18n.fileTooLarge, 'danger');
        return;
      }
      assignFile(file);
      // Programmatic .files assignment doesn't fire a native change event,
      // so notify other listeners (AI tag preview, file analyzer) explicitly.
      fileInput.dispatchEvent(new Event('change', { bubbles: true }));
    });

    fileInput.addEventListener('change', () => {
      if (fileInput.files.length) assignFile(fileInput.files[0]);
    });

    function assignFile(file) {
      /* Put file into the input if it came via drag-drop */
      if (file !== fileInput.files[0]) {
        try {
          const dt = new DataTransfer();
          dt.items.add(file);
          fileInput.files = dt.files;
        } catch (_) { /* fallback: user can re-select */ }
      }

      dropZone.classList.add('has-file');
      if (dropDefault) dropDefault.style.display = 'none';

      if (filePreview) {
        filePreview.classList.add('visible');
        if (previewName) previewName.textContent = file.name;
        if (previewSize) previewSize.textContent = fmtSize(file.size);
      }

      /* Auto-fill title from filename if blank */
      const titleInput = document.getElementById('id_title');
      if (titleInput && !titleInput.value.trim()) {
        titleInput.value = file.name.replace(/\.pdf$/i, '').replace(/[-_]+/g, ' ').trim();
      }
    }

    if (clearFileBtn) {
      clearFileBtn.addEventListener('click', e => {
        e.stopPropagation();
        fileInput.value = '';
        dropZone.classList.remove('has-file');
        if (dropDefault) dropDefault.style.display = '';
        if (filePreview) filePreview.classList.remove('visible');
      });
    }
  }

  /* ---- Upload form: progress animation ---- */
  if (uploadForm) {
    uploadForm.addEventListener('submit', () => {
      const fi = document.getElementById('pdf-file-input');
      if (!fi || !fi.files.length) return;

      const btn = uploadForm.querySelector('[type="submit"]');
      if (btn) {
        btn.disabled = true;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>' + window.i18n.processing;
      }

      if (progressSteps) {
        progressSteps.classList.add('visible');
        runStepAnimation(progressSteps.querySelectorAll('.step-item'));
      }
    });
  }

  function runStepAnimation(steps) {
    let i = 0;
    (function next() {
      if (i >= steps.length) return;
      if (i > 0) { steps[i - 1].classList.remove('active'); steps[i - 1].classList.add('done'); }
      steps[i].classList.add('active');
      i++;
      if (i < steps.length) setTimeout(next, 1400 + Math.random() * 800);
    })();
  }

  /* ---- Copy share link ---- */
  document.querySelectorAll('.copy-share-link').forEach(btn => {
    btn.addEventListener('click', async () => {
      const input = document.getElementById('share-link-input');
      if (!input) return;
      const ok = await copyToClipboard(input.value);
      if (ok) {
        const orig = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check2 me-1"></i>' + window.i18n.copiedExcl;
        btn.classList.replace('btn-outline-secondary', 'btn-success');
        showToast(window.i18n.shareLinkCopied, 'success');
        setTimeout(() => {
          btn.innerHTML = orig;
          btn.classList.replace('btn-success', 'btn-outline-secondary');
        }, 2200);
      } else {
        showToast(window.i18n.couldNotCopy, 'danger');
      }
    });
  });

});

/* ---- Clipboard helper (callable from anywhere) ----
   Tries the modern async Clipboard API first; falls back to a hidden
   textarea + execCommand on insecure contexts (http://) or older browsers.
   Returns a Promise<boolean> — true on success, false on failure. */
async function copyToClipboard(text) {
  // Modern path — requires a secure context (https:// or localhost)
  if (window.isSecureContext && navigator.clipboard && navigator.clipboard.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) { /* fall through to legacy */ }
  }
  // Legacy path — works on http:// inside a user gesture
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '0';
    ta.style.left = '0';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    ta.setSelectionRange(0, text.length);
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch (e) {
    return false;
  }
}
window.copyToClipboard = copyToClipboard;

/* ---- Toast helper (callable from anywhere) ---- */
function showToast(message, type = 'info', title = '') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const i18n = window.i18n || {};
  const cfg = {
    success: { icon: 'check-circle-fill text-success',       label: i18n.toastSuccess || 'Success' },
    warning: { icon: 'exclamation-triangle-fill text-warning', label: i18n.toastWarning || 'Warning' },
    danger:  { icon: 'exclamation-circle-fill text-danger',  label: i18n.toastError   || 'Error' },
    error:   { icon: 'exclamation-circle-fill text-danger',  label: i18n.toastError   || 'Error' },
    info:    { icon: 'info-circle-fill text-info',           label: i18n.toastInfo    || 'Info' },
  };

  const { icon, label } = cfg[type] || cfg.info;
  const id = `toast-${Date.now()}-${Math.random().toString(36).slice(2)}`;

  container.insertAdjacentHTML('beforeend', `
    <div id="${id}" class="toast align-items-center mb-2" role="alert" aria-live="assertive" aria-atomic="true">
      <div class="toast-header">
        <i class="bi bi-${icon} me-2 fs-6"></i>
        <strong class="me-auto">${title || label}</strong>
        <button type="button" class="btn-close" data-bs-dismiss="toast" aria-label="Close"></button>
      </div>
      <div class="toast-body">${message}</div>
    </div>`
  );

  const el = document.getElementById(id);
  const toast = new bootstrap.Toast(el, { delay: 5000 });
  toast.show();
  el.addEventListener('hidden.bs.toast', () => el.remove());
}

/* ---- Utility ---- */
function fmtSize(bytes) {
  if (bytes < 1024)          return `${bytes} B`;
  if (bytes < 1024 * 1024)   return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}
