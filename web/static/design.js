/* ============================================================
   AutoRewier — design.js
   UI/UX логика: меню, анимации, верификация, форм-валидация
   ============================================================ */

(function () {
  'use strict';

  /* ============================================================
     УТИЛИТЫ
     ============================================================ */
  const $ = (sel, ctx = document) => ctx.querySelector(sel);
  const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

  /* ============================================================
     ГАМБУРГЕР-МЕНЮ
     ============================================================ */
  function initHamburger() {
    const toggle = $('#nav-toggle');
    const mobileNav = $('#nav-mobile');
    if (!toggle || !mobileNav) return;

    toggle.addEventListener('click', () => {
      const isOpen = toggle.classList.toggle('open');
      mobileNav.classList.toggle('open', isOpen);
      toggle.setAttribute('aria-expanded', isOpen);
      document.body.style.overflow = isOpen ? 'hidden' : '';
    });

    // Закрыть при клике на ссылку
    $$('a', mobileNav).forEach(link => {
      link.addEventListener('click', () => {
        toggle.classList.remove('open');
        mobileNav.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
        document.body.style.overflow = '';
      });
    });

    // Закрыть при клике вне
    document.addEventListener('click', e => {
      if (!toggle.contains(e.target) && !mobileNav.contains(e.target)) {
        toggle.classList.remove('open');
        mobileNav.classList.remove('open');
        toggle.setAttribute('aria-expanded', 'false');
        document.body.style.overflow = '';
      }
    });
  }

  /* ============================================================
     STICKY HEADER — добавляем класс при скролле
     ============================================================ */
  function initStickyHeader() {
    const header = $('.header');
    if (!header) return;

    const onScroll = () => {
      header.classList.toggle('scrolled', window.scrollY > 20);
    };

    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ============================================================
     АНИМАЦИИ ПРИ СКРОЛЛЕ (Intersection Observer)
     ============================================================ */
  function initScrollReveal() {
    // Не запускаем если нет поддержки или пользователь не хочет анимации
    if (
      !('IntersectionObserver' in window) ||
      window.matchMedia('(prefers-reduced-motion: reduce)').matches
    ) {
      $$('.reveal').forEach(el => {
        el.classList.add('visible');
      });
      return;
    }

    const observer = new IntersectionObserver(
      entries => {
        entries.forEach(entry => {
          if (entry.isIntersecting) {
            entry.target.classList.add('visible');
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -40px 0px' }
    );

    $$('.reveal').forEach(el => observer.observe(el));
  }

  /* ============================================================
     PAGE TRANSITION — fade
     ============================================================ */
  function initPageTransition() {
    const main = $('main');
    if (!main) return;
    main.classList.add('page-fade');
  }

  /* ============================================================
     6-ЗНАЧНЫЙ КОД ВЕРИФИКАЦИИ
     ============================================================ */
  function initCodeInputs() {
    const container = $('#code-inputs-container');
    if (!container) return;

    const inputs = $$('.code-digit', container);
    if (!inputs.length) return;

    // Авто-фокус на первый
    inputs[0]?.focus();

    inputs.forEach((input, idx) => {
      input.addEventListener('input', e => {
        const val = e.target.value.replace(/\D/g, '').slice(-1);
        e.target.value = val;

        if (val) {
          input.classList.add('filled');
          // Переходим к следующему
          if (idx < inputs.length - 1) {
            inputs[idx + 1].focus();
          } else {
            // Последний — автосабмит
            autoSubmitCode();
          }
        } else {
          input.classList.remove('filled');
        }

        updateHiddenCode(inputs);
      });

      input.addEventListener('keydown', e => {
        // Backspace — возврат к предыдущему
        if (e.key === 'Backspace' && !e.target.value && idx > 0) {
          inputs[idx - 1].value = '';
          inputs[idx - 1].classList.remove('filled');
          inputs[idx - 1].focus();
          updateHiddenCode(inputs);
        }

        // Стрелки
        if (e.key === 'ArrowLeft' && idx > 0) {
          inputs[idx - 1].focus();
        }
        if (e.key === 'ArrowRight' && idx < inputs.length - 1) {
          inputs[idx + 1].focus();
        }
      });

      // Вставка кода из буфера
      input.addEventListener('paste', e => {
        e.preventDefault();
        const pasted = (e.clipboardData || window.clipboardData)
          .getData('text')
          .replace(/\D/g, '')
          .slice(0, inputs.length);

        pasted.split('').forEach((char, i) => {
          if (inputs[i]) {
            inputs[i].value = char;
            inputs[i].classList.add('filled');
          }
        });

        updateHiddenCode(inputs);

        const nextEmpty = inputs.findIndex(inp => !inp.value);
        if (nextEmpty !== -1) {
          inputs[nextEmpty].focus();
        } else {
          inputs[inputs.length - 1].focus();
          autoSubmitCode();
        }
      });
    });
  }

  function updateHiddenCode(inputs) {
    const hidden = $('#verification-code');
    if (!hidden) return;
    hidden.value = inputs.map(i => i.value).join('');
  }

  function autoSubmitCode() {
    const form = $('#verify-form');
    if (!form) return;

    const hidden = $('#verification-code');
    if (!hidden) return;

    // Небольшая пауза для UX
    setTimeout(() => {
      if (hidden.value.length === 6) {
        form.submit();
      }
    }, 150);
  }

  /* ============================================================
     ТАЙМЕР ПОВТОРНОЙ ОТПРАВКИ КОДА
     ============================================================ */
  function initResendTimer() {
    const timerEl = $('#resend-timer');
    const countdownEl = $('#resend-countdown');
    const resendBtn = $('#resend-btn');
    if (!timerEl || !countdownEl || !resendBtn) return;

    let seconds = 60;
    resendBtn.disabled = true;

    const interval = setInterval(() => {
      seconds--;
      countdownEl.textContent = seconds;

      if (seconds <= 0) {
        clearInterval(interval);
        timerEl.style.display = 'none';
        resendBtn.disabled = false;
        resendBtn.style.display = 'inline-block';
      }
    }, 1000);

    resendBtn.style.display = 'none';

    resendBtn.addEventListener('click', async () => {
      resendBtn.disabled = true;
      resendBtn.textContent = 'Отправляем...';

      try {
        const res = await fetch('/api/v1/auth/resend-verification', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });

        if (res.ok) {
          resendBtn.textContent = 'Отправлено!';
          // Перезапускаем таймер
          setTimeout(() => {
            resendBtn.style.display = 'none';
            timerEl.style.display = '';
            seconds = 60;
            countdownEl.textContent = seconds;

            const newInterval = setInterval(() => {
              seconds--;
              countdownEl.textContent = seconds;
              if (seconds <= 0) {
                clearInterval(newInterval);
                timerEl.style.display = 'none';
                resendBtn.disabled = false;
                resendBtn.style.display = 'inline-block';
                resendBtn.textContent = 'Отправить снова';
              }
            }, 1000);
          }, 2000);
        } else {
          resendBtn.disabled = false;
          resendBtn.textContent = 'Попробовать снова';
        }
      } catch {
        resendBtn.disabled = false;
        resendBtn.textContent = 'Ошибка. Повторите';
      }
    });
  }

  /* ============================================================
     ВАЛИДАЦИЯ ПАРОЛЕЙ (страница reset)
     ============================================================ */
  function initPasswordValidation() {
    const form = $('#reset-form');
    if (!form) return;

    const newPwd  = $('#new-password');
    const confPwd = $('#confirm-password');
    const errorEl = $('#password-match-error');
    const submitBtn = $('#reset-submit');

    if (!newPwd || !confPwd || !errorEl) return;

    function validate() {
      const match = newPwd.value === confPwd.value;
      const hasLength = newPwd.value.length >= 6;

      if (confPwd.value && !match) {
        errorEl.textContent = 'Пароли не совпадают';
        errorEl.style.display = 'block';
        confPwd.style.borderColor = 'var(--bad)';
        confPwd.style.boxShadow = '0 0 0 3px rgba(255,91,91,0.15)';
        if (submitBtn) submitBtn.disabled = true;
      } else if (confPwd.value && match && hasLength) {
        errorEl.style.display = 'none';
        confPwd.style.borderColor = 'var(--ok)';
        confPwd.style.boxShadow = '0 0 0 3px rgba(52,212,122,0.15)';
        if (submitBtn) submitBtn.disabled = false;
      } else {
        errorEl.style.display = 'none';
        confPwd.style.borderColor = '';
        confPwd.style.boxShadow = '';
        if (submitBtn) submitBtn.disabled = !hasLength;
      }
    }

    newPwd.addEventListener('input', validate);
    confPwd.addEventListener('input', validate);

    form.addEventListener('submit', e => {
      if (newPwd.value !== confPwd.value) {
        e.preventDefault();
        errorEl.textContent = 'Пароли не совпадают';
        errorEl.style.display = 'block';
      }
    });
  }

  /* ============================================================
     СРАВНЕНИЕ АВТ — чекбоксы и sticky-бар
     ============================================================ */
  function initCompareCheckboxes() {
    const checkboxes = $$('[data-compare-checkbox]');
    const compareBar = $('#compare-bar');
    const compareBadge = $('#compare-count');
    const compareBtn = $('#compare-btn');
    if (!checkboxes.length || !compareBar) return;

    const MAX = 3;

    function updateBar() {
      const checked = checkboxes.filter(cb => cb.checked);
      const count = checked.length;

      if (compareBadge) compareBadge.textContent = count;

      if (count >= 2) {
        compareBar.classList.add('visible');
        if (compareBtn) compareBtn.disabled = false;
      } else {
        compareBar.classList.remove('visible');
        if (compareBtn) compareBtn.disabled = true;
      }

      // Блокируем лишние
      checkboxes.forEach(cb => {
        if (!cb.checked && count >= MAX) {
          cb.disabled = true;
        } else {
          cb.disabled = false;
        }
      });
    }

    checkboxes.forEach(cb => {
      cb.addEventListener('change', updateBar);
    });

    // Кнопка "Сравнить"
    if (compareBtn) {
      compareBtn.addEventListener('click', () => {
        const checked = checkboxes.filter(cb => cb.checked);
        const ids = checked.map(cb => cb.getAttribute('data-compare-checkbox')).join(',');
        if (ids) {
          window.location.href = `/cabinet/compare?ids=${ids}`;
        }
      });
    }
  }

  /* ============================================================
     FLOATING LABELS — обратная совместимость
     ============================================================ */
  function initFloatingLabels() {
    $$('.form-field').forEach(field => {
      const input = field.querySelector('input, textarea, select');
      if (!input) return;

      // Начальное состояние
      if (input.value) {
        field.classList.add('has-value');
      }

      input.addEventListener('focus', () => field.classList.add('focused'));
      input.addEventListener('blur',  () => {
        field.classList.remove('focused');
        field.classList.toggle('has-value', !!input.value);
      });
      input.addEventListener('input', () => {
        field.classList.toggle('has-value', !!input.value);
      });
    });
  }

  /* ============================================================
     СЧЁТЧИК СИМВОЛОВ для textarea
     ============================================================ */
  function initCharCounters() {
    $$('textarea[maxlength]').forEach(ta => {
      const max = parseInt(ta.getAttribute('maxlength'), 10);
      const counter = document.createElement('small');
      counter.style.cssText = 'display:block;text-align:right;color:var(--muted);font-size:0.77rem;margin-top:0.25rem;';
      counter.textContent = `0 / ${max}`;
      ta.parentNode.insertBefore(counter, ta.nextSibling);

      ta.addEventListener('input', () => {
        counter.textContent = `${ta.value.length} / ${max}`;
      });
    });
  }

  /* ============================================================
     FORGOT PASSWORD — показать сообщение об успехе
     ============================================================ */
  function initForgotForm() {
    const form = $('#forgot-form');
    const successMsg = $('#forgot-success');
    if (!form || !successMsg) return;

    form.addEventListener('submit', async e => {
      e.preventDefault();
      const btn = form.querySelector('[type="submit"]');
      const email = form.querySelector('[name="email"]')?.value;
      if (!email) return;

      if (btn) {
        btn.disabled = true;
        btn.textContent = 'Отправляем...';
      }

      try {
        const res = await fetch('/api/v1/auth/forgot-password', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email }),
        });

        // Показываем успех вне зависимости от ответа (безопасность)
        form.style.display = 'none';
        successMsg.style.display = 'block';
      } catch {
        if (btn) {
          btn.disabled = false;
          btn.textContent = 'Отправить ссылку';
        }
      }
    });
  }

  /* ============================================================
     АВТОМАТИЧЕСКОЕ СКРЫТИЕ АЛЕРТОВ
     ============================================================ */
  function initAutoHideAlerts() {
    $$('.alert[data-auto-hide]').forEach(alert => {
      const delay = parseInt(alert.getAttribute('data-auto-hide'), 10) || 5000;
      setTimeout(() => {
        alert.style.opacity = '0';
        alert.style.transform = 'translateY(-8px)';
        alert.style.transition = 'opacity 0.3s, transform 0.3s';
        setTimeout(() => alert.remove(), 350);
      }, delay);
    });
  }

  /* ============================================================
     ИНИЦИАЛИЗАЦИЯ
     ============================================================ */
  function init() {
    initHamburger();
    initStickyHeader();
    initScrollReveal();
    initPageTransition();
    initCodeInputs();
    initResendTimer();
    initPasswordValidation();
    initCompareCheckboxes();
    initFloatingLabels();
    initCharCounters();
    initForgotForm();
    initAutoHideAlerts();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
