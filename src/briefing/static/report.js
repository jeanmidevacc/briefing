/* briefing report — the shared runtime (window.briefing) and the core behaviour: charts, tabs,
   dropdowns, DataTable, toggles and print. Vanilla JS, no deps. */
(function () {
  'use strict';

  // ── Runtime ──────────────────────────────────────────────────────────────────
  // One per page, shared by every briefing report or fragment on it. Each script registers
  // a part: make(runtime) runs once per page and returns setup(root), which briefing.init(root)
  // runs on that root, once (the root's data-bf-ready flag says it is done). Parts query from
  // their root only, add page-wide listeners only through runtime.on, and do their print
  // work through runtime.onPrint, which the runtime calls on beforeprint and afterprint.

  if (!window.briefing) {
    window.briefing = (function () {
      var parts = [], roots = [], registered = {}, printHooks = [], printing = false;

      function on(target, type, handler, capture) { target.addEventListener(type, handler, !!capture); }

      on(window, 'beforeprint', function () {
        if (printing) return;
        printing = true;
        printHooks.forEach(function (hook) { hook.before(); });
      });
      on(window, 'afterprint', function () {
        if (!printing) return;
        printing = false;
        printHooks.forEach(function (hook) { hook.after(); });
      });

      var runtime = {
        on: on,
        onPrint: function (before, after) { printHooks.push({ before: before, after: after }); }
      };

      return {
        register: function (name, make) {
          if (registered[name]) return;  // the same script, inlined again by another output
          registered[name] = true;
          var setup = make(runtime);
          parts.push(setup);
          roots.forEach(function (root) { setup(root); });  // roots initialized before it came
        },
        init: function (root) {
          var flag = root.documentElement || root;  // a document is flagged on its <html>
          if (flag.hasAttribute('data-bf-ready')) return;
          flag.setAttribute('data-bf-ready', '');
          roots.push(root);
          parts.forEach(function (setup) { setup(root); });
        }
      };
    })();
  }

  // Plotly sizes a chart when it draws it; one drawn while hidden keeps the 700 px
  // default. Redraw the charts inside a panel once that panel is shown.
  function resizePlots(root) {
    if (!root) return;
    var plotly = window.Plotly;
    if (plotly && plotly.Plots) {
      root.querySelectorAll('.js-plotly-plot').forEach(function (el) { plotly.Plots.resize(el); });
    }
    // Vega sizes width="container" charts on window resize.
    if (root.querySelector('.bf-altair')) window.dispatchEvent(new Event('resize'));
  }

  // ── Altair (Vega-Lite) ───────────────────────────────────────────────────────

  function drawAltair(el) {
    var specEl = el.nextElementSibling;
    if (!window.vegaEmbed || !specEl) return;
    // No actions menu: it links to the online Vega editor.
    window.vegaEmbed(el, JSON.parse(specEl.textContent), { actions: false, renderer: 'svg' })
      .catch(function (err) { el.textContent = 'This chart could not be drawn: ' + err; });
  }

  function thousands(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

  // ── Select / tabs ───────────────────────────────────────────────────────────

  function setupTabs(sel, root) {
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
      resizePlots(panels[idx]);
    }

    tabs.forEach(function (tab, i) {
      tab.addEventListener('click', function () { activate(i); panelChosen(root, panels[i]); });

      // Arrow-key navigation for accessibility.
      tab.addEventListener('keydown', function (e) {
        var j = e.key === 'ArrowRight' ? Math.min(i + 1, tabs.length - 1)
          : e.key === 'ArrowLeft' ? Math.max(i - 1, 0)
          : e.key === 'Home' ? 0
          : e.key === 'End' ? tabs.length - 1 : -1;
        if (j < 0) return;
        activate(j);
        tabs[j].focus();
        panelChosen(root, panels[j]);
      });
    });

    activate(0);
  }

  // ── Select / dropdown ────────────────────────────────────────────────────────

  function setupDropdown(sel, root) {
    var select = sel.querySelector(':scope > .bf-select__select');
    var panels = Array.from(sel.querySelectorAll(':scope > .bf-select__panel'));

    var shown = 0;

    function activate(idx) {
      shown = idx;
      panels.forEach(function (p, i) { p.hidden = i !== idx; });
      if (select && panels[idx] && panels[idx].id) select.setAttribute('aria-controls', panels[idx].id);
      resizePlots(panels[idx]);
    }

    if (select) {
      // 'input' too (#29): some browsers fire 'change' only when a keyboard user leaves the list.
      var choose = function () {
        var idx = parseInt(select.value, 10);
        if (idx === shown) return;
        activate(idx);
        panelChosen(root, panels[idx]);
      };
      select.addEventListener('input', choose);
      select.addEventListener('change', choose);
    }

    activate(0);
  }

  // ── DataTable ────────────────────────────────────────────────────────────────

  // The rows of a table, by number: the <tr>s of its HTML, or for a table of more than
  // DataTable.HTML_ROWS rows the cells packed as JSON in script.bf-dt__data (#38), whose
  // <tr>s are made as they show, link cells (#33) as links. Each row has the key it sorts by in a column (the
  // data-sort key Python wrote for numbers, dates and durations, else its text) and the
  // text a search looks into.
  function tableRows(container, tbody) {
    var data = container.querySelector('script.bf-dt__data');
    if (!data) {
      var trs = Array.from(tbody.rows);
      return {
        count: trs.length,
        element: function (i) { return trs[i]; },
        key: function (i, col) {
          var cell = trs[i].cells[col];
          if (!cell) return '';
          var key = cell.getAttribute('data-sort');
          return key !== null ? key : cell.textContent.trim();
        },
        text: function (i) { return trs[i].textContent; }
      };
    }
    var table = JSON.parse(window.briefingUnpack(JSON.parse(data.textContent), Number(data.getAttribute('data-size'))));
    var columns = table.text, keys = table.keys, links = table.links || {}, wrap = table.wrap || [], made = [];
    return {
      count: table.rows,
      element: function (i) {
        if (!made[i]) {
          var tr = document.createElement('tr');
          columns.forEach(function (column, col) {
            var td = document.createElement('td');
            var key = keys[col] ? keys[col][i] : null;
            var href = links[col] ? links[col][i] : null;  // a link column (#33)
            if (href) {
              var a = document.createElement('a');
              a.setAttribute('href', href);
              a.setAttribute('target', '_blank');
              a.setAttribute('rel', 'noopener noreferrer');
              a.textContent = column[i];
              td.appendChild(a);
            } else {
              td.textContent = column[i];
            }
            if (key !== null && key !== column[i]) td.setAttribute('data-sort', key);
            if (wrap.indexOf(col) !== -1) td.className = 'bf-dt__wrap';  // #151
            tr.appendChild(td);
          });
          made[i] = tr;
        }
        return made[i];
      },
      key: function (i, col) {
        var key = keys[col] ? keys[col][i] : null;
        return key !== null ? key : (columns[col] ? columns[col][i].trim() : '');
      },
      text: function (i) { return columns.map(function (column) { return column[i]; }).join(''); }
    };
  }

  function setupDataTable(container, runtime) {
    var tbody    = container.querySelector('.bf-dt__table tbody');
    var search   = container.querySelector('.bf-dt__search');
    var countEl  = container.querySelector('.bf-dt__count');
    var pageInfo = container.querySelector('.bf-dt__page-info');
    var prevBtn  = container.querySelector('.bf-dt__page-btn[data-dir="-1"]');
    var nextBtn  = container.querySelector('.bf-dt__page-btn[data-dir="1"]');
    var headers  = Array.from(container.querySelectorAll('.bf-dt__th'));

    if (!tbody) return;

    var rows      = tableRows(container, tbody);
    var all       = [];
    for (var n = 0; n < rows.count; n++) all.push(n);
    var onSlide = !!container.closest('.bf-slide');  // a deck's slide (#197) shows 10 rows and prints them
    var PAGE_SIZE = onSlide ? 10 : 25;  // PAGE_ROWS in renderers/table.py
    var PRINT_ROWS = 1000;
    var page     = 0;
    var sortCol  = -1;
    var sortAsc  = true;
    var filtered = all.slice();
    var searchText = null;  // each row's text in lower case, made on the first search
    var keep = null;  // a filter set from outside (a lab block's linked selection, #238): i -> bool

    // The tbody holds the rows on show, in their (sorted) order, and nothing else.
    function show(list) {
      var frag = document.createDocumentFragment();
      list.forEach(function (i) { frag.appendChild(rows.element(i)); });
      tbody.textContent = '';
      tbody.appendChild(frag);
    }

    function render() {
      var start = page * PAGE_SIZE;
      show(filtered.slice(start, start + PAGE_SIZE));

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
      if (q && !searchText) searchText = all.map(function (i) { return rows.text(i).toLowerCase(); });
      filtered = q ? all.filter(function (i) { return searchText[i].indexOf(q) !== -1; }) : all.slice();
      if (keep) filtered = filtered.filter(keep);
      if (sortCol >= 0) applySortToFiltered();
      page = 0;
      render();
    }

    // A key that is a whole number, optionally with thousands separators ("1,200"); else NaN.
    function asNumber(s) {
      if (/^[-+]?\d{1,3}(,\d{3})+(\.\d+)?$/.test(s)) s = s.replace(/,/g, '');
      return s === '' ? NaN : Number(s);
    }

    function applySortToFiltered() {
      filtered.sort(function (a, b) {
        var av = rows.key(a, sortCol);
        var bv = rows.key(b, sortCol);
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

    var csv = container.querySelector('.bf-dt__csv');
    if (csv) csv.addEventListener('click', function () { downloadCsv(container, csv, headers, rows, filtered); });

    if (search) search.addEventListener('input', applyFilter);
    if (prevBtn) prevBtn.addEventListener('click', function () { if (page > 0) { page--; render(); } });
    if (nextBtn) nextBtn.addEventListener('click', function () { page++; render(); });

    // Print every row matching the search, up to PRINT_ROWS, instead of one page (a slide
    // prints the page it shows).
    var printNote = null;
    if (!onSlide) runtime.onPrint(function () {
      show(filtered.slice(0, PRINT_ROWS));
      if (filtered.length > PRINT_ROWS && !printNote) {
        printNote = document.createElement('p');
        printNote.className = 'bf-dt__print-note';
        printNote.textContent = 'Printed ' + thousands(PRINT_ROWS) + ' of ' + thousands(filtered.length) + ' rows.';
        container.querySelector('.bf-dt__scroll').insertAdjacentElement('afterend', printNote);
      }
    }, function () {
      if (printNote) { printNote.remove(); printNote = null; }
      render();
    });

    // Lets other code keep only some rows, under the search, sort and paging: keep(i) says
    // whether row i (in the table's original order) stays; null keeps them all (#238).
    container.briefingTable = { filter: function (fn) { keep = fn || null; applyFilter(); } };

    render();
  }

  // ── CSV download (#34) ──────────────────────────────────────────────────────

  // One CSV field: quoted when it holds a quote, a comma or a line break, and with a ' before
  // text a spreadsheet would run as a formula (but not before a number such as -5).
  function csvField(value) {
    var text = String(value);
    if (/^[=+\-@\t\r]/.test(text) && isNaN(Number(text))) text = "'" + text;
    return /[",\r\n]/.test(text) ? '"' + text.replace(/"/g, '""') + '"' : text;
  }

  // The rows matching the search, in their order, every page: each cell's raw value (its sort
  // key: full-precision numbers, ISO dates), not its formatted text (#33). UTF-8 with a BOM, so
  // spreadsheets read accents; made in the page, with no server.
  function downloadCsv(container, button, headers, rows, filtered) {
    var lines = [headers.map(function (th) { return csvField(th.textContent.trim()); }).join(',')];
    filtered.forEach(function (i) {
      var cells = [];
      for (var col = 0; col < headers.length; col++) cells.push(csvField(rows.key(i, col)));
      lines.push(cells.join(','));
    });
    var name = button.getAttribute('data-bf-filename') || 'table.csv';
    var blob = new Blob(['\ufeff' + lines.join('\r\n') + '\r\n'], { type: 'text/csv;charset=utf-8' });
    saveFile(container, blob, name, container.querySelector('.bf-dt__csv-note'),
      'Downloaded ' + thousands(filtered.length) + ' row' + (filtered.length !== 1 ? 's' : '') + ' as ' + name + '.');
  }

  // Download *blob* as *name* from the page, and say so in *note*: in a frame, a host may block
  // downloads, so the note also says what to do then.
  function saveFile(container, blob, name, note, said) {
    var url = URL.createObjectURL(blob);
    var link = document.createElement('a');
    link.href = url;
    link.download = name;
    link.hidden = true;
    container.appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
    if (note) {
      note.textContent = said + (window.top !== window
        ? " If no file arrived, this page can't download here: open the report in its own tab." : '');
    }
  }

  // ── Attachment (#36) ─────────────────────────────────────────────────────────

  // The file is in script.bf-attachment__data: packed text (#38) or base64 bytes.
  function setupAttachment(container) {
    var button = container.querySelector('.bf-attachment__button');
    var data = container.querySelector('script.bf-attachment__data');
    if (!button || !data) return;
    button.addEventListener('click', function () {
      var encoded = JSON.parse(data.textContent);
      var content;
      if (data.hasAttribute('data-packed')) {
        content = window.briefingUnpack(encoded, Number(data.getAttribute('data-size')));
      } else {
        var binary = atob(encoded);
        content = new Uint8Array(binary.length);
        for (var i = 0; i < binary.length; i++) content[i] = binary.charCodeAt(i);
      }
      var name = button.getAttribute('data-bf-filename');
      saveFile(container, new Blob([content], { type: button.getAttribute('data-bf-type') }), name,
        container.querySelector('.bf-attachment__note'), 'Downloaded ' + name + '.');
    });
  }

  // ── Toggle ───────────────────────────────────────────────────────────────────

  function setupToggle(header, root) {
    var bodyId = header.getAttribute('aria-controls');
    var body   = bodyId ? root.querySelector('[id="' + bodyId + '"]') : header.nextElementSibling;

    // Start collapsed (HTML already sets hidden + aria-expanded="false").
    function toggle() {
      var expanded = header.getAttribute('aria-expanded') === 'true';
      header.setAttribute('aria-expanded', String(!expanded));
      if (body) body.hidden = expanded;
      if (!expanded) resizePlots(body);
    }

    header.addEventListener('click', toggle);
    header.addEventListener('keydown', function (e) {
      if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); toggle(); }
    });
  }

  // ── Print ────────────────────────────────────────────────────────────────────
  // While printing, html.bf-printing lays the report out at the paper's width
  // with every panel and toggle shown (report.css), each panel under its tab or
  // option label. Charts are resized for that width, and everything is restored
  // afterwards. The class also applies on screen, so hidden charts can be measured.
  // A root that is an element (an embedded fragment) gets the class itself.

  function setupPrint(root, runtime) {
    var flag = root.documentElement || root;
    var body = root.body || root;
    runtime.onPrint(function () {
      flag.classList.add('bf-printing');
      root.querySelectorAll('.bf-select').forEach(function (sel) {
        if (sel.closest('.bf-slide')) return;  // a slide prints its chosen tab only (#197)
        var labels = sel.classList.contains('bf-select--dropdown')
          ? Array.from(sel.querySelectorAll(':scope > .bf-select__select option'))
          : Array.from(sel.querySelectorAll(':scope > .bf-select__tablist > .bf-select__tab'));
        sel.querySelectorAll(':scope > .bf-select__panel').forEach(function (panel, i) {
          var label = document.createElement('div');
          label.className = 'bf-print-label';
          label.textContent = labels[i] ? labels[i].textContent : '';
          panel.insertAdjacentElement('beforebegin', label);
        });
      });
      resizePlots(body);
    }, function () {
      root.querySelectorAll('.bf-print-label').forEach(function (label) { label.remove(); });
      flag.classList.remove('bf-printing');
      resizePlots(body);
    });
  }

  // ── Links (#24) ──────────────────────────────────────────────────────────────
  // A named block or heading carries data-bf-link, and its link as its id: "page/name", or
  // "name" outside a named page. In a document, the address bar's #link opens the pages,
  // tabs and toggles around its target and scrolls to it, and choosing a tab writes that
  // tab's link there without adding a history entry. Inside an element root (an embedded
  // fragment) links never read or write the page's address: a link to a block in the root
  // opens and scrolls to it there.

  var revealing = false;  // set while reveal() opens tabs and toggles

  function isDocument(root) { return root.nodeType === 9; }

  function findLink(root, link) {
    return link ? root.querySelector('[data-bf-link][id="' + link.replace(/["\\]/g, '\\$&') + '"]') : null;
  }

  function linkOf(href) {
    try { return decodeURIComponent(href.slice(href.indexOf('#') + 1)); } catch (e) { return ''; }
  }

  // Open every hidden tab panel and toggle around target, outermost first, then scroll to it.
  function reveal(root, target) {
    var around = [];
    for (var node = target.parentElement; node && node !== root; node = node.parentElement) around.unshift(node);
    revealing = true;
    around.forEach(function (el) {
      if (!el.hidden) return;
      if (el.classList.contains('bf-select__panel')) {
        var sel = el.parentElement;
        var i = Array.prototype.indexOf.call(sel.querySelectorAll(':scope > .bf-select__panel'), el);
        var select = sel.querySelector(':scope > .bf-select__select');
        if (select) {
          select.value = String(i);
          select.dispatchEvent(new Event('change'));
        } else {
          sel.querySelectorAll(':scope > .bf-select__tablist > .bf-select__tab')[i].click();
        }
      } else if (el.classList.contains('bf-toggle__body') && el.previousElementSibling) {
        el.previousElementSibling.click();
      }
    });
    revealing = false;
    target.scrollIntoView();
  }

  // The link of what a chosen panel shows: its block's, else the closest named block around it.
  function panelChosen(root, panel) {
    if (revealing || !isDocument(root)) return;
    var named = panel.querySelector(':scope > [data-bf-link]');
    for (var node = panel.parentElement; !named && node && node !== root; node = node.parentElement) {
      if (node.hasAttribute('data-bf-link')) named = node;
    }
    history.replaceState(history.state, '', named ? '#' + named.id : location.pathname + location.search);
  }

  function setupLinks(root, runtime) {
    if (isDocument(root)) {
      var follow = function () {
        var target = findLink(root, linkOf(location.hash));
        if (target) reveal(root, target);
      };
      follow();
      runtime.on(window, 'hashchange', follow);
    } else {
      root.addEventListener('click', function (e) {
        var a = e.target.closest ? e.target.closest('a[href^="#"]') : null;
        var target = a && root.contains(a) ? findLink(root, linkOf(a.getAttribute('href'))) : null;
        if (!target) return;
        e.preventDefault();
        reveal(root, target);
      });
    }
    // A named heading's icon copies its link (in a document; in a fragment it just goes there).
    root.querySelectorAll('.bf-heading-link').forEach(function (icon) {
      icon.addEventListener('click', function (e) {
        if (!isDocument(root)) return;
        e.preventDefault();
        history.replaceState(history.state, '', icon.getAttribute('href'));
        if (navigator.clipboard) navigator.clipboard.writeText(location.href).catch(function () {});
        icon.setAttribute('data-copied', '');
        setTimeout(function () { icon.removeAttribute('data-copied'); }, 1500);
      });
    });
  }

  window.briefing.register('report', function (runtime) {
    return function (root) {
      root.querySelectorAll('.bf-altair').forEach(drawAltair);
      root.querySelectorAll('.bf-select:not(.bf-select--dropdown)').forEach(function (sel) { setupTabs(sel, root); });
      root.querySelectorAll('.bf-select--dropdown').forEach(function (sel) { setupDropdown(sel, root); });
      root.querySelectorAll('.bf-datatable').forEach(function (container) { setupDataTable(container, runtime); });
      root.querySelectorAll('.bf-attachment').forEach(setupAttachment);
      root.querySelectorAll('.bf-toggle__header').forEach(function (header) { setupToggle(header, root); });
      setupPrint(root, runtime);
      setupLinks(root, runtime);
    };
  });

})();
