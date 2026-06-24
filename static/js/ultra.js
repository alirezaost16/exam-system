/* ════════════════════════════════════════════════════════
   EXAM SYSTEM — Ultra Animations JS
   جاوا اسکریپت انیمیشن‌های فوق‌العاده
   ════════════════════════════════════════════════════════ */

'use strict';

/* ── ۱. Ripple effect روی دکمه‌ها ── */
function addRippleEffect() {
  document.querySelectorAll('.btn-primary, .btn-secondary, .btn-confirm').forEach(btn => {
    btn.addEventListener('click', function(e) {
      const ripple = document.createElement('span');
      ripple.className = 'ripple-effect';
      const rect = this.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      ripple.style.cssText = `
        width: ${size}px; height: ${size}px;
        left: ${e.clientX - rect.left - size/2}px;
        top:  ${e.clientY - rect.top  - size/2}px;
      `;
      this.appendChild(ripple);
      setTimeout(() => ripple.remove(), 700);
    });
  });
}

/* ── ۲. شمارنده متحرک عدد ── */
function animateCounter(el, target, duration = 1200) {
  const start = performance.now();
  const startVal = 0;

  function update(now) {
    const elapsed = now - start;
    const progress = Math.min(elapsed / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3); // ease-out-cubic
    const current = Math.round(startVal + (target - startVal) * eased);
    el.textContent = current;
    if (progress < 1) requestAnimationFrame(update);
    else el.textContent = target;
  }
  requestAnimationFrame(update);
}

function initCounters() {
  document.querySelectorAll('.stat-value').forEach(el => {
    const text = el.textContent.trim();
    const num = parseFloat(text.replace(/[^0-9.]/g, ''));
    if (!isNaN(num) && num > 0 && num < 10000) {
      const suffix = text.replace(/[0-9.]/g, '').trim();
      const hasDecimal = text.includes('.');
      
      el.setAttribute('data-target', num);
      el.textContent = '0';
      
      setTimeout(() => {
        const start = performance.now();
        function update(now) {
          const elapsed = now - start;
          const progress = Math.min(elapsed / 1000, 1);
          const eased = 1 - Math.pow(1 - progress, 3);
          const current = num * eased;
          el.textContent = hasDecimal ? current.toFixed(1) : Math.round(current);
          if (suffix) el.textContent += suffix;
          if (progress < 1) requestAnimationFrame(update);
          else el.textContent = (hasDecimal ? num.toFixed(1) : num) + suffix;
        }
        requestAnimationFrame(update);
      }, 300);
    }
  });
}

/* ── ۳. Confetti برای نمره خوب ── */
function launchConfetti() {
  const colors = ['#00d4ff','#00e5a0','#ffb347','#7b8cff','#ff6b9d','#ffd700'];
  const container = document.createElement('div');
  container.className = 'confetti-container';
  document.body.appendChild(container);

  for (let i = 0; i < 80; i++) {
    setTimeout(() => {
      const piece = document.createElement('div');
      piece.className = 'confetti-piece';
      piece.style.cssText = `
        right: ${Math.random() * 100}%;
        top: -10px;
        background: ${colors[Math.floor(Math.random() * colors.length)]};
        width: ${Math.random() * 8 + 4}px;
        height: ${Math.random() * 12 + 6}px;
        border-radius: ${Math.random() > .5 ? '50%' : '2px'};
        animation-duration: ${Math.random() * 2 + 2}s;
        animation-delay: 0s;
        transform-origin: center;
      `;
      container.appendChild(piece);
      setTimeout(() => piece.remove(), 4000);
    }, i * 40);
  }

  setTimeout(() => container.remove(), 6000);
}

/* ── ۴. Intersection Observer برای کارت‌ها ── */
function initScrollAnimations() {
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry, idx) => {
      if (entry.isIntersecting) {
        entry.target.style.animationDelay = (idx * 0.07) + 's';
        entry.target.classList.add('fade-in');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });

  document.querySelectorAll('.card, .exam-card, .stat-card, .feature-card').forEach(el => {
    if (!el.classList.contains('fade-in')) {
      el.style.opacity = '0';
      observer.observe(el);
    }
  });
}

