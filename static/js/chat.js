/* ─────────────────────────────────────────────────────────────────────────
   Chat with paper — editorial-tech UI

   Hooks any element with [data-chat-panel][data-paper-id] on the page.
   Loads history from /summarizer/paper/<pk>/chat/history/ on mount,
   posts new messages to /summarizer/paper/<pk>/chat/send/, renders
   assistant replies through marked.js for Markdown.

   Expected DOM (rendered server-side by _chat_panel.html):

   <section data-chat-panel data-paper-id="42"
            data-history-url="…" data-send-url="…" data-clear-url="…"
            data-csrf="…">
     <div class="chat-head">…</div>
     <div class="chat-empty" data-chat-empty>…</div>
     <div class="chat-messages" data-chat-messages></div>
     <div class="chat-error"   data-chat-error></div>
     <form class="chat-input"  data-chat-form>
       <textarea data-chat-input></textarea>
       <button   data-chat-send class="btn btn-primary">Send</button>
     </form>
   </section>
   ───────────────────────────────────────────────────────────────────────── */

(function () {
  'use strict';

  function esc(s) {
    return String(s)
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;').replace(/'/g, '&#039;');
  }

  function renderMarkdown(text) {
    if (window.marked && typeof window.marked.parse === 'function') {
      try {
        // Configure once (idempotent)
        if (!window.__markedConfigured) {
          window.marked.setOptions({
            gfm: true,
            breaks: true,
            mangle: false,
            headerIds: false,
          });
          window.__markedConfigured = true;
        }
        return window.marked.parse(text);
      } catch (e) {
        return esc(text).replace(/\n/g, '<br>');
      }
    }
    // Fallback: just escape + line breaks
    return esc(text).replace(/\n/g, '<br>');
  }

  function makeMsgEl(role, content) {
    const wrap = document.createElement('div');
    wrap.className = 'chat-msg chat-msg--' + (role === 'user' ? 'user' : 'assistant');

    const roleEl = document.createElement('div');
    roleEl.className = 'chat-role';
    roleEl.textContent = role === 'user' ? (window.i18n && window.i18n.you || 'You')
                                         : (window.i18n && window.i18n.assistant || 'Assistant');
    wrap.appendChild(roleEl);

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    if (role === 'assistant') {
      bubble.innerHTML = renderMarkdown(content);
    } else {
      bubble.textContent = content;
    }
    wrap.appendChild(bubble);

    return wrap;
  }

  function makeTypingEl() {
    const wrap = document.createElement('div');
    wrap.className = 'chat-msg chat-msg--assistant';
    wrap.dataset.typing = '1';

    const roleEl = document.createElement('div');
    roleEl.className = 'chat-role';
    roleEl.textContent = (window.i18n && window.i18n.assistant) || 'Assistant';
    wrap.appendChild(roleEl);

    const bubble = document.createElement('div');
    bubble.className = 'chat-bubble';
    bubble.innerHTML = '<span class="typing-indicator"><span></span><span></span><span></span></span>';
    wrap.appendChild(bubble);
    return wrap;
  }

  function initPanel(panel) {
    if (panel.dataset.chatBound) return;
    panel.dataset.chatBound = '1';

    const paperId    = panel.dataset.paperId;
    const historyUrl = panel.dataset.historyUrl;
    const sendUrl    = panel.dataset.sendUrl;
    const clearUrl   = panel.dataset.clearUrl;
    const csrf       = panel.dataset.csrf;

    const emptyEl    = panel.querySelector('[data-chat-empty]');
    const messagesEl = panel.querySelector('[data-chat-messages]');
    const errorEl    = panel.querySelector('[data-chat-error]');
    const form       = panel.querySelector('[data-chat-form]');
    const input      = panel.querySelector('[data-chat-input]');
    const sendBtn    = panel.querySelector('[data-chat-send]');
    const clearBtn   = panel.querySelector('[data-chat-clear]');

    // ── helpers ──────────────────────────────────────────────────────────
    function scrollToBottom() {
      // Run after a frame so newly-inserted nodes are measured first
      requestAnimationFrame(() => {
        messagesEl.scrollTop = messagesEl.scrollHeight;
      });
    }

    function showError(msg) {
      errorEl.textContent = '';
      const icon = document.createElement('i');
      icon.className = 'bi bi-exclamation-circle';
      errorEl.appendChild(icon);
      const span = document.createElement('span');
      span.textContent = ' ' + msg;
      errorEl.appendChild(span);
      errorEl.classList.add('is-shown');
    }
    function clearError() {
      errorEl.classList.remove('is-shown');
      errorEl.textContent = '';
    }

    function setEmptyVisible(visible) {
      if (!emptyEl) return;
      emptyEl.style.display = visible ? '' : 'none';
    }

    function appendMessage(role, content) {
      messagesEl.appendChild(makeMsgEl(role, content));
      setEmptyVisible(false);
      scrollToBottom();
    }

    function showTyping() {
      if (messagesEl.querySelector('[data-typing="1"]')) return;
      messagesEl.appendChild(makeTypingEl());
      scrollToBottom();
    }
    function hideTyping() {
      messagesEl.querySelectorAll('[data-typing="1"]').forEach(el => el.remove());
    }

    function setBusy(busy) {
      sendBtn.disabled = busy;
      input.disabled   = busy;
      if (clearBtn) clearBtn.disabled = busy;
    }

    function autoGrow() {
      input.style.height = 'auto';
      input.style.height = Math.min(input.scrollHeight, 200) + 'px';
    }

    // ── load existing history ────────────────────────────────────────────
    async function loadHistory() {
      try {
        const res = await fetch(historyUrl, { headers: { 'Accept': 'application/json' } });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        const data = await res.json();
        if (Array.isArray(data.messages) && data.messages.length) {
          data.messages.forEach(m => appendMessage(m.role, m.content));
        }
      } catch (e) {
        // Soft-fail on history — user can still send fresh messages
        console.warn('chat history load failed:', e);
      }
    }

    // ── send a message ──────────────────────────────────────────────────
    async function sendMessage(text) {
      clearError();
      if (!text.trim()) return;
      appendMessage('user', text);
      input.value = '';
      autoGrow();
      showTyping();
      setBusy(true);

      try {
        const res = await fetch(sendUrl, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken':  csrf,
            'Accept':       'application/json',
          },
          body: JSON.stringify({ content: text }),
        });
        const data = await res.json().catch(() => ({}));
        hideTyping();
        if (!res.ok) {
          const fallback = window.i18n.format(window.i18n.serverReturned, { code: res.status });
          showError(data.error || fallback);
          return;
        }
        appendMessage('assistant', data.reply);
      } catch (e) {
        hideTyping();
        showError(window.i18n.format(window.i18n.networkError, {
          detail: e.message || window.i18n.couldNotReachServer,
        }));
      } finally {
        setBusy(false);
        input.focus();
      }
    }

    // ── clear history ───────────────────────────────────────────────────
    async function clearHistory() {
      if (!confirm(window.i18n.confirmClearChat)) return;
      setBusy(true);
      try {
        const res = await fetch(clearUrl, {
          method: 'POST',
          headers: { 'X-CSRFToken': csrf, 'Accept': 'application/json' },
        });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        messagesEl.innerHTML = '';
        setEmptyVisible(true);
        clearError();
      } catch (e) {
        showError(window.i18n.format(window.i18n.couldNotClearHistory, { detail: e.message }));
      } finally {
        setBusy(false);
      }
    }

    // ── wire it up ───────────────────────────────────────────────────────
    form.addEventListener('submit', (e) => {
      e.preventDefault();
      sendMessage(input.value);
    });

    input.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage(input.value);
      }
    });
    input.addEventListener('input', autoGrow);

    if (clearBtn) clearBtn.addEventListener('click', clearHistory);

    // Suggestion chips: each [data-suggestion] inside the panel
    panel.querySelectorAll('[data-suggestion]').forEach(btn => {
      btn.addEventListener('click', () => {
        const text = btn.dataset.suggestion || btn.textContent.trim();
        input.value = text;
        autoGrow();
        sendMessage(text);
      });
    });

    loadHistory();
  }

  function init() {
    document.querySelectorAll('[data-chat-panel]').forEach(initPanel);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
