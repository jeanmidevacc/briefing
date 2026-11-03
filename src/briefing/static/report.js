/* briefing report — interactive behaviour (tabs + toggles). Vanilla JS, no deps. */
(function () {
  'use strict';

  // ── Select / tabs ───────────────────────────────────────────────────────────

  document.querySelectorAll('.bf-select:not(.bf-select--dropdown)').forEach(function (sel) {
    var tablist = sel.querySelector(':scope > .bf-select__tablist');
    if (!tablist) return;

    var tabs   = Array.from(tablist.querySelectorAll('.bf-select__tab'));
    var panels = Array.from(sel.querySelectorAll(':scope > .bf-select__panel'));

    function activate(idx) {
      tabs.forEach(function (t, i) {
        t.setAttribute('aria-selected', i === idx ? 'true' : 'false');
        t.tabIndex = i === idx ? 0 : -1;
      });
      panels.forEach(function (p, i) {
        p.hidden = i !== idx;
      });
    }

    tabs.forEach(function (tab, i) {
      tab.addEventListener('click', function () { activate(i); });

      // Arrow-key navigation for accessibility.
      tab.addEventListener('keydown', function (e) {
        if (e.key === 'ArrowRight') { activate(Math.min(i + 1, tabs.length - 1)); tabs[Math.min(i + 1, tabs.length - 1)].focus(); }
        if (e.key === 'ArrowLeft')  { activate(Math.max(i - 1, 0));               tabs[Math.max(i - 1, 0)].focus(); }
        if (e.key === 'Home')       { activate(0);                                 tabs[0].focus(); }
        if (e.key === 'End')        { activate(tabs.length - 1);                   tabs[tabs.length - 1].focus(); }
      });
    });

    activate(0);
  });

  // ── Select / dropdown ────────────────────────────────────────────────────────

  document.querySelectorAll('.bf-select--dropdown').forEach(function (sel) {
    var select = sel.querySelector('.bf-select__select');
    var panels = Array.from(sel.querySelectorAll('.bf-select__panel'));

    function activate(idx) {
      panels.forEach(function (p, i) { p.hidden = i !== idx; });
    }

    if (select) {
      select.addEventListener('change', function () {
        activate(parseInt(select.value, 10));
      });
    }

    activate(0);
  });

  // ── DataTable ────────────────────────────────────────────────────────────────

  document.querySelectorAll('.bf-datatable').forEach(function (container) {
    var tbody    = container.querySelector('.bf-dt__table tbody');
    var search   = container.querySelector('.bf-dt__search');
    var countEl  = container.querySelector('.bf-dt__count');
    var pageInfo = container.querySelector('.bf-dt__page-info');
    var prevBtn  = container.querySelector('.bf-dt__page-btn[data-dir="-1"]');
    var nextBtn  = container.querySelector('.bf-dt__page-btn[data-dir="1"]');
    var headers  = Array.from(container.querySelectorAll('.bf-dt__th'));

    if (!tbody) return;

    var allRows  = Array.from(tbody.rows);
    var PAGE_SIZE = 25;
    var page     = 0;
    var sortCol  = -1;
    var sortAsc  = true;
    var filtered = allRows.slice();

    function render() {
      // Move the matching rows to the end of tbody in their current (sorted) order,
      // so the page shows them in that order and not in the original one.
      var frag = document.createDocumentFragment();
      filtered.forEach(function (r) { frag.appendChild(r); });
      tbody.appendChild(frag);
      allRows.forEach(function (r) { r.hidden = true; });
      var start = page * PAGE_SIZE;
      filtered.slice(start, start + PAGE_SIZE).forEach(function (r) { r.hidden = false; });

      var total = filtered.length;
      var from  = total === 0 ? 0 : start + 1;
      var to    = Math.min(start + PAGE_SIZE, total);
      if (countEl)  countEl.textContent  = total + ' row' + (total !== 1 ? 's' : '');
      if (pageInfo) pageInfo.textContent = total === 0 ? '–' : from + '–' + to + ' of ' + total;
      if (prevBtn)  prevBtn.disabled     = page === 0;
      if (nextBtn)  nextBtn.disabled     = to >= total;
    }

    function applyFilter() {
      var q = search ? search.value.toLowerCase() : '';
      filtered = q
        ? allRows.filter(function (r) { return r.textContent.toLowerCase().indexOf(q) !== -1; })
        : allRows.slice();
      if (sortCol >= 0) applySortToFiltered();
      page = 0;
      render();
    }

    // The value a row sorts by: the cell's data-sort key (written by Python for
    // numbers, dates and durations), else its text.
    function sortKey(row) {
      var cell = row.cells[sortCol];
      if (!cell) return '';
      var key = cell.getAttribute('data-sort');
      return key !== null ? key : cell.textContent.trim();
    }

    // A key that is a whole number, optionally with thousands separators ("1,200"); else NaN.
    function asNumber(s) {
      if (/^[-+]?\d{1,3}(,\d{3})+(\.\d+)?$/.test(s)) s = s.replace(/,/g, '');
      return s === '' ? NaN : Number(s);
    }

    function applySortToFiltered() {
      filtered.sort(function (a, b) {
        var av = sortKey(a);
        var bv = sortKey(b);
        // Empty cells go last whichever way the column is sorted.
        if (av === '' || bv === '') return av === bv ? 0 : (av === '' ? 1 : -1);
        var an = asNumber(av);
        var bn = asNumber(bv);
        var cmp = (!isNaN(an) && !isNaN(bn)) ? (an - bn) : av.localeCompare(bv);
        return sortAsc ? cmp : -cmp;
      });
    }

    headers.forEach(function (th) {
      th.addEventListener('click', function () {
        var col = parseInt(th.dataset.col, 10);
        if (sortCol === col) {
          sortAsc = !sortAsc;
        } else {
          sortCol = col;
          sortAsc = true;
          headers.forEach(function (h) { h.removeAttribute('data-sort'); });
        }
        th.setAttribute('data-sort', sortAsc ? 'asc' : 'desc');
        applySortToFiltered();
        page = 0;
        render();
      });
    });

    if (search) search.addEventListener('input', applyFilter);
    if (prevBtn) prevBtn.addEventListener('click', function () { if (page > 0) { page--; render(); } });
    if (nextBtn) nextBtn.addEventListener('click', function () { page++; render(); });

    render();
  });

  // ── Toggle ───────────────────────────────────────────────────────────────────

  document.querySelectorAll('.bf-toggle__header').forEach(function (header) {
    var bodyId = header.getAttribute('aria-controls');
    var body   = bodyId ? document.getElementById(bodyId) : header.nextElementSibling;

    // Start collapsed (HTML already sets hidden + aria-expanded="false").
    function toggle() {
      var expanded = header.getAttribute('aria-expanded') === 'true';
      header.setAttribute('aria-expanded', String(!expanded));
      if (body) body.hidden = expanded;
    }

    header.addEventListener('click', toggle);
    header.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
    });
  });

})();
