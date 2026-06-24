/* ── Exam Timer (global countdown) ──────────────────────────── */
function startExamTimer(durationMinutes, endTimeStr) {
  const timerEl = document.getElementById('timer-value');
  if (!timerEl) return;

  function update() {
    const now = new Date();
    const end = new Date(endTimeStr);
    const diff = Math.max(0, Math.floor((end - now) / 1000));
    const capDiff = Math.min(diff, durationMinutes * 60);

    const m = Math.floor(capDiff / 60).toString().padStart(2, '0');
    const s = (capDiff % 60).toString().padStart(2, '0');
    timerEl.textContent = `${m}:${s}`;

    timerEl.className = 'timer-value';
    if (capDiff < 60)  timerEl.classList.add('timer-crit');
    else if (capDiff < 300) timerEl.classList.add('timer-warn');

    if (capDiff <= 0) {
      // ── FIX: ارسال نهایی واقعی با پاسخ‌های ذخیره‌شده (savedAnswers/savedFiles) ──
      // فرم #exam-form معمولاً خالی است (فیلدهای مخفی فقط در صفحه پایان تزریق می‌شوند)،
      // پس submit() خام آن باعث از دست رفتن پاسخ‌های تایید شده می‌شد.
      if (typeof window.doFinalSubmit === 'function') {
        window.doFinalSubmit(true);
      } else {
        document.getElementById('exam-form')?.submit();
      }
      return;
    }
    setTimeout(update, 1000);
  }
  update();
}

/* ── Per-question timers ─────────────────────────────────────── */
/* منطق تایمر در exam_take.html مستقیماً مدیریت می‌شود          */
function startQuestionTimers() {}

/* ── Auto-save answers ───────────────────────────────────────── */
function setupAutoSave(examId) {
  const form = document.getElementById('exam-form');
  if (!form) return;

  // ── BUG FIX: clear any stale draft from a previous session ──
  // We store a session key (tab open time) so old drafts don't
  // auto-populate as "wrong answers" when a new exam session starts.
  const sessionKey = `exam_${examId}_session`;
  const draftKey   = `exam_${examId}_draft`;
  const thisSession = Date.now().toString();

  const storedSession = sessionStorage.getItem(sessionKey);
  if (!storedSession) {
    // New page load → clear any old localStorage draft
    localStorage.removeItem(draftKey);
    sessionStorage.setItem(sessionKey, thisSession);
  }

  form.addEventListener('change', () => {
    const fd = new FormData(form);
    const data = {};
    fd.forEach((v, k) => { data[k] = v; });
    localStorage.setItem(draftKey, JSON.stringify(data));
  });

  // Restore only within the same browser session
  if (storedSession) {
    const draft = localStorage.getItem(draftKey);
    if (draft) {
      try {
        const data = JSON.parse(draft);
        Object.entries(data).forEach(([k, v]) => {
          const el = form.querySelector(`[name="${k}"][value="${v}"]`) || form.querySelector(`[name="${k}"]`);
          if (el) { el.type === 'radio' ? (el.checked = el.value === v) : (el.value = v); }
        });
      } catch(e) { localStorage.removeItem(draftKey); }
    }
  }
}

/* ── Progress tracker ────────────────────────────────────────── */
function setupProgressTracker() {
  const radios = document.querySelectorAll('.question-card input[type=radio]');
  const textareas = document.querySelectorAll('.question-card textarea');
  const totalCards = document.querySelectorAll('.question-card').length;
  const progressFill = document.getElementById('progress-fill');
  const progressText = document.getElementById('progress-text');

  function update() {
    const answered = new Set();
    radios.forEach(r => { if (r.checked) answered.add(r.name); });
    textareas.forEach(t => { if (t.value.trim()) answered.add(t.name); });
    const pct = totalCards ? Math.round((answered.size / totalCards) * 100) : 0;
    if (progressFill) progressFill.style.width = pct + '%';
    if (progressText) progressText.textContent = `${answered.size} از ${totalCards} سوال پاسخ داده شد`;
  }

  radios.forEach(r => r.addEventListener('change', update));
  textareas.forEach(t => t.addEventListener('input', update));
  update();
}

/* ── Confirm submit ──────────────────────────────────────────── */
function confirmSubmit(e) {
  if (!confirm('آیا از ارسال پاسخ‌ها اطمینان دارید؟ این عمل قابل برگشت نیست.')) {
    e.preventDefault();
  } else {
    const examId = document.getElementById('exam-form')?.dataset.examId;
    if (examId) {
      localStorage.removeItem(`exam_${examId}_draft`);
      sessionStorage.removeItem(`exam_${examId}_session`);
    }
  }
}

