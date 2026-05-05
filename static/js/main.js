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
        showToast('Only PDF files are accepted.', 'warning');
        return;
      }
      if (file.size > 50 * 1024 * 1024) {
        showToast('File is larger than 50 MB.', 'danger');
        return;
      }
      assignFile(file);
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
        btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status"></span>Processing…';
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
    btn.addEventListener('click', () => {
      const input = document.getElementById('share-link-input');
      if (!input) return;
      navigator.clipboard.writeText(input.value).then(() => {
        const orig = btn.innerHTML;
        btn.innerHTML = '<i class="bi bi-check2 me-1"></i>Copied!';
        btn.classList.replace('btn-outline-secondary', 'btn-success');
        setTimeout(() => {
          btn.innerHTML = orig;
          btn.classList.replace('btn-success', 'btn-outline-secondary');
        }, 2200);
      }).catch(() => {
        input.select();
        document.execCommand('copy');
      });
    });
  });

});

/* ---- Toast helper (callable from anywhere) ---- */
function showToast(message, type = 'info', title = '') {
  const container = document.getElementById('toast-container');
  if (!container) return;

  const cfg = {
    success: { icon: 'check-circle-fill text-success', label: 'Success' },
    warning: { icon: 'exclamation-triangle-fill text-warning', label: 'Warning' },
    danger:  { icon: 'exclamation-circle-fill text-danger',  label: 'Error' },
    error:   { icon: 'exclamation-circle-fill text-danger',  label: 'Error' },
    info:    { icon: 'info-circle-fill text-info',           label: 'Info' },
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
