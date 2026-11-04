/* briefing lab: CalendarHeatmap — sizing, and on_click="rows" (click a day or an hour to list its rows). Vanilla JS. */
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
      var when = cell.querySelector('title').textContent.split(' · ')[0];
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