/* ── ۵. Typing effect برای page-title ── */
function initTypewriter() {
  const titles = document.querySelectorAll('.page-title, .auth-title');
  titles.forEach(el => {
    const text = el.textContent;
    if (text.length < 3 || text.length > 40) return;
    el.textContent = '';
    el.style.borderLeft = '2px solid var(--accent)';
    el.style.paddingLeft = '2px';
    
    let i = 0;
    const type = () => {
      if (i < text.length) {
        el.textContent += text[i++];
        setTimeout(type, 40 + Math.random() * 20);
      } else {
        setTimeout(() => {
          el.style.borderLeft = 'none';
          el.style.paddingLeft = '0';
        }, 500);
      }
    };
    setTimeout(type, 200);
  });
}

/* ── ۶. Particle background برای صفحه لاگین ── */
function initLoginParticles() {
  if (!document.querySelector('.auth-page')) return;
  
  const canvas = document.createElement('canvas');
  canvas.style.cssText = `
    position: fixed; inset: 0; pointer-events: none; z-index: 0;
    opacity: .4;
  `;
  document.body.insertBefore(canvas, document.body.firstChild);
  
  const ctx = canvas.getContext('2d');
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  const color = isLight ? '108,60,225' : '0,212,255';
  
  let particles = [];
  
  function resize() {
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  resize();
  window.addEventListener('resize', resize);
  
  for (let i = 0; i < 50; i++) {
    particles.push({
      x: Math.random() * canvas.width,
      y: Math.random() * canvas.height,
      vx: (Math.random() - .5) * .5,
      vy: (Math.random() - .5) * .5,
      r: Math.random() * 2 + 1,
      alpha: Math.random() * .5 + .2
    });
  }
  
  function draw() {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    
    particles.forEach((p, i) => {
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0 || p.x > canvas.width)  p.vx *= -1;
      if (p.y < 0 || p.y > canvas.height) p.vy *= -1;
      
      ctx.beginPath();
      ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2);
      ctx.fillStyle = `rgba(${color}, ${p.alpha})`;
      ctx.fill();
      
      // اتصال ذرات نزدیک
      particles.slice(i + 1).forEach(q => {
        const dx = p.x - q.x, dy = p.y - q.y;
        const dist = Math.sqrt(dx*dx + dy*dy);
        if (dist < 120) {
          ctx.beginPath();
          ctx.moveTo(p.x, p.y);
          ctx.lineTo(q.x, q.y);
          ctx.strokeStyle = `rgba(${color}, ${.15 * (1 - dist/120)})`;
          ctx.lineWidth = .5;
          ctx.stroke();
        }
      });
    });
    
    requestAnimationFrame(draw);
  }
  draw();
}

/* ── ۷. Magnetic buttons ── */
function initMagneticButtons() {
  document.querySelectorAll('.btn-primary.btn-lg, .hero-cta .btn').forEach(btn => {
    btn.addEventListener('mousemove', function(e) {
      const rect = this.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top  + rect.height / 2;
      const dx = (e.clientX - cx) * .2;
      const dy = (e.clientY - cy) * .2;
      this.style.transform = `translate(${dx}px, ${dy}px) scale(1.03)`;
    });
    btn.addEventListener('mouseleave', function() {
      this.style.transform = '';
    });
  });
}

/* ── ۸. Tilt effect روی stat cards ── */
function initTiltEffect() {
  document.querySelectorAll('.stat-card, .feature-card').forEach(card => {
    card.addEventListener('mousemove', function(e) {
      const rect = this.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top  + rect.height / 2;
      const dx = (e.clientX - cx) / (rect.width / 2);
      const dy = (e.clientY - cy) / (rect.height / 2);
      this.style.transform = `
        translateY(-6px) scale(1.02)
        rotateX(${-dy * 5}deg)
        rotateY(${dx * 5}deg)
      `;
      this.style.transition = 'transform .05s ease';
    });
    card.addEventListener('mouseleave', function() {
      this.style.transform = '';
      this.style.transition = 'transform .3s var(--ease-spring)';
    });
  });
}

