/* briefing lab: linked selection (#21, #238) — a bar or a cell of a lab block built with
   selects= keeps its rows in a DataDive or a DataTable. A click selects it; Shift+click adds
   another of the same chart; clicking it again, the chip's × in the receiver, or Esc clears.
   The selection travels as a bf:select event on the report's root, with one self-contained test
   per pick (lab/_select.py lists the kinds), so nothing crosses into another report.
   window.briefingSelection.compile turns those tests into a row filter; the DataDive (lab.js)
   and the DataTable (here) both use it. Vanilla JS. */
(function () {
  'use strict';

  // ── the tests ──
  // column(name) gives a receiver's column as renderers/columns.py encodes it: numbers and
  // dates (epoch ms) in values, categories as levels and codes. A test on a column the
  // receiver lacks, or holds as another kind, gives null: the selection doesn't apply there.
  function compileOne(t, column) {
    if (!t) return null;
    if (t.kind === 'all') {
      var parts = (t.tests || []).map(function (s) { return compileOne(s, column); });
      if (!parts.length || parts.some(function (p) { return p === null; })) return null;
      return function (i) { return parts.every(function (p) { return p(i); }); };
    }
    var c = column(t.column);
    if (!c) return null;
    if (t.kind === 'value') {
      if (c.kind !== 'categorical') return null;
      var k = c.levels.indexOf(t.value);
      return function (i) { return k >= 0 && c.codes[i] === k; };
    }
    if (c.kind === 'categorical') return null;
    var values = c.values;
    if (t.kind === 'range') {
      var both = t.closed === 'both';
      return function (i) {
        var v = values[i];
        if (v === null || v === undefined) return false;
        return v >= t.min && (both ? v <= t.max : v < t.max);
      };
    }
    if (t.kind === 'bin') {
      // The value's bin, found exactly as Python binned it (same minimum, maximum, scale, bins).
      var unit = t.unit || 1, s = t.scale, low = t.min * s, span = t.max * s - t.min * s;
      return function (i) {
        var v = values[i];
        if (v === null || v === undefined) return false;
        v = v * unit;
        if (v < t.min || v > t.max) return false;
        if (t.min === t.max) return t.bin === 0;
        return Math.min(Math.floor((v * s - low) / span * t.bins), t.bins - 1) === t.bin;
      };
    }
    return null;
  }

  // A row matches a selection when any of its tests holds; null when none applies here.
  function compile(tests, column) {
    var parts = (tests || []).map(function (t) { return compileOne(t, column); })
      .filter(function (p) { return p !== null; });
    if (!parts.length) return null;
    return function (i) { return parts.some(function (p) { return p(i); }); };
  }

  window.briefingSelection = { compile: compile };

  // ── the senders ──
  var senders = [];  // every sender's clear(), for Esc

  function testOf(chart, hit) {
    var own = hit.getAttribute('data-bf-test');  // a cell's own test (a calendar day…)
    try {
      if (own) return JSON.parse(own);
      var test = JSON.parse(chart.getAttribute('data-bf-test')), column = chart.getAttribute('data-bf-column');
      var pick = hit.getAttribute('data-bf-pick');
      if (test.kind === 'values') return { kind: 'value', column: column, value: pick };
      if (test.kind === 'bins') {
        return { kind: 'bin', column: column, min: test.min, max: test.max, scale: test.scale, bins: test.bins,
                 unit: test.unit, bin: +pick };
      }
    } catch (e) { return null; }
    return null;
  }

  function setup(root, block) {
    var targets, source = block.getAttribute('data-bf-source'), from = block.getAttribute('data-bf-from');
    try { targets = JSON.parse(block.getAttribute('data-bf-selects')); } catch (e) { return; }
    var state = { chart: null, picks: [] };  // the chart whose bars are selected, and which

    function hitsOf(chart) { return chart ? chart.querySelectorAll('.bf-sel__hit') : []; }

    function mark() {
      block.querySelectorAll('.bf-sel__hit').forEach(function (hit) {
        var on = !!state.chart && state.chart.contains(hit) && state.picks.indexOf(hit.getAttribute('data-bf-pick')) >= 0;
        hit.setAttribute('aria-pressed', on ? 'true' : 'false');
      });
    }

    function send() {
      var detail = { targets: targets, source: source, from: from, column: null, any: [], picks: [], labels: [] };
      if (state.chart && state.picks.length) {
        detail.column = state.chart.getAttribute('data-bf-column');
        detail.picks = state.picks.slice();
        hitsOf(state.chart).forEach(function (hit) {
          if (detail.picks.indexOf(hit.getAttribute('data-bf-pick')) < 0) return;
          var test = testOf(state.chart, hit);
          if (test) detail.any.push(test);
          detail.labels.push(hit.getAttribute('data-bf-label'));
        });
      }
      root.dispatchEvent(new CustomEvent('bf:select', { detail: detail }));
    }

    function clear(quietly) {
      if (!state.chart) return;
      state.chart = null;
      state.picks = [];
      mark();
      if (!quietly) send();
    }

    // A click selects this bar; again, unselects it. Shift adds it to the bars of the same chart.
    function choose(chart, hit, adding) {
      var pick = hit.getAttribute('data-bf-pick'), at = state.picks.indexOf(pick);
      if (state.chart === chart && at >= 0) {
        state.picks.splice(at, 1);
        if (!state.picks.length) state.chart = null;
      } else if (adding && state.chart === chart) {
        state.picks.push(pick);
      } else {
        state.chart = chart;
        state.picks = [pick];
      }
      mark();
      send();
    }

    block.querySelectorAll('[data-bf-column]').forEach(function (chart) {
      hitsOf(chart).forEach(function (hit) {
        hit.addEventListener('click', function (e) { choose(chart, hit, e.shiftKey); });
        hit.addEventListener('keydown', function (e) {
          if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); choose(chart, hit, e.shiftKey); }
        });
      });
    });
    // A receiver's × on the chip: forget the selection, without sending it again.
    root.addEventListener('bf:unselect', function (e) {
      if (e.detail && e.detail.source === source) clear(true);
    });
    senders.push(clear);
  }

  // ── a DataTable as a receiver ──
  // It keeps the rows every selection holds (search, sort, paging and the CSV button apply
  // within them) and shows each selection as a chip in its toolbar.
  function receive(root, table) {
    var script = table.querySelector('script.bf-dt__values'), data;
    if (!script) return;
    try {
      var text = JSON.parse(script.textContent);
      data = script.hasAttribute('data-size')
        ? JSON.parse(window.briefingUnpack(text, Number(script.getAttribute('data-size')))) : text;
    } catch (e) { return; }
    var columns = data.columns || {}, selections = {}, order = [];
    var chips = document.createElement('span');
    chips.className = 'bf-sel__chips';
    var toolbar = table.querySelector('.bf-dt__toolbar');
    if (toolbar) toolbar.appendChild(chips);

    function column(name) { return columns.hasOwnProperty(name) ? columns[name] : null; }

    function refilter() {
      if (!table.briefingTable) return;
      var tests = order.map(function (source) { return selections[source].test; });
      table.briefingTable.filter(tests.length ? function (i) {
        for (var k = 0; k < tests.length; k++) if (!tests[k](i)) return false;
        return true;
      } : null);
    }

    function drop(source) {
      var sel = selections[source];
      if (!sel) return;
      if (sel.chip.parentNode) sel.chip.parentNode.removeChild(sel.chip);
      delete selections[source];
      order.splice(order.indexOf(source), 1);
    }

    root.addEventListener('bf:select', function (e) {
      var d = e.detail;
      if (!d || !d.targets || d.targets.indexOf(table.id) < 0) return;
      drop(d.source);
      var test = d.any && d.any.length ? compile(d.any, column) : null;
      if (test) {
        var chip = document.createElement('span');
        chip.className = 'bf-sel__chip';
        var name = document.createElement('span');
        name.className = 'bf-sel__chip-name';
        name.textContent = d.column;
        chip.appendChild(name);
        chip.appendChild(document.createTextNode(' ' + d.labels.join(', ') + ' · from ' + d.from));
        var remove = document.createElement('button');
        remove.type = 'button';
        remove.className = 'bf-sel__chip-remove';
        remove.textContent = '×';
        remove.setAttribute('aria-label', 'Clear the selection from ' + d.from);
        remove.addEventListener('click', function () {
          drop(d.source);
          root.dispatchEvent(new CustomEvent('bf:unselect', { detail: { source: d.source } }));
          refilter();
        });
        chip.appendChild(remove);
        chips.appendChild(chip);
        selections[d.source] = { test: test, chip: chip };
        order.push(d.source);
      }
      refilter();
    });
    table.briefingSelect = { selections: function () { return order.slice(); } };  // for tests
  }

  window.briefing.register('select', function (runtime) {
    runtime.on(document, 'keydown', function (e) {
      if (e.key === 'Escape' || e.key === 'Esc') senders.forEach(function (clear) { clear(false); });
    });
    return function (root) {
      root.querySelectorAll('[data-bf-selects]').forEach(function (block) { setup(root, block); });
      root.querySelectorAll('.bf-datatable').forEach(function (table) { receive(root, table); });
    };
  });
})();
