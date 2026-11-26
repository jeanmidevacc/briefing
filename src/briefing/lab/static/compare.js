/* briefing lab: DataCompare (#17) — sort, search and filter the rows, and redraw the charts as
   percentages or counts, on a linear or log scale, with each dataset's deciles. The charts Python
   drew (percentages, linear) stay until a control changes; this script draws them again from
   script.bf-cmp__data with the same geometry (lab/_render_compare.py). Vanilla JS. */
(function () {
  'use strict';

  var SVG = 'http://www.w3.org/2000/svg';
  // The chart's geometry, as in _render_compare.py.
  var W = 320, TOP = 4, BOTTOM = 92, BARS = 10, LABEL = 24, LEFT = 104;

  function color(k) { return 'var(--bf-cmp-' + (k % 8) + ')'; }

  function short(text) { return text.length <= LABEL ? text : text.slice(0, LABEL - 1) + '…'; }

  function node(svg, tag, attrs, text) {
    var el = svg.ownerDocument.createElementNS(SVG, tag);
    Object.keys(attrs).forEach(function (key) { el.setAttribute(key, String(attrs[key])); });
    if (text !== undefined) el.textContent = text;
    svg.appendChild(el);
    return el;
  }

  function clear(svg) { while (svg.firstChild) svg.removeChild(svg.firstChild); }

  function fixed(v) { return (Math.round(v * 10) / 10).toFixed(1); }

  // What a bar or a bin shows: a share of the dataset's values (in %) or a count, maybe on a log scale.
  function value(count, n, view) {
    var v = view.unit === 'count' ? count : (n ? count / n * 100 : 0);
    return view.log ? Math.log(1 + v) / Math.LN10 : v;
  }

  function pct(share) {
    if (share > 0 && share < 0.001) return '<0.1%';
    return (share * 100).toFixed(1) + '%';
  }

  function axis(svg) {
    node(svg, 'line', { x1: 0, y1: BOTTOM, x2: W, y2: BOTTOM, 'class': 'bf-cmp__axis' });
  }

  function histogram(svg, column, view) {
    clear(svg);
    var top = 0, bins = 0;
    column.sides.forEach(function (side) {
      if (!side || !side.n) return;
      bins = Math.max(bins, side.counts.length);
      side.counts.forEach(function (c) { top = Math.max(top, value(c, side.n, view)); });
    });
    if (!top) return;
    var step = W / bins, height = BOTTOM - TOP;
    column.sides.forEach(function (side, k) {
      if (!side || !side.n) return;
      var d = 'M0 ' + BOTTOM;
      side.counts.forEach(function (c, i) {
        var y = fixed(BOTTOM - value(c, side.n, view) / top * height);
        d += 'L' + fixed(i * step) + ' ' + y + 'L' + fixed((i + 1) * step) + ' ' + y;
      });
      node(svg, 'path', {
        d: d + 'L' + W + ' ' + BOTTOM + 'Z', fill: color(k), 'fill-opacity': 0.16, stroke: color(k),
        'stroke-width': 1.5, 'vector-effect': 'non-scaling-stroke'
      });
    });
    axis(svg);
    if (view.deciles && column.kind === 'numeric' && column.range) deciles(svg, column);
  }

  // Each dataset's deciles as ticks on a strip at the top of the chart, its median taller.
  function deciles(svg, column) {
    var lo = column.range[0], hi = column.range[1];
    column.sides.forEach(function (side, k) {
      if (!side || !side.deciles) return;
      var group = node(svg, 'g', { 'class': 'bf-cmp__deciles', stroke: color(k), 'stroke-width': 1.5,
                                   'vector-effect': 'non-scaling-stroke' });
      node(group, 'title', {}, 'deciles');
      side.deciles.forEach(function (d, i) {
        var x = hi > lo ? (d - lo) / (hi - lo) * W : W / 2;
        var y = TOP + k * 10;
        node(group, 'line', { x1: fixed(x), x2: fixed(x), y1: y, y2: y + (i === 4 ? 9 : 6),
                              'vector-effect': 'non-scaling-stroke' });
      });
    });
  }

  function bars(svg, column, view, names) {
    clear(svg);
    var labels = column.other ? column.labels.slice(0, -1) : column.labels;
    var drawn = labels.slice(0, BARS);
    var rows = drawn.map(function (label, i) {
      return { label: label, other: false, pick: function (counts) { return counts[i]; } };
    });
    if (column.labels.length > drawn.length) {
      rows.push({ label: 'other', other: true, pick: function (counts) {
        return counts.slice(drawn.length).reduce(function (a, b) { return a + b; }, 0);
      } });
    }
    var datasets = column.sides.length;
    var bar = datasets <= 3 ? 6 : 4, rowH = bar * datasets + 6, width = W - 108;
    var top = 0;
    rows.forEach(function (row) {
      column.sides.forEach(function (side) {
        if (side && side.n) top = Math.max(top, value(row.pick(side.counts), side.n, view));
      });
    });
    top = top || 1;
    rows.forEach(function (row, r) {
      var y0 = r * rowH;
      node(svg, 'text', { x: LEFT - 6, y: fixed(y0 + rowH / 2 + 3), 'text-anchor': 'end',
                          'class': row.other ? 'bf-cmp__label bf-cmp__label--other' : 'bf-cmp__label' },
           short(row.label));
      column.sides.forEach(function (side, k) {
        if (!side || !side.n) return;
        var count = row.pick(side.counts);
        var rect = node(svg, 'rect', {
          x: LEFT, y: fixed(y0 + 3 + k * bar), width: fixed(value(count, side.n, view) / top * width),
          height: fixed(bar - 1), fill: color(k)
        });
        node(rect, 'title', {}, names[k] + ' · ' + row.label + ': ' + pct(count / side.n) + ' (' +
             count.toLocaleString('en-US') + ')');
      });
    });
  }

  // The share (or count) of the values the top *rank* values cover; a log scale spreads the ranks.
  function curves(svg, column, view) {
    clear(svg);
    var longest = 0, most = 0;
    column.sides.forEach(function (side) {
      if (!side || !side.curve) return;
      longest = Math.max(longest, side.curve[side.curve.length - 1][0]);
      most = Math.max(most, side.n);
    });
    if (!longest) return;
    var height = BOTTOM - TOP;
    function x(rank) {
      if (view.log) return longest > 1 ? Math.log(rank) / Math.log(longest) * W : 0;
      return (rank - 1) / Math.max(1, longest - 1) * W;
    }
    column.sides.forEach(function (side, k) {
      if (!side || !side.curve) return;
      var points = side.curve.map(function (point) {
        var y = view.unit === 'count' ? point[1] * side.n / most : point[1];
        return fixed(x(point[0])) + ',' + fixed(BOTTOM - y * height);
      }).join(' ');
      node(svg, 'polyline', { points: points, fill: 'none', stroke: color(k), 'stroke-width': 1.5,
                              'vector-effect': 'non-scaling-stroke' });
    });
    axis(svg);
  }

  function redraw(block, data, view) {
    block.querySelectorAll('.bf-cmp__row').forEach(function (row) {
      var column = data.columns[+row.getAttribute('data-i')];
      var svg = row.querySelector('svg.bf-cmp__svg');
      if (!column || !svg) return;
      var hits = svg.querySelector('.bf-sel__hits');  // a linked selection's bar targets (#21) stay on top
      if (hits) svg.removeChild(hits);
      if (column.kind !== 'categorical') histogram(svg, column, view);
      else if (column.sides.some(function (side) { return side && side.curve; })) curves(svg, column, view);
      else bars(svg, column, view, data.names);
      if (hits) svg.appendChild(hits);
    });
  }

  // ── sorting and filtering ──

  function key(row, sort) {
    var raw = row.getAttribute('data-' + sort.replace('_', '-'));
    return raw === null || raw === '' ? null : parseFloat(raw);
  }

  function byName(a, b) {
    var x = a.getAttribute('data-name'), y = b.getAttribute('data-name');
    var lx = x.toLowerCase(), ly = y.toLowerCase();
    return lx < ly ? -1 : lx > ly ? 1 : x < y ? -1 : x > y ? 1 : 0;
  }

  function sortRows(list, sort) {
    var rows = Array.prototype.slice.call(list.querySelectorAll(':scope > .bf-cmp__row'));
    rows.sort(function (a, b) {
      if (sort === 'name') return byName(a, b);
      var x = key(a, sort), y = key(b, sort);
      if (x === null || y === null) return x === y ? byName(a, b) : x === null ? 1 : -1;
      return y - x || byName(a, b);
    });
    rows.forEach(function (row) { list.appendChild(row); });
  }

  function filter(block, list, shown) {
    var query = block.querySelector('.bf-cmp__search').value.trim().toLowerCase();
    var kinds = {};
    block.querySelectorAll('.bf-cmp__kind-filter').forEach(function (box) { kinds[box.value] = box.checked; });
    var rows = list.querySelectorAll(':scope > .bf-cmp__row'), visible = 0;
    rows.forEach(function (row) {
      var hit = kinds[row.getAttribute('data-kind')] !== false &&
        row.getAttribute('data-name').toLowerCase().indexOf(query) !== -1;
      row.hidden = !hit;
      if (hit) visible += 1;
    });
    shown.textContent = visible === rows.length ? '' : visible + ' of ' + rows.length + ' columns';
  }

  function setup(block) {
    var script = block.querySelector('script.bf-cmp__data');
    var controls = block.querySelector('.bf-cmp__controls');
    var list = block.querySelector('.bf-cmp__rows');
    if (!script || !controls || !list) return;
    var data;
    try { data = JSON.parse(script.textContent); } catch (e) { return; }
    var view = { unit: 'share', log: false, deciles: false };
    var shown = controls.querySelector('.bf-cmp__shown');
    controls.hidden = false;

    controls.querySelector('.bf-cmp__sort').addEventListener('change', function (e) {
      sortRows(list, e.target.value);
    });
    controls.querySelector('.bf-cmp__search').addEventListener('input', function () { filter(block, list, shown); });
    controls.querySelectorAll('.bf-cmp__kind-filter').forEach(function (box) {
      box.addEventListener('change', function () { filter(block, list, shown); });
    });
    controls.querySelectorAll('.bf-cmp__unit').forEach(function (button) {
      button.addEventListener('click', function () {
        view.unit = button.getAttribute('data-unit');
        controls.querySelectorAll('.bf-cmp__unit').forEach(function (b) {
          b.setAttribute('aria-pressed', String(b === button));
        });
        redraw(block, data, view);
      });
    });
    controls.querySelector('.bf-cmp__log').addEventListener('change', function (e) {
      view.log = e.target.checked;
      redraw(block, data, view);
    });
    var decileBox = controls.querySelector('.bf-cmp__deciles');
    if (decileBox) {
      decileBox.addEventListener('change', function (e) {
        view.deciles = e.target.checked;
        redraw(block, data, view);
      });
    }
    block.briefingCompare = { view: view, redraw: function () { redraw(block, data, view); } };  // for tests
  }

  window.briefing.register('compare', function () {
    return function (root) {
      root.querySelectorAll('.bf-compare').forEach(setup);
    };
  });
})();
