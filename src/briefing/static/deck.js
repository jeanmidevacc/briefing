/* briefing deck (#197): one slide at a time, scaled to the window. Keys, a link per slide,
   an overview of every slide and full screen. Vanilla JS, no deps. */
(function () {
  'use strict';

  // What doesn't fit a slide shrinks, down to this; below it, the slide scrolls and says so.
  var MIN_FIT = 0.7;

  // Charts drawn at one width need a redraw at another (Plotly); Vega follows window resizes.
  function resizePlots(el, win) {
    var plotly = win.Plotly;
    if (plotly && plotly.Plots) {
      el.querySelectorAll('.js-plotly-plot').forEach(function (plot) { plotly.Plots.resize(plot); });
    }
    if (el.querySelector('.bf-altair')) win.dispatchEvent(new Event('resize'));
  }

  // Shrink a slide's content until it fits its body (the slide keeps its 1280 x 720 layout,
  // whatever the window's size, so this is measured once per change of content).
  function fit(slide, win) {
    var body = slide.querySelector(':scope > .bf-slide__body');
    var content = body && body.querySelector(':scope > .bf-slide__content');
    if (!content) return;
    var before = content.style.getPropertyValue('--bf-fit') || '1';
    var room = body.clientHeight;
    var k = 1;
    content.style.removeProperty('--bf-fit');
    slide.classList.remove('bf-slide--overflow');
    for (var i = 0; i < 4 && content.offsetHeight * k > room + 1; i++) {
      k = Math.max(MIN_FIT, k * room / (content.offsetHeight * k));
      content.style.setProperty('--bf-fit', String(k));
      if (k === MIN_FIT) break;
    }
    if (content.offsetHeight * k > room + 1) slide.classList.add('bf-slide--overflow');
    if (String(k) !== before) resizePlots(content, win);
  }

  function linkOf(hash) {
    try { return decodeURIComponent(hash.replace(/^#/, '')); } catch (e) { return ''; }
  }

  window.briefing.register('deck', function (runtime) {
    return function (root) {
      if (root.nodeType !== 9) return;  // a deck is a whole page, never a fragment
      var deck = root.querySelector('[data-bf-deck]');
      if (!deck) return;
      var win = root.defaultView;
      var stage = deck.querySelector('.bf-deck__stage');
      var slides = Array.prototype.slice.call(stage.querySelectorAll(':scope > .bf-slide'));
      if (!slides.length) return;
      var width = Number(deck.getAttribute('data-bf-width')) || 1280;
      var height = Number(deck.getAttribute('data-bf-height')) || 720;
      var controls = deck.querySelector('.bf-deck__controls');
      var count = deck.querySelector('.bf-deck__count');
      var button = function (go) { return controls.querySelector('[data-bf-go="' + go + '"]'); };
      var prevBtn = button('prev'), nextBtn = button('next'), overviewBtn = button('overview');
      var current = -1;
      var overview = false;

      function scale() {
        deck.style.setProperty('--bf-scale', String(Math.min(win.innerWidth / width, win.innerHeight / height)));
      }

      function show(i, write) {
        i = Math.max(0, Math.min(slides.length - 1, i));
        if (current >= 0) {
          slides[current].classList.remove('bf-slide--current');
          slides[current].removeAttribute('aria-current');
        }
        current = i;
        slides[i].classList.add('bf-slide--current');
        slides[i].setAttribute('aria-current', 'step');
        fit(slides[i], win);
        count.textContent = (i + 1) + ' / ' + slides.length;
        prevBtn.disabled = i === 0;
        nextBtn.disabled = i === slides.length - 1;
        if (write) win.history.replaceState(win.history.state, '', '#' + (i + 1));
      }

      // #3 is the third slide; #name is the slide, or the block, of that name.
      function follow() {
        var link = linkOf(win.location.hash);
        if (/^\d+$/.test(link)) return show(Number(link) - 1, false);
        var target = link ? root.querySelector('[data-bf-link][id="' + link.replace(/["\\]/g, '\\$&') + '"]') : null;
        var slide = target && target.closest('.bf-slide');
        show(slide ? slides.indexOf(slide) : Math.max(current, 0), false);
      }

      function setOverview(on) {
        overview = on;
        deck.classList.toggle('bf-deck--overview', on);
        overviewBtn.setAttribute('aria-pressed', on ? 'true' : 'false');
        slides.forEach(function (slide) {
          if (on) slide.setAttribute('tabindex', '0'); else slide.removeAttribute('tabindex');
        });
        if (on) slides[current].focus();
      }

      function pick(slide) {
        setOverview(false);
        show(slides.indexOf(slide), true);
      }

      function fullscreen() {
        if (root.fullscreenElement) {
          if (root.exitFullscreen) root.exitFullscreen();
        } else if (root.documentElement.requestFullscreen) {
          root.documentElement.requestFullscreen();
        }
      }

      var actions = {
        prev: function () { show(current - 1, true); },
        next: function () { show(current + 1, true); },
        overview: function () { setOverview(!overview); },
        fullscreen: fullscreen
      };

      controls.addEventListener('click', function (e) {
        var btn = e.target.closest('[data-bf-go]');
        if (btn) actions[btn.getAttribute('data-bf-go')]();
      });

      stage.addEventListener('click', function (e) {
        var slide = e.target.closest('.bf-slide');
        if (overview && slide) return pick(slide);
        // A tab or a toggle may change what the slide holds: fit it again.
        win.setTimeout(function () { if (current >= 0) fit(slides[current], win); }, 0);
      });

      var startX = null, startY = null;
      stage.addEventListener('touchstart', function (e) {
        startX = e.touches[0].clientX;
        startY = e.touches[0].clientY;
      }, { passive: true });
      stage.addEventListener('touchend', function (e) {
        if (startX === null || overview) return;
        var dx = e.changedTouches[0].clientX - startX, dy = e.changedTouches[0].clientY - startY;
        startX = null;
        if (Math.abs(dx) > 50 && Math.abs(dx) > Math.abs(dy)) show(current + (dx < 0 ? 1 : -1), true);
      });

      runtime.on(root, 'keydown', function (e) {
        if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
        var target = e.target;
        // Keys belong to what has focus when it uses them: fields, tabs, buttons and links (space).
        if (target.closest && target.closest('input, textarea, select, [contenteditable], [role="tablist"]')) return;
        if (e.key === ' ' && target.closest && target.closest('button, a')) return;
        var key = e.key;
        if (overview && (key === 'Enter' || key === 'Escape') && target.classList.contains('bf-slide')) {
          pick(target);
        } else if (overview && key === 'Escape') {
          setOverview(false);
        } else if (key === 'ArrowRight' || key === 'ArrowDown' || key === 'PageDown' || (key === ' ' && !e.shiftKey)) {
          show(current + 1, true);
          if (overview) slides[current].focus();
        } else if (key === 'ArrowLeft' || key === 'ArrowUp' || key === 'PageUp' || key === ' ') {
          show(current - 1, true);
          if (overview) slides[current].focus();
        } else if (key === 'Home') {
          show(0, true);
        } else if (key === 'End') {
          show(slides.length - 1, true);
        } else if (key === 'o' || key === 'O') {
          setOverview(!overview);
        } else if (key === 'f' || key === 'F') {
          fullscreen();
        } else {
          return;
        }
        e.preventDefault();
      });

      // The controls fade out two seconds after the mouse last moved (and stay while hovered).
      var idle = null;
      function wake() {
        controls.classList.remove('bf-deck__controls--idle');
        win.clearTimeout(idle);
        idle = win.setTimeout(function () { controls.classList.add('bf-deck__controls--idle'); }, 2000);
      }
      runtime.on(root, 'mousemove', wake);

      // Print every slide, one per page (deck.css): leave the overview while printing.
      var overviewBeforePrint = false;
      runtime.onPrint(function () {
        overviewBeforePrint = overview;
        if (overview) setOverview(false);
      }, function () {
        if (overviewBeforePrint) setOverview(true);
      });

      deck.classList.add('bf-deck--live');
      controls.hidden = false;
      wake();
      win.scrollTo(0, 0);
      scale();
      slides.forEach(function (slide) { fit(slide, win); });
      follow();
      runtime.on(win, 'resize', scale);
      runtime.on(win, 'hashchange', follow);
      // Images and charts drawn late may change what a slide holds.
      runtime.on(win, 'load', function () { slides.forEach(function (slide) { fit(slide, win); }); });
    };
  });
})();
