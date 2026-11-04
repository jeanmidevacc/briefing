/* briefing lab: CalendarHeatmap — sizing, hover tooltip, and on_click="rows" (click a day or an hour to
   list its rows). Vanilla JS. */
(function () {
  'use strict';

  // The SVGs fit the width of their block (CSS, #106). Publish the scale k on the view: legend
  // swatches follow the cells (--bf-cal-k), and labels change size at half the cells' rate, so
  // they stay readable when the calendar grows or shrinks (--bf-cal-text, in the SVG's units).
  function measure(view) {
    var svg = view.querySelector('svg.bf-cal__days, svg.bf-cal__hours');
    var natural = svg ? parseFloat(svg.getAttribute('width')) : 0;
    var shown = svg ? svg.getBoundingClientRect().width : 0;
    if (!(natural > 0 && shown > 0)) return;  // a hidden tab: measured once it is shown
    var k = shown / natural;
    view.style.setProperty('--bf-cal-k', String(k));
    view.style.setProperty('--bf-cal-text', String((1 + k) / (2 * k)));
  }
  document.querySelectorAll('.bf-calendar').forEach(function (figure) {
    var views = figure.querySelectorAll('.bf-cal__views > .bf-select__panel');
    views = views.length ? Array.prototype.slice.call(views) : [figure];
    views.forEach(function (view) {
      measure(view);
      if (window.ResizeObserver) {
        new ResizeObserver(function () { measure(view); }).observe(view);
      } else {
        window.addEventListener('resize', function () { measure(view); });
      }
    });
  });

  // Hover tooltip (#109): instant, themed, and shown on keyboard focus and tap too. Its text comes
  // from each cell's <title>, which is then removed so the browser's own slow tooltip doesn't double
  // up; clickable cells keep the text as their aria-label. Built with textContent only.
  var tips = [];
  function hideTips() { tips.forEach(function (tip) { tip.hidden = true; }); }
  function showTip(tip, cell) {
    var lines = (cell.getAttribute('data-tip') || '').split(' \u00b7 ');
    tip.textContent = '';
    lines.forEach(function (line, i) {
      var el = document.createElement(i === 0 ? 'strong' : 'div');
      el.textContent = line;
      tip.appendChild(el);
    });
    hideTips();
    tip.hidden = false;
    // Above the cell, centred; below it when there is no room above; always inside the window.
    var box = cell.getBoundingClientRect(), gap = 6, edge = 4;
    var width = tip.offsetWidth, height = tip.offsetHeight;
    var left = box.left + box.width / 2 - width / 2;
    left = Math.max(edge, Math.min(left, document.documentElement.clientWidth - width - edge));
    var top = box.top - height - gap;
    if (top < edge) top = box.bottom + gap;
    tip.style.left = left + 'px';
    tip.style.top = top + 'px';
  }
  document.querySelectorAll('.bf-calendar').forEach(function (figure) {
    var tip = document.createElement('div');
    tip.className = 'bf-cal__tip';
    tip.setAttribute('role', 'tooltip');
    tip.hidden = true;
    figure.appendChild(tip);
    tips.push(tip);
    figure.querySelectorAll('rect.bf-cal__day, rect.bf-cal__hour, g.bf-cal__event').forEach(function (cell) {
      var title = cell.querySelector('title');
      if (!title) return;
      cell.setAttribute('data-tip', title.textContent);
      if (cell.getAttribute('role') === 'button') cell.setAttribute('aria-label', title.textContent);
      cell.removeChild(title);
      cell.addEventListener('mouseenter', function () { showTip(tip, cell); });
      cell.addEventListener('mouseleave', hideTips);
      cell.addEventListener('focus', function () { showTip(tip, cell); });
      cell.addEventListener('blur', hideTips);
      cell.addEventListener('pointerdown', function (e) { if (e.pointerType !== 'mouse') showTip(tip, cell); });
    });
  });
  if (tips.length) {
    // A tap elsewhere, scrolling (the page or a calendar's own scroll box) or Escape hides it.
    document.addEventListener('pointerdown', function (e) {
      if (!(e.target.closest && e.target.closest('[data-tip]'))) hideTips();
    });
    window.addEventListener('scroll', hideTips, true);
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') hideTips(); });
  }

  document.querySelectorAll('.bf-calendar').forEach(function (figure) {
    var dataEl = figure.querySelector('script.bf-cal__rows');
    if (!dataEl) return;
    var data = JSON.parse(dataEl.textContent);
    var panel = figure.querySelector('.bf-cal__panel');
    var title = panel.querySelector('.bf-cal__panel-title');
    var body = panel.querySelector('.bf-cal__panel-body');

    // Built with textContent only: row values are shown as text, never as markup.
    function open(cell) {
      var calendar = cell.closest('.bf-cal__calendar');
      var group = calendar ? calendar.getAttribute('data-group') : null;
      var date = cell.getAttribute('data-date');
      var key = (date ? 'd|' + date : 'h|' + cell.getAttribute('data-hour')) + (group !== null ? '|' + group : '');
      var entry = data.cells[key];
      var when = (cell.getAttribute('data-tip') || '').split(' \u00b7 ')[0];
      var count = entry ? entry.total + (entry.total === 1 ? ' row' : ' rows') : 'no rows';
      title.textContent = [when, group, count].filter(function (x) { return x !== null; }).join(' · ');
      body.textContent = '';
      if (entry) {
        var table = document.createElement('table');
        table.className = 'bf-table__table';
        var head = table.createTHead().insertRow();
        data.columns.forEach(function (name) {
          var th = document.createElement('th');
          th.textContent = name;
          head.appendChild(th);
        });
        var rows = table.createTBody();
        entry.rows.forEach(function (values) {
          var tr = rows.insertRow();
          values.forEach(function (value) { tr.insertCell().textContent = value; });
        });
        var scroll = document.createElement('div');
        scroll.className = 'bf-table__scroll';
        scroll.appendChild(table);
        body.appendChild(scroll);
        if (entry.total > entry.rows.length) {
          var note = document.createElement('p');
          note.className = 'bf-cal__panel-note';
          note.textContent = 'Showing the first ' + entry.rows.length + ' of ' + entry.total + ' rows.';
          body.appendChild(note);
        }
      }
      panel.hidden = false;
    }

    figure.querySelectorAll('rect.bf-cal__day[role="button"], rect.bf-cal__hour[role="button"]').forEach(function (cell) {
      cell.addEventListener('click', function () { open(cell); });
      cell.addEventListener('keydown', function (e) {
        if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(cell); }
      });
    });
    panel.querySelector('.bf-cal__panel-close').addEventListener('click', function () { panel.hidden = true; });
  });
})();