/* ── ۹. Score result confetti trigger ── */
function checkAndLaunchConfetti() {
  const scoreBig = document.querySelector('.score-big');
  const scoreTotal = document.querySelector('.score-total');
  if (!scoreBig || !scoreTotal) return;

  const score = parseFloat(scoreBig.dataset.target ?? scoreBig.textContent);
  const totalText = scoreTotal.textContent.replace(/[^0-9.]/g, '');
  const total = parseFloat(totalText);
  
  if (!isNaN(score) && !isNaN(total) && total > 0) {
    const pct = score / total;
    if (pct >= .75) {
      setTimeout(launchConfetti, 1200);
    }
  }
}

/* ── ۱۰. Stagger animation برای list items ── */
function initStaggerAnimations() {
  document.querySelectorAll('tbody tr, .exam-grid .exam-card').forEach((el, i) => {
    el.style.animationDelay = (i * 0.06) + 's';
    el.style.animation = 'fadeInUp .4s cubic-bezier(0.34,1.56,0.64,1) both';
    el.style.animationDelay = (i * 0.06) + 's';
  });
}

/* ── ۱۱. Sound wave for timer warning (visual only) ── */
function initTimerVisualEffect() {
  const timerEl = document.getElementById('timer-value');
  if (!timerEl) return;
  
  const observer = new MutationObserver(() => {
    if (timerEl.classList.contains('timer-crit')) {
      timerEl.closest('.exam-timer-widget')?.classList.add('crit-shake');
      setTimeout(() => {
        timerEl.closest('.exam-timer-widget')?.classList.remove('crit-shake');
      }, 200);
    }
  });
  observer.observe(timerEl, { attributeFilter: ['class'] });
}

/* ── ۱۲. Cursor glow effect (subtle) ── */
function initCursorGlow() {
  const glow = document.createElement('div');
  glow.style.cssText = `
    position: fixed;
    width: 200px; height: 200px;
    border-radius: 50%;
    background: radial-gradient(circle, rgba(0,212,255,.04) 0%, transparent 70%);
    pointer-events: none;
    z-index: 9998;
    transform: translate(-50%, -50%);
    transition: opacity .3s;
    mix-blend-mode: screen;
  `;
  document.body.appendChild(glow);
  
  let mouseX = 0, mouseY = 0, glowX = 0, glowY = 0;
  
  document.addEventListener('mousemove', e => {
    mouseX = e.clientX;
    mouseY = e.clientY;
  });
  
  function animateGlow() {
    glowX += (mouseX - glowX) * .08;
    glowY += (mouseY - glowY) * .08;
    glow.style.left = glowX + 'px';
    glow.style.top  = glowY + 'px';
    requestAnimationFrame(animateGlow);
  }
  animateGlow();
  
  // پنهان شدن وقتی ماوس نیست
  document.addEventListener('mouseleave', () => glow.style.opacity = '0');
  document.addEventListener('mouseenter', () => glow.style.opacity = '1');
}

/* ── ۱۳. Smooth number update for timer ── */
function smoothTimerTick() {
  const timerEl = document.getElementById('timer-value');
  if (!timerEl) return;
  
  const originalUpdate = window.startExamTimer;
  if (!originalUpdate) return;
  
  // Add scale animation on each tick
  const tickObserver = new MutationObserver(() => {
    timerEl.style.transform = 'scale(1.08)';
    setTimeout(() => {
      timerEl.style.transform = 'scale(1)';
      timerEl.style.transition = 'transform .15s ease';
    }, 50);
  });
  tickObserver.observe(timerEl, { childList: true, characterData: true, subtree: true });
}