/* ── Score ring animation ────────────────────────────────────── */
function animateScoreRing(score, total) {
  const circle = document.getElementById('score-circle');
  if (!circle) return;
  const r = 66;
  const circumference = 2 * Math.PI * r;
  const pct = total > 0 ? Math.max(0, Math.min(1, score / total)) : 0;

  circle.style.strokeDasharray = circumference;
  circle.style.strokeDashoffset = circumference;

  const dot = document.getElementById('score-circle-dot');
  if (dot) { dot.style.opacity = 0; }

  setTimeout(() => {
    circle.style.transition = 'stroke-dashoffset 1.4s cubic-bezier(.22,1,.36,1)';
    circle.style.strokeDashoffset = circumference * (1 - pct);

    // Move the leading dot to the end of the arc (SVG circle starts at 12 o'clock, rotated -90deg via CSS)
    if (dot) {
      const angle = pct * 360 - 90; // degrees, 0 at top after the -90deg ring rotation
      const rad = (angle * Math.PI) / 180;
      const cx = 86 + r * Math.cos(rad);
      const cy = 86 + r * Math.sin(rad);
      dot.setAttribute('cx', cx.toFixed(2));
      dot.setAttribute('cy', cy.toFixed(2));
      dot.style.transition = 'opacity .4s ease 1.1s, cx 1.4s cubic-bezier(.22,1,.36,1), cy 1.4s cubic-bezier(.22,1,.36,1)';
      dot.style.opacity = pct > 0.02 ? 1 : 0;
    }
  }, 120);

  // Animated count-up for the big number
  const sb = document.querySelector('.score-big');
  if (sb) {
    const target = parseFloat(sb.dataset.target ?? score) || 0;
    const duration = 1100;
    const start = performance.now();
    const startVal = 0;
    function tick(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const val = startVal + (target - startVal) * eased;
      sb.textContent = val.toFixed(1);
      if (t < 1) requestAnimationFrame(tick);
      else sb.textContent = target.toFixed(1);
    }
    requestAnimationFrame(tick);
  }
}

/* ── Toast notifications ─────────────────────────────────────── */
function showToast(msg, type = 'info') {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';

  const darkColors  = { info: '#00d4ff',  success: '#00e5a0', warning: '#ffb347', error: '#ff5f6d' };
  const lightColors = { info: '#6c3ce1',  success: '#059669', warning: '#d97706', error: '#e11d48' };
  const lightBg     = { info: 'rgba(108,60,225,.10)', success: 'rgba(5,150,105,.10)',
                        warning: 'rgba(245,158,11,.10)', error: 'rgba(225,29,72,.10)' };
  const lightBorder = { info: 'rgba(108,60,225,.30)', success: 'rgba(5,150,105,.30)',
                        warning: 'rgba(245,158,11,.35)', error: 'rgba(225,29,72,.30)' };

  const icons = { info: 'ℹ️', success: '✅', warning: '⚠️', error: '❌' };

  const color  = isLight ? lightColors[type] : darkColors[type];
  const bg     = isLight ? lightBg[type]     : '#1a1a24';
  const border = isLight ? lightBorder[type] : `1px solid ${darkColors[type]}`;
  const shadow = isLight
    ? `0 6px 24px ${lightBorder[type]}, 0 2px 8px rgba(0,0,0,.08)`
    : '0 4px 20px rgba(0,0,0,.6)';
  const textColor = isLight ? color : color;
  const blur = isLight ? 'backdrop-filter:blur(12px);-webkit-backdrop-filter:blur(12px);' : '';

  const toast = document.createElement('div');
  toast.style.cssText = `
    position:fixed; bottom:80px; left:24px; z-index:9999;
    background:${bg}; border:1px solid ${border};
    color:${textColor}; padding:13px 18px; border-radius:10px;
    font-size:.88rem; font-family:Vazirmatn,sans-serif;
    box-shadow:${shadow};
    animation:fadeInUp .25s ease both;
    direction:rtl; display:flex; align-items:center; gap:8px;
    max-width:320px;
    ${isLight ? 'background:' + bg + ';' : ''}
    ${blur}
  `;
  toast.innerHTML = `<span>${icons[type]}</span><span>${msg}</span>`;
  document.body.appendChild(toast);
  setTimeout(() => {
    toast.style.transition = 'opacity .3s ease, transform .3s ease';
    toast.style.opacity = '0';
    toast.style.transform = 'translateY(8px)';
    setTimeout(() => toast.remove(), 300);
  }, 3200);
}

/* ── Theme Toggle ────────────────────────────────────────────── */
(function initTheme() {
  const saved = localStorage.getItem('exam_theme') || 'dark';
  if (saved === 'light') document.documentElement.setAttribute('data-theme', 'light');
})();

function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme') || 'dark';
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('exam_theme', next);
}

function injectThemeToggle() {
  if (document.getElementById('theme-toggle-btn')) return;
  const btn = document.createElement('button');
  btn.id = 'theme-toggle-btn';
  btn.className = 'theme-toggle';
  btn.setAttribute('title', 'تغییر تم');
  btn.setAttribute('aria-label', 'تغییر تم روشن/تاریک');
  btn.innerHTML = '<span class="icon-dark">🌙</span><span class="icon-light">☀️</span>';
  btn.addEventListener('click', toggleTheme);
  document.body.appendChild(btn);
}

/* ── DOM Ready ───────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('.fade-in').forEach((el, i) => {
    el.style.animationDelay = (i * 0.05) + 's';
  });

  const path = window.location.pathname;
  document.querySelectorAll('.nav-item').forEach(item => {
    if (item.getAttribute('href') === path) item.classList.add('active');
  });

  document.querySelectorAll('.role-badge').forEach(b => {
    const r = b.dataset.role;
    b.className = `badge role-${r}`;
    const labels = { admin: 'مدیر', teacher: 'استاد', student: 'دانشجو' };
    b.textContent = labels[r] || r;
  });

  injectThemeToggle();
});