/* ── ۱۴. نوار پیشرفت متحرک هنگام تغییر ── */
function enhanceProgressBar() {
  const fill = document.getElementById('progress-fill');
  if (!fill) return;
  
  const origSetWidth = Object.getOwnPropertyDescriptor(CSSStyleDeclaration.prototype, 'width');
  
  const observer = new MutationObserver(() => {
    fill.style.transition = 'width .6s cubic-bezier(0.34, 1.56, 0.64, 1)';
  });
  observer.observe(fill, { attributeFilter: ['style'] });
}

/* ── ۱۵. کارت‌ها با Glass morphism بهتر ── */
function enhanceGlassMorphism() {
  const isLight = document.documentElement.getAttribute('data-theme') === 'light';
  if (!isLight) return;
  
  document.querySelectorAll('.card, .stat-card').forEach(el => {
    el.style.backdropFilter = 'blur(20px) saturate(180%) brightness(1.02)';
    el.style.webkitBackdropFilter = 'blur(20px) saturate(180%) brightness(1.02)';
  });
}

/* ── DOM Ready ── */
document.addEventListener('DOMContentLoaded', () => {
  // اجرای تمام افکت‌ها
  addRippleEffect();
  initScrollAnimations();
  initMagneticButtons();
  initTiltEffect();
  initTimerVisualEffect();
  smoothTimerTick();
  enhanceProgressBar();
  enhanceGlassMorphism();
  
  // صفحه لاگین
  if (document.querySelector('.auth-page')) {
    initLoginParticles();
    // typewriter فقط روی title
    const authTitle = document.querySelector('.auth-title');
    if (authTitle) {
      const text = authTitle.textContent;
      authTitle.textContent = '';
      let i = 0;
      const type = () => {
        if (i < text.length) {
          authTitle.textContent += text[i++];
          setTimeout(type, 50);
        }
      };
      setTimeout(type, 400);
    }
  }
  
  // شمارنده‌های متحرک
  setTimeout(initCounters, 100);
  
  // stagger برای جداول
  setTimeout(initStaggerAnimations, 50);
  
  // confetti برای صفحه نتیجه
  checkAndLaunchConfetti();
  
  // cursor glow (فقط desktop)
  if (window.innerWidth > 900) {
    initCursorGlow();
  }
  
  // ریزپانیمیشن برای option labels در آزمون
  document.querySelectorAll('.option-label').forEach((label, idx) => {
    label.style.animationDelay = (idx * 0.08) + 's';
    label.style.animation = 'fadeInUp .4s cubic-bezier(0.34,1.56,0.64,1) both';
    label.style.animationDelay = (idx * 0.08) + 's';
  });
  
  // نور متحرک در هدر آزمون
  const examHeader = document.querySelector('.exam-header');
  if (examHeader) {
    examHeader.style.animation = 'topbar-in .5s cubic-bezier(0.34,1.56,0.64,1) both';
  }
  
  // keyboard nav مخفی کردن glow
  document.addEventListener('keydown', e => {
    if (e.key === 'Tab') {
      const glow = document.querySelector('[style*="cursor glow"]');
      if (glow) glow.style.opacity = '0';
    }
  });
});

/* ── Theme change مجدد ── */
const origToggleTheme = window.toggleTheme;
window.toggleTheme = function() {
  const html = document.documentElement;
  
  // افکت flash هنگام تغییر تم
  const flash = document.createElement('div');
  flash.style.cssText = `
    position: fixed; inset: 0; z-index: 99999;
    background: white; opacity: 0;
    pointer-events: none;
    transition: opacity .15s ease;
  `;
  document.body.appendChild(flash);
  
  requestAnimationFrame(() => {
    flash.style.opacity = '.3';
    setTimeout(() => {
      if (origToggleTheme) origToggleTheme();
      flash.style.opacity = '0';
      setTimeout(() => {
        flash.remove();
        enhanceGlassMorphism();
      }, 150);
    }, 100);
  });
  
  if (!origToggleTheme) {
    const current = html.getAttribute('data-theme') || 'dark';
    html.setAttribute('data-theme', current === 'dark' ? 'light' : 'dark');
    localStorage.setItem('exam_theme', current === 'dark' ? 'light' : 'dark');
  }
};
