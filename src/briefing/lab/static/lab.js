/* briefing.lab — DataDive interactive dot explorer, drawn on a canvas (#16). Vanilla JS, no deps.
   Inlined into a report only when a DataDive block is present. Its data comes packed by column in
   script.bf-dd__data (window.briefingUnpack opens it); the dots go on a <canvas>, the axes and
   labels in an SVG on top of it, and the legend under the controls hides or shows a category. */
(function () {
  'use strict';

  // The theme's categorical hues for light and dark pages (Formatting.CATEGORICAL_LIGHT and
  // _DARK): the accent comes first, then the hues that stay apart from it, as in
  // Formatting.categorical().
  var LIGHT = ['#005b8b', '#ee5e23', '#00a16e', '#b56ae7', '#9f0051', '#a44d00', '#6c4bcc'];
  var DARK = ['#00c3fc', '#ee5e23', '#4ca77b', '#a670f3', '#fcdf00', '#ff89bf', '#ffa10e'];
  var MISSING = '#9ca3af';
  var BLANK = '(blank)';
  var DIM = '\u0000dim';  // the group of dots that don't match, in Highlight mode
  var LEGEND_MAX = 24;  // categories listed before "+N more"
  var MOTION_MAX = 30000;  // above this many dots, a change redraws at once: each frame would take too long
  var PRINT_VECTOR = 5000;  // up to this many dots print as SVG circles (vector PDFs); more print as the canvas

  // ── colours ─────────────────────────────────────────────────────────────────

  var probe = null;
  // Any CSS colour as [r, g, b], or null.
  function rgbOf(css) {
    if (!css) return null;
    if (!probe) probe = document.createElement('canvas').getContext('2d');
    probe.fillStyle = '#000';
    probe.fillStyle = css.trim();
    var c = probe.fillStyle, m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})$/i.exec(c);
    if (m) return [parseInt(m[1], 16), parseInt(m[2], 16), parseInt(m[3], 16)];
    m = /rgba?\(([^)]+)\)/.exec(c);
    return m ? m[1].split(',').slice(0, 3).map(function (v) { return Math.round(+v); }) : null;
  }
  function hex(c) {
    return '#' + c.map(function (v) { return ('0' + Math.max(0, Math.min(255, Math.round(v))).toString(16)).slice(-2); }).join('');
  }
  function mix(a, b, t) { return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t]; }
  function apart(a, b) {
    var d = 0;
    for (var k = 0; k < 3; k++) d += (a[k] - b[k]) * (a[k] - b[k]);
    return Math.sqrt(d) > 90;
  }

  // The theme, read from the CSS variables on the block: palette, ramp ends, missing colour.
  function theme(el) {
    var style = getComputedStyle(el);
    var accent = rgbOf(style.getPropertyValue('--bf-accent')) || [79, 70, 229];
    var bg = rgbOf(style.getPropertyValue('--bf-bg')) || [255, 255, 255];
    var text = rgbOf(style.getPropertyValue('--bf-text')) || [17, 24, 39];
    var dark = (0.299 * bg[0] + 0.587 * bg[1] + 0.114 * bg[2]) / 255 < 0.5;
    var palette = [hex(accent)];
    (dark ? DARK : LIGHT).forEach(function (c) { if (apart(rgbOf(c), accent)) palette.push(c); });
    var stops = [mix(bg, accent, 0.38), accent, mix(accent, text, 0.55)];
    var ramp = [];
    for (var i = 0; i < 64; i++) {
      var t = i / 63 * 2, k = Math.min(1, Math.floor(t));
      ramp.push(hex(mix(stops[k], stops[k + 1], t - k)));
    }
    return { palette: palette, ramp: ramp, dim: hex(mix(bg, text, 0.45)), bg: hex(bg) };
  }

  // ── text ────────────────────────────────────────────────────────────────────

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function cut(s, n) { return s.length > n ? s.slice(0, n - 1) + '…' : s; }
  // 12,345 but 2024: four digits stay as they are, so years read as years.
  function thousands(s) { return s.length > 4 ? s.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : s; }
  function fmtNum(v) {
    if (Math.round(v) === v && Math.abs(v) < 1e15) return (v < 0 ? '-' : '') + thousands(String(Math.abs(v)));
    var p = String(+v.toPrecision(5)), parts = p.split('.');
    return parts[0].indexOf('e') < 0 ? thousands(parts[0]) + (parts[1] ? '.' + parts[1] : '') : p;
  }
  function fmtTick(v) {
    var a = Math.abs(v);
    if (a >= 1e9) return +(v / 1e9).toPrecision(3) + 'B';
    if (a >= 1e6) return +(v / 1e6).toPrecision(3) + 'M';
    if (a >= 1e4) return +(v / 1e3).toPrecision(3) + 'k';
    return fmtNum(+v.toPrecision(6));
  }
  var MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  function pad(n) { return (n < 10 ? '0' : '') + n; }
  function fmtDate(ms, withTime) {
    var d = new Date(ms);
    var day = d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate());
    var time = pad(d.getUTCHours()) + ':' + pad(d.getUTCMinutes());
    return withTime && time !== '00:00' ? day + ' ' + time : day;
  }
  function natural(a, b) { return a.localeCompare(b, undefined, { numeric: true }); }

  // ── the data ────────────────────────────────────────────────────────────────

  function load(container) {
    var el = container.querySelector('script.bf-dd__data');
    var payload = JSON.parse(window.briefingUnpack(JSON.parse(el.textContent), Number(el.getAttribute('data-size'))));
    var cols = {}, names = [];
    payload.columns.forEach(function (c) {
      names.push(c.name);
      cols[c.name] = c;
      if (c.kind === 'categorical') {
        c.counts = c.levels.map(function () { return 0; });
        c.blanks = 0;
        c.codes.forEach(function (k) { if (k < 0) c.blanks++; else c.counts[k]++; });
      } else {
        var lo = Infinity, hi = -Infinity;
        c.values.forEach(function (v) { if (v !== null) { if (v < lo) lo = v; if (v > hi) hi = v; } });
        c.lo = lo; c.hi = hi; c.empty = lo > hi;
      }
    });
    var scaleEl = container.querySelector('script.bf-dd__scale');
    return { n: payload.rows, cols: cols, names: names, scale: scaleEl ? JSON.parse(scaleEl.textContent) : null,
             thumbs: payload.thumbs || null };
  }

  // A cell as text for the tooltip, or null when it is missing.
  function display(col, i) {
    if (col.kind === 'categorical') { var k = col.codes[i]; return k < 0 ? null : col.levels[k]; }
    var v = col.values[i];
    if (v === null) return null;
    return col.kind === 'datetime' ? fmtDate(v, true) : fmtNum(v);
  }

  // A deterministic jitter in [-0.5, 0.5) for row i, so categories spread their dots the same way each time.
  function jitter(i, salt) { return ((Math.imul(i * 2 + salt + 1, 2654435761) >>> 0) / 4294967296) - 0.5; }

  // The levels of a category column in axis order (natural), with the blank last when there is one.
  function axisLevels(col) {
    var order = col.levels.map(function (_, k) { return k; });
    order.sort(function (a, b) { return natural(col.levels[a], col.levels[b]); });
    return order;
  }

  // ── axes ────────────────────────────────────────────────────────────────────

  function niceTicks(a, b, count) {
    var span = b - a;
    if (!(span > 0)) return [a];
    var step = Math.pow(10, Math.floor(Math.log(span / count) / Math.LN10)), err = span / count / step;
    if (err >= 7.5) step *= 10; else if (err >= 3.5) step *= 5; else if (err >= 1.5) step *= 2;
    var out = [];
    for (var v = Math.ceil(a / step) * step; v <= b + step * 1e-9; v += step) out.push(+v.toFixed(10));
    return out;
  }

  // A round width at least raw: 1, 2, 2.5 or 5 times a power of ten.
  function niceStep(raw) {
    var p = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), f = raw / p;
    return (f <= 1 ? 1 : f <= 2 ? 2 : f <= 2.5 ? 2.5 : f <= 5 ? 5 : 10) * p;
  }

  // Ticks on round dates: years, months, days or hours, at most about `most`.
  function timeTicks(a, b, most) {
    var HOUR = 36e5, DAY = 864e5, span = b - a, out = [], d = new Date(a), step, label;
    if (span > 3 * 365 * DAY) {
      step = Math.max(1, Math.ceil(span / (365.25 * DAY) / (most - 1)));
      for (var y = d.getUTCFullYear(); ; y += step) {
        var at = Date.UTC(y, 0, 1);
        if (at > b) break;
        if (at >= a) out.push({ at: at, label: String(y) });
      }
      return out;
    }
    if (span > 60 * DAY) {
      var months = span / (30.44 * DAY);
      step = [1, 2, 3, 6, 12].filter(function (s) { return months / s <= most; })[0] || 12;
      for (var m = d.getUTCFullYear() * 12 + d.getUTCMonth(); ; m++) {
        var t = Date.UTC(Math.floor(m / 12), m % 12, 1);
        if (t > b) break;
        if (t >= a && (m % 12) % step === 0) {
          label = MONTHS[m % 12] + (m % 12 === 0 || !out.length ? ' ' + Math.floor(m / 12) : '');
          out.push({ at: t, label: label });
        }
      }
      return out;
    }
    var unit = span > 2 * DAY ? DAY : HOUR;
    var steps = unit === DAY ? [1, 2, 7, 14, 28] : [1, 3, 6, 12];
    step = steps.filter(function (s) { return span / (s * unit) <= most; })[0] || steps[steps.length - 1];
    var first = Math.ceil(a / (step * unit)) * step * unit;
    for (var v = first; v <= b; v += step * unit) {
      out.push({ at: v, label: unit === DAY ? fmtDate(v, false).slice(5) : fmtDate(v, true).slice(11) });
    }
    return out;
  }

  // Where each row sits along one axis, from lo to hi px: numbers and dates on a linear scale,
  // categories in bands with a little jitter. {pos: Float32Array (NaN when missing), ticks, title}
  // w0 and w1 are the zoom window: the part of the full range shown, as fractions (0 and 1: all of it).
  function axis(col, n, lo, hi, salt, w0, w1) {
    var pos = new Float32Array(n), ticks = [], i;
    if (w0 === undefined) { w0 = 0; w1 = 1; }
    var zoom = 1 / (w1 - w0);
    if (col.kind === 'categorical') {
      var order = axisLevels(col), slot = {}, bands = order.length + (col.blanks ? 1 : 0) || 1;
      order.forEach(function (k, j) { slot[k] = j; });
      var at = function (f) { return lo + (f - w0) * zoom * (hi - lo); };  // f: a fraction of the full range
      for (i = 0; i < n; i++) {
        var k = col.codes[i], j = k < 0 ? bands - 1 : slot[k];
        pos[i] = at((j + 0.5 + jitter(i, salt) * 0.7) / bands);
      }
      var seen = Math.max(1, bands / zoom);
      var every = Math.max(1, Math.ceil(seen / Math.max(2, Math.floor(Math.abs(hi - lo) / 60))));
      var labels = order.map(function (k) { return col.levels[k]; });
      if (col.blanks) labels.push(BLANK);
      labels.forEach(function (label, j) {
        var f = (j + 0.5) / bands;
        if (j % every === 0 && f >= w0 && f <= w1) ticks.push({ at: at(f), label: cut(label, 14), grid: false });
      });
      return { pos: pos, ticks: ticks };
    }
    var a = col.lo, b = col.hi;
    if (col.empty) { a = 0; b = 1; }
    if (a === b) { var w = col.kind === 'datetime' ? 864e5 : Math.abs(a) || 1; a -= w; b += w; }
    var padding = (b - a) * 0.03;
    a -= padding; b += padding;
    var full = b - a;
    a += full * w0;
    b = a + full * (w1 - w0);
    var scale = (hi - lo) / (b - a);
    for (i = 0; i < n; i++) {
      var v = col.values[i];
      pos[i] = v === null ? NaN : lo + (v - a) * scale;
    }
    var most = Math.max(2, Math.min(7, Math.floor(Math.abs(hi - lo) / 60)));  // ticks the room holds
    var marks = col.kind === 'datetime' ? timeTicks(a, b, most) : niceTicks(a, b, most - 1).map(function (v) {
      return { at: v, label: fmtTick(v) };
    });
    marks.forEach(function (m) { ticks.push({ at: lo + (m.at - a) * scale, label: m.label, grid: true }); });
    return { pos: pos, ticks: ticks };
  }

  // ── colour of each dot, and the legend ──────────────────────────────────────

  // {of(i) -> colour, kind, items (categories: level code, label, colour, count) or ramp + range}
  function colouring(data, name, look) {
    var col = name ? data.cols[name] : null, scale = data.scale;
    if (!col) return { kind: 'none', of: function () { return look.palette[0]; } };
    if (col.kind === 'categorical') {
      var named = scale && scale.categories ? scale.categories : {};
      var order = col.levels.map(function (_, k) { return k; });
      order.sort(function (a, b) { return col.counts[b] - col.counts[a] || natural(col.levels[a], col.levels[b]); });
      var colours = [], next = 0;
      order.forEach(function (k) {
        var label = col.levels[k];
        colours[k] = Object.prototype.hasOwnProperty.call(named, label) ? named[label]
          : look.palette[next++ % look.palette.length];
      });
      var items = order.map(function (k) {
        return { code: k, label: col.levels[k], colour: colours[k], count: col.counts[k] };
      });
      if (col.blanks) items.push({ code: -1, label: BLANK, colour: MISSING, count: col.blanks });
      return {
        kind: 'categorical', items: items,
        of: function (i) { var k = col.codes[i]; return k < 0 ? MISSING : colours[k]; },
        code: function (i) { return col.codes[i]; }
      };
    }
    var ramp = look.ramp, lo = col.lo, hi = col.hi, center = null, steps = null;
    if (scale && scale.ramp) {
      ramp = scale.ramp;
      steps = scale.steps || null;
      center = scale.center === undefined ? null : scale.center;
      if (scale.domain) { lo = scale.domain[0]; hi = scale.domain[1]; }
      else if (center !== null) {
        var reach = Math.max(Math.abs(lo - center), Math.abs(hi - center)) || 1;
        lo = center - reach; hi = center + reach;
      }
    }
    // Where v falls from 0 to 1, as Scale.position does (the centre, if any, at 0.5).
    function where(v) {
      v = Math.min(hi, Math.max(lo, v));
      var w;
      if (center === null) w = hi === lo ? 1 : (v - lo) / (hi - lo);
      else if (v <= center) w = center > lo ? 0.5 * (v - lo) / (center - lo) : 0.5;
      else w = hi > center ? 0.5 + 0.5 * (v - center) / (hi - center) : 0.5;
      return w;
    }
    return {
      kind: 'ramp', ramp: ramp, lo: lo, hi: hi, date: col.kind === 'datetime',
      of: function (i) {
        var v = col.values[i];
        if (v === null) return MISSING;
        var w = where(v);
        return ramp[steps ? Math.min(steps - 1, Math.floor(w * steps)) : Math.round(w * (ramp.length - 1))];
      }
    };
  }

  // ── one DataDive ────────────────────────────────────────────────────────────

  // Esc closes the cards of the DataDive the reader last clicked in: one listener for the page.
  var escape = null;
  function onEscape(fn) { escape = fn; }

  function setupDive(container, runtime, root) {
    if (container.briefingDive) return;
    var data = load(container), n = data.n;
    var area = container.querySelector('.bf-dd__plot-area');
    var canvas = container.querySelector('.bf-dd__canvas');
    var svg = container.querySelector('.bf-dd__axes');
    var tip = container.querySelector('.bf-dd__tooltip');
    var legend = container.querySelector('.bf-dd__legend');
    var footer = container.querySelector('.bf-dd__footer');
    var layout = container.getAttribute('data-layout') || 'scatter';
    var selects = {};
    container.querySelectorAll('.bf-dd__sel').forEach(function (sel) { selects[sel.getAttribute('data-axis')] = sel; });
    function chosen(axisName) { return selects[axisName] ? selects[axisName].value : ''; }

    var look = theme(container);
    var titleName = container.getAttribute('data-title') || '';
    var cardsEl = container.querySelector('.bf-dd__cards');
    var cards = [];  // the open cards, in order: {row, pinned}
    var filters = [], query = '', mode = 'highlight', narrowing = false, match = new Uint8Array(n), lastLit = n;
    var selections = {};  // what other blocks selected here (#21), by the id of the block that sent it
    var view = { x0: 0, x1: 1, y0: 0, y1: 1 }, geo = null, dpr = 1, drawnH = 400, painted = { groups: {}, order: [] };
    function zoomed() { return 1 / Math.max(view.x1 - view.x0, view.y1 - view.y0); }
    var colour = null, hidden = {}, drawnWidth = 0, drawnW = 620;
    var xs = new Float32Array(n), ys = new Float32Array(n), shown = new Uint8Array(n), count = 0;
    var grid = null, cell = 12, radius = 3, hover = null;

    // Shown: not hidden by the legend and, in Filter mode, matching the search and filters.
    // In Highlight mode a dot that doesn't match stays, dimmed.
    function visible(i) {
      if (colour.kind === 'categorical' && hidden[colour.code(i)]) return false;
      return mode === 'highlight' || !narrowing || match[i] === 1;
    }

    // ── legend
    function drawLegend() {
      legend.innerHTML = '';
      var name = chosen('color');
      if (colour.kind === 'none') { legend.hidden = true; return; }
      legend.hidden = false;
      var title = document.createElement('span');
      title.className = 'bf-dd__legend-title';
      title.textContent = name;
      legend.appendChild(title);
      if (colour.kind === 'ramp') {
        var bar = document.createElement('span');
        bar.className = 'bf-dd__ramp';
        var stops = [];
        for (var s = 0; s < 9; s++) stops.push(colour.ramp[Math.round(s / 8 * (colour.ramp.length - 1))]);
        bar.style.background = 'linear-gradient(to right, ' + stops.join(', ') + ')';
        var low = document.createElement('span'), high = document.createElement('span');
        low.textContent = colour.date ? fmtDate(colour.lo, false) : fmtTick(colour.lo);
        high.textContent = colour.date ? fmtDate(colour.hi, false) : fmtTick(colour.hi);
        low.className = high.className = 'bf-dd__ramp-end';
        legend.appendChild(low); legend.appendChild(bar); legend.appendChild(high);
        return;
      }
      colour.items.slice(0, LEGEND_MAX).forEach(function (item) {
        var key = document.createElement('button');
        key.type = 'button';
        key.className = 'bf-dd__key';
        key.setAttribute('aria-pressed', hidden[item.code] ? 'false' : 'true');
        key.title = 'Click to hide or show; Alt+click to show only this one';
        var swatch = document.createElement('span');
        swatch.className = 'bf-dd__swatch';
        swatch.style.background = item.colour;
        var label = document.createElement('span');
        label.textContent = cut(item.label, 28);
        var tally = document.createElement('span');
        tally.className = 'bf-dd__key-count';
        tally.textContent = fmtNum(item.count);
        key.appendChild(swatch); key.appendChild(label); key.appendChild(tally);
        key.addEventListener('click', function (e) {
          if (e.altKey) {
            var alone = colour.items.every(function (o) { return o.code === item.code ? !hidden[o.code] : hidden[o.code]; });
            colour.items.forEach(function (o) { hidden[o.code] = alone ? false : o.code !== item.code; });
          } else {
            hidden[item.code] = !hidden[item.code];
          }
          drawLegend();
          draw();
        });
        legend.appendChild(key);
      });
      if (colour.items.length > LEGEND_MAX) {
        var more = document.createElement('span');
        more.className = 'bf-dd__key-more';
        more.textContent = '+' + fmtNum(colour.items.length - LEGEND_MAX) + ' more';
        legend.appendChild(more);
      }
    }

    // ── placing the dots

    // How many groups a column makes when it splits the dots: buckets= for it, else everyone's.
    var bucketsBy = JSON.parse(container.getAttribute('data-buckets') || '{}');
    function bucketsFor(name) {
      return Object.prototype.hasOwnProperty.call(bucketsBy, name) ? bucketsBy[name] : (bucketsBy[''] || 5);
    }

    // The groups a column splits the dots into (a facet, or a tile axis). {labels, of(i) -> index}
    // A category keeps its most frequent values plus "other"; a number or date is cut into bins,
    // a number's with round edges.
    function groups(name) {
      var col = name ? data.cols[name] : null;
      if (!col) return null;
      var most = bucketsFor(name), labels = [], slot = {};
      if (col.kind === 'categorical') {
        var byCount = col.levels.map(function (_, k) { return k; });
        byCount.sort(function (a, b) { return col.counts[b] - col.counts[a] || natural(col.levels[a], col.levels[b]); });
        var kept = byCount.length > most ? byCount.slice(0, most) : byCount;
        kept.sort(function (a, b) { return natural(col.levels[a], col.levels[b]); });
        kept.forEach(function (k, j) { slot[k] = j; labels.push(col.levels[k]); });
        var other = byCount.length > most ? labels.push('other') - 1 : -1;
        var blank = col.blanks ? labels.push(BLANK) - 1 : -1;
        return {
          labels: labels,
          of: function (i) { var k = col.codes[i]; return k < 0 ? blank : (k in slot ? slot[k] : other); }
        };
      }
      if (col.empty) return { labels: [BLANK], of: function () { return 0; } };
      var a = col.lo, b = col.hi, step, bins, date = col.kind === 'datetime';
      if (a === b) { step = 1; bins = 1; }
      else if (date) { step = (b - a) / most; bins = most; }
      else {
        step = niceStep((b - a) / most);
        a = Math.floor(a / step) * step;
        bins = Math.max(1, Math.ceil((b - a) / step - 1e-9));
      }
      var show = date ? function (v) { return fmtDate(v, false); } : function (v) { return fmtTick(+v.toPrecision(10)); };
      for (var k = 0; k < bins; k++) labels.push(bins === 1 ? show(a) : show(a + k * step) + '–' + show(a + (k + 1) * step));
      var blanks = col.values.some(function (v) { return v === null; }) ? labels.push(BLANK) - 1 : -1;
      return {
        labels: labels,
        of: function (i) {
          var v = col.values[i];
          return v === null ? blanks : Math.max(0, Math.min(bins - 1, Math.floor((v - a) / step)));
        }
      };
    }

    // The panels the facets make: rows × columns, and which panel each row of data falls in.
    function facets() {
      var rows = groups(chosen('frow')), cols = groups(chosen('fcol'));
      return {
        rows: rows, cols: cols,
        nr: rows ? rows.labels.length : 1, nc: cols ? cols.labels.length : 1,
        r: function (i) { return rows ? rows.of(i) : 0; },
        c: function (i) { return cols ? cols.of(i) : 0; }
      };
    }

    // The facet headers: a column's labels above the panels, a row's to their right.
    function facetHeads(f, parts, left, top, pw, ph, gap, right) {
      if (f.cols) {
        f.cols.labels.forEach(function (label, j) {
          parts.push('<text class="bf-dd__head" x="' + (left + j * (pw + gap) + pw / 2).toFixed(1) + '" y="' + (top - 7) +
            '" text-anchor="middle">' + esc(cut(label, Math.max(4, Math.floor(pw / 7)))) + '</text>');
        });
        parts.push('<text class="bf-dd__title" x="' + (left + (f.nc * (pw + gap) - gap) / 2).toFixed(1) + '" y="' + (top - 24) +
          '" text-anchor="middle">' + esc(chosen('fcol')) + '</text>');
      }
      if (f.rows) {
        f.rows.labels.forEach(function (label, j) {
          var x = right + 13, y = top + j * (ph + gap) + ph / 2;
          parts.push('<text class="bf-dd__head" transform="rotate(90 ' + x + ' ' + y.toFixed(1) + ')" x="' + x + '" y="' +
            y.toFixed(1) + '" text-anchor="middle">' + esc(cut(label, Math.max(4, Math.floor(ph / 7)))) + '</text>');
        });
        var mid = top + (f.nr * (ph + gap) - gap) / 2, tx = right + 30;
        parts.push('<text class="bf-dd__title" transform="rotate(90 ' + tx + ' ' + mid.toFixed(1) + ')" x="' + tx + '" y="' +
          mid.toFixed(1) + '" text-anchor="middle">' + esc(chosen('frow')) + '</text>');
      }
    }

    // Two axes, in each panel, on scales shared by every panel. -> {H, parts}
    function placeScatter(W) {
      var f = facets(), GAP = 12, yCat = data.cols[chosen('y')];
      // Room on the left for the Y labels: a category's names, cut at 14 characters, can be long.
      var longest = yCat && yCat.kind === 'categorical' ? yCat.levels.reduce(function (m, l) { return Math.max(m, Math.min(14, l.length)); }, 0) : 0;
      var ML = Math.max(58, Math.min(120, Math.round(longest * 6.2 + 24))), MR = 16 + (f.rows ? 38 : 0), MT = 12 + (f.cols ? 34 : 0), MB = 46;
      var pw = (W - ML - MR - (f.nc - 1) * GAP) / f.nc;
      var ph = f.nr * f.nc === 1 ? Math.round(Math.max(240, Math.min(640, W * 0.62))) - MT - MB
        : Math.round(Math.max(110, Math.min(420, pw * 0.72)));
      var H = MT + f.nr * ph + (f.nr - 1) * GAP + MB;
      var xCol = data.cols[chosen('x')], yCol = data.cols[chosen('y')];
      var parts = [];
      if (!xCol || !yCol) { for (var m = 0; m < n; m++) xs[m] = ys[m] = NaN; return { H: H, parts: parts }; }
      var ax = axis(xCol, n, 0, pw, 0, view.x0, view.x1), ay = axis(yCol, n, ph, 0, 1, view.y0, view.y1);
      for (var i = 0; i < n; i++) {
        var r = f.r(i), c = f.c(i), lx = ax.pos[i], ly = ay.pos[i];
        var out = r < 0 || c < 0 || lx < -1 || lx > pw + 1 || ly < -1 || ly > ph + 1;  // zoomed out of its panel
        xs[i] = out ? NaN : ML + c * (pw + GAP) + lx;
        ys[i] = out ? NaN : MT + r * (ph + GAP) + ly;
      }
      geo = { left: ML, top: MT, pw: pw, ph: ph, gap: GAP, nr: f.nr, nc: f.nc };
      for (var pr = 0; pr < f.nr; pr++) {
        for (var pc = 0; pc < f.nc; pc++) {
          var x0 = ML + pc * (pw + GAP), y0 = MT + pr * (ph + GAP), x1 = x0 + pw, y1 = y0 + ph;
          ax.ticks.forEach(function (t) {
            var x = (x0 + t.at).toFixed(1);
            if (t.grid) parts.push('<line class="bf-dd__grid" x1="' + x + '" y1="' + y0 + '" x2="' + x + '" y2="' + y1 + '"/>');
            // Between panels, a label at the edge would run into the next panel's first one.
            var edge = f.nc > 1 && (t.at < 18 || t.at > pw - 18);
            if (pr === f.nr - 1 && !edge) parts.push('<text class="bf-dd__tick" x="' + x + '" y="' + (y1 + 16) + '" text-anchor="middle">' + esc(t.label) + '</text>');
          });
          ay.ticks.forEach(function (t) {
            var y = (y0 + t.at).toFixed(1);
            if (t.grid) parts.push('<line class="bf-dd__grid" x1="' + x0 + '" y1="' + y + '" x2="' + x1 + '" y2="' + y + '"/>');
            if (pc === 0) parts.push('<text class="bf-dd__tick" x="' + (x0 - 6) + '" y="' + y + '" text-anchor="end" dominant-baseline="middle">' + esc(t.label) + '</text>');
          });
          parts.push('<line class="bf-dd__axis" x1="' + x0 + '" y1="' + y1 + '" x2="' + x1 + '" y2="' + y1 + '"/>');
          parts.push('<line class="bf-dd__axis" x1="' + x0 + '" y1="' + y0 + '" x2="' + x0 + '" y2="' + y1 + '"/>');
        }
      }
      facetHeads(f, parts, ML, MT, pw, ph, GAP, W - MR);
      parts.push('<text class="bf-dd__title" x="' + ((ML + W - MR) / 2) + '" y="' + (H - 8) + '" text-anchor="middle">' + esc(chosen('x')) + '</text>');
      parts.push('<text class="bf-dd__title" transform="rotate(-90)" x="' + (-(MT + H - MB) / 2) + '" y="14" text-anchor="middle">' + esc(chosen('y')) + '</text>');
      radius = (count > 20000 ? 1.4 : count > 5000 ? 2 : count > 1000 ? 2.8 : 3.6) * (f.nr * f.nc > 1 ? 0.8 : 1);
      if (zoomed() > 1) radius = Math.min(5, radius * Math.sqrt(zoomed()));  // bigger dots as they spread out
      return { H: H, parts: parts };
    }

    // Zoomed in far enough, dots are labelled by title=: only the ones in view, a few hundred at most.
    function labels() {
      if (!titleName || layout === 'tile' || zoomed() < 3) return '';
      var out = [], dim = narrowing && mode === 'highlight';
      for (var i = 0; i < n && out.length < 250; i++) {
        if (!shown[i] || xs[i] !== xs[i] || (dim && !match[i])) continue;
        var right = geo && xs[i] > geo.left + geo.nc * (geo.pw + geo.gap) - geo.gap - 130;  // near the edge: label on the left
        out.push('<text class="bf-dd__label" x="' + (right ? xs[i] - radius - 3 : xs[i] + radius + 3).toFixed(1) + '" y="' +
          (ys[i] + 3.5).toFixed(1) + '"' + (right ? ' text-anchor="end"' : '') + '>' + esc(cut(label(i), 24)) + '</text>');
      }
      return out.join('');
    }

    // Dots packed into cells, in each panel; every cell of every panel uses one dot size. -> {H, parts}
    function placeTile(W) {
      var f = facets(), GAP = 12, PAD = 5;
      var yName = chosen('y'), tx = groups(chosen('x')), ty = groups(yName) || { labels: [''], of: function () { return 0; } };
      var LX = yName ? 96 : 12, MR = 8 + (f.rows ? 38 : 0), LY = 42 + (f.cols ? 34 : 0);
      var pw = (W - LX - MR - (f.nc - 1) * GAP) / f.nc;
      var ph = f.nr * f.nc === 1 ? Math.round(Math.max(240, Math.min(640, W * 0.6))) - LY
        : Math.round(Math.max(120, Math.min(480, pw * 0.75)));
      var H = LY + f.nr * ph + (f.nr - 1) * GAP + 4;
      var parts = [], i;
      for (i = 0; i < n; i++) xs[i] = ys[i] = NaN;
      if (!tx) return { H: H, parts: parts };
      var cw = pw / tx.labels.length, ch = ph / ty.labels.length;
      var cells = {}, most = 1;
      for (i = 0; i < n; i++) {
        if (!shown[i]) continue;
        var r = f.r(i), c = f.c(i), cx = tx.of(i), cy = ty.of(i);
        if (r < 0 || c < 0 || cx < 0 || cy < 0) continue;
        var key = r + ',' + c + ',' + cx + ',' + cy;
        (cells[key] || (cells[key] = [])).push(i);
      }
      Object.keys(cells).forEach(function (k) { most = Math.max(most, cells[k].length); });
      // The biggest step at which the fullest cell's rows still fit: dots stay small (11 px at
      // most); with thumbnails, cells with room show the pictures, up to 56 px.
      var wide = cw - 2 * PAD, tall = ch - 2 * PAD, step = data.thumbs ? 56 : 11;
      while (step > 1.5 && Math.ceil(most / Math.max(1, Math.floor(wide / step))) * step > tall) step -= step > 8 ? 1 : 0.25;
      step = Math.max(1.5, step);
      tileStep = step;
      radius = Math.max(0.6, Math.min(5, step * 0.42));
      var per = Math.max(1, Math.floor((cw - 2 * PAD) / step));
      var rank = colour.kind === 'categorical' ? function (q) { var k = colour.code(q); return k < 0 ? 1e9 : k; } : function () { return 0; };
      Object.keys(cells).forEach(function (key) {
        var at = key.split(',').map(Number);
        var left = LX + at[1] * (pw + GAP) + at[2] * cw + PAD, top = LY + at[0] * (ph + GAP) + at[3] * ch + PAD;
        var list = cells[key].slice().sort(function (p, q) { return rank(p) - rank(q) || p - q; });
        list.forEach(function (q, d) {
          var y = top + Math.floor(d / per) * step + step / 2;
          if (y + step / 2 > top - PAD + ch) return;  // more than the cell holds, even at the smallest step
          xs[q] = left + (d % per) * step + step / 2;
          ys[q] = y;
        });
      });
      for (var pr = 0; pr < f.nr; pr++) {
        for (var pc = 0; pc < f.nc; pc++) {
          var x0 = LX + pc * (pw + GAP), y0 = LY + pr * (ph + GAP);
          tx.labels.forEach(function (label, j) {
            var cx0 = x0 + j * cw;
            if (j) parts.push('<line class="bf-dd__grid" x1="' + cx0.toFixed(1) + '" y1="' + y0 + '" x2="' + cx0.toFixed(1) + '" y2="' + (y0 + ph) + '"/>');
            if (pr === 0) parts.push('<text class="bf-dd__tick" x="' + (cx0 + cw / 2).toFixed(1) + '" y="' + (y0 - 6) + '" text-anchor="middle">' + esc(cut(label, Math.max(4, Math.floor(cw / 6)))) + '</text>');
          });
          ty.labels.forEach(function (label, j) {
            var cy0 = y0 + j * ch;
            if (j) parts.push('<line class="bf-dd__grid" x1="' + x0 + '" y1="' + cy0.toFixed(1) + '" x2="' + (x0 + pw).toFixed(1) + '" y2="' + cy0.toFixed(1) + '"/>');
            if (yName && pc === 0) parts.push('<text class="bf-dd__tick" x="' + (x0 - 8) + '" y="' + (cy0 + ch / 2).toFixed(1) + '" text-anchor="end" dominant-baseline="middle">' + esc(cut(label, 13)) + '</text>');
          });
          parts.push('<rect class="bf-dd__frame" x="' + x0 + '" y="' + y0 + '" width="' + pw.toFixed(1) + '" height="' + ph + '"/>');
        }
      }
      facetHeads(f, parts, LX, f.cols ? LY - 18 : LY, pw, ph, GAP, W - MR);
      parts.push('<text class="bf-dd__title" x="' + (LX + (W - LX - MR) / 2) + '" y="11" text-anchor="middle">' + esc(chosen('x')) + '</text>');
      if (yName) parts.push('<text class="bf-dd__title" transform="rotate(-90)" x="' + (-(LY + H) / 2) + '" y="12" text-anchor="middle">' + esc(yName) + '</text>');
      return { H: H, parts: parts };
    }

    // ── drawing
    // Paint the dots of `groups` (colour -> rows, in `order`) at px, py.
    function paint(px, py) {
      var ctx = canvas.getContext('2d'), W = drawnW, H = drawnH;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      var alpha = layout === 'tile' ? 0.85 : count > 20000 ? 0.55 : 0.72, square = radius < 1.8;
      if (pictured()) { paintPictures(ctx, px, py); return; }
      painted.order.forEach(function (c) {
        ctx.fillStyle = c === DIM ? look.dim : c;
        ctx.globalAlpha = c === DIM ? 0.28 : alpha;
        var list = painted.groups[c];
        if (square) {
          for (var j = 0; j < list.length; j++) {
            var q = list[j];
            if (px[q] === px[q]) ctx.fillRect(px[q] - radius, py[q] - radius, radius * 2, radius * 2);
          }
          return;
        }
        ctx.beginPath();
        for (var k = 0; k < list.length; k++) {
          var p = list[k];
          if (px[p] !== px[p]) continue;
          ctx.moveTo(px[p] + radius, py[p]);
          ctx.arc(px[p], py[p], radius, 0, 2 * Math.PI);
        }
        ctx.fill();
      });
      ctx.globalAlpha = 1;
    }

    // ── thumbnails (#16): in tiles with room, each dot shows its picture, framed in its colour
    var pictures = [], tileStep = 0;
    function pictured() { return !!data.thumbs && layout === 'tile' && tileStep >= 16; }
    function picture(k) {  // made when first needed; the page repaints once it has loaded
      if (!pictures[k]) {
        var img = new Image();
        img.onload = function () { if (pictured()) paint(xs, ys); };
        img.src = data.thumbs.images[k];
        pictures[k] = img;
      }
      return pictures[k];
    }
    function paintPictures(ctx, px, py) {
      var size = tileStep - 3, half = size / 2;
      painted.order.forEach(function (c) {
        var list = painted.groups[c];
        for (var j = 0; j < list.length; j++) {
          var q = list[j];
          if (px[q] !== px[q]) continue;
          var k = data.thumbs.codes[q], img = k >= 0 ? picture(k) : null;
          ctx.globalAlpha = c === DIM ? 0.25 : 1;
          ctx.fillStyle = c === DIM ? look.dim : c;
          ctx.fillRect(px[q] - half - 1, py[q] - half - 1, size + 2, size + 2);  // its colour, as a frame
          if (img && img.complete && img.naturalWidth) {
            var fit = Math.min(size / img.naturalWidth, size / img.naturalHeight);
            var w = img.naturalWidth * fit, h = img.naturalHeight * fit;
            ctx.fillStyle = look.bg;
            ctx.fillRect(px[q] - half, py[q] - half, size, size);
            ctx.drawImage(img, px[q] - w / 2, py[q] - h / 2, w, h);
          }
        }
      });
      ctx.globalAlpha = 1;
    }

    var REDUCED = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var frame = 0, moving = false;
    // Move the dots from where they were (fromX, fromY) to where they are now, in about 300 ms.
    function glide(fromX, fromY) {
      var start = null, px = new Float32Array(n), py = new Float32Array(n), mine = ++frame;
      moving = true;
      function step(now) {
        if (mine !== frame) return;  // a newer draw took over
        if (start === null) start = now;
        var t = Math.min(1, (now - start) / 300), e = 1 - Math.pow(1 - t, 3);
        for (var i = 0; i < n; i++) {
          var a = fromX[i], b = fromY[i];
          if (a !== a || b !== b) { px[i] = xs[i]; py[i] = ys[i]; continue; }  // new in view: in place
          px[i] = a + (xs[i] - a) * e;
          py[i] = b + (ys[i] - b) * e;
        }
        paint(px, py);
        if (t < 1) window.requestAnimationFrame(step); else moving = false;
      }
      window.requestAnimationFrame(step);
    }

    function draw(animate) {
      // Motion only where it stays smooth: up to MOTION_MAX dots, and never when the reader asks for less.
      var fromX = animate && !REDUCED && !printing && count <= MOTION_MAX ? xs.slice() : null, fromY = fromX ? ys.slice() : null;
      frame++;
      moving = false;
      var W = Math.max(280, Math.round(area.clientWidth || 620));
      drawnWidth = area.clientWidth;
      drawnW = W;
      count = 0;
      for (var i = 0; i < n; i++) { shown[i] = visible(i) ? 1 : 0; count += shown[i]; }
      var placed = layout === 'tile' ? placeTile(W) : placeScatter(W), H = placed.H, parts = placed.parts;
      if (layout === 'tile') geo = null;
      dpr = Math.min(3, window.devicePixelRatio || 1);
      drawnH = H;
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

      var groups = {}, order = [], dimmed = [], lit = 0, dim = narrowing && mode === 'highlight';
      grid = {};
      cell = Math.max(8, radius * 3, pictured() ? tileStep : 0);
      for (i = 0; i < n; i++) {
        if (!shown[i] || xs[i] !== xs[i] || ys[i] !== ys[i]) continue;
        if (dim && !match[i]) { dimmed.push(i); } else {
          var c = colour.of(i);
          if (!groups[c]) { groups[c] = []; order.push(c); }
          groups[c].push(i);
          lit++;
        }
        var key = Math.floor(xs[i] / cell) + ',' + Math.floor(ys[i] / cell);
        (grid[key] || (grid[key] = [])).push(i);
      }
      if (dimmed.length) { groups[DIM] = dimmed; order.unshift(DIM); }  // under the matches
      painted = { groups: groups, order: order };
      if (fromX) glide(fromX, fromY); else paint(xs, ys);

      parts.push(labels());
      parts.push('<g class="bf-dd__rings"></g>');
      parts.push('<circle class="bf-dd__hover" r="' + (radius + 2.5) + '" cx="-99" cy="-99"/>');
      svg.innerHTML = parts.join('');
      hover = svg.querySelector('.bf-dd__hover');
      drawRings();
      footer.textContent = dim ? fmtNum(lit) + ' of ' + fmtNum(n) + ' match'
        : count === n ? fmtNum(n) + ' rows' : fmtNum(count) + ' of ' + fmtNum(n) + ' shown';
      lastLit = dim ? lit : count;
      var described = layout === 'tile' ? 'DataDive tiles by ' + chosen('x') + (chosen('y') ? ' and ' + chosen('y') : '')
        : 'DataDive scatter plot of ' + chosen('y') + ' against ' + chosen('x');
      canvas.setAttribute('aria-label', described + (chosen('color') ? ', coloured by ' + chosen('color') : '') +
        ': ' + fmtNum(count) + ' of ' + fmtNum(n) + ' dots');
      tip.hidden = true;
      if (printing) vector(true);  // printing narrows the page: a redraw keeps the printed circles
    }

    // ── hover
    function nearest(x, y) {
      var reach = pictured() ? tileStep / 2 : radius + 4;
      var gx = Math.floor(x / cell), gy = Math.floor(y / cell), best = -1, bestD = reach * reach;
      for (var dx = -1; dx <= 1; dx++) {
        for (var dy = -1; dy <= 1; dy++) {
          var list = grid[(gx + dx) + ',' + (gy + dy)];
          if (!list) continue;
          for (var k = 0; k < list.length; k++) {
            var p = list[k], d = (xs[p] - x) * (xs[p] - x) + (ys[p] - y) * (ys[p] - y);
            if (d <= bestD) { bestD = d; best = p; }
          }
        }
      }
      return best;
    }

    function thumbFor(i, cls) {
      var k = data.thumbs ? data.thumbs.codes[i] : -1;
      if (k < 0) return null;
      var img = el('img', cls);
      img.src = data.thumbs.images[k];
      img.alt = '';
      return img;
    }

    function showTip(i, e) {
      tip.innerHTML = '';
      var tipPicture = thumbFor(i, 'bf-dd__tip-thumb');
      if (tipPicture) tip.appendChild(tipPicture);
      if (titleName) {
        var heading = document.createElement('div');
        heading.className = 'bf-dd__tip-title';
        heading.textContent = cut(label(i), 60);
        tip.appendChild(heading);
      }
      data.names.filter(function (name) { return name !== titleName; }).slice(0, titleName ? 9 : 10).forEach(function (name) {
        var line = document.createElement('div'), b = document.createElement('b'), v = display(data.cols[name], i);
        b.textContent = cut(name, 24) + ': ';
        line.appendChild(b);
        line.appendChild(document.createTextNode(v === null ? '—' : cut(v, 60)));
        tip.appendChild(line);
      });
      tip.hidden = false;
      var rect = area.getBoundingClientRect();
      var px = e.clientX - rect.left + 12, py = e.clientY - rect.top - 8;
      if (px + tip.offsetWidth > rect.width) px = e.clientX - rect.left - tip.offsetWidth - 12;
      if (py + tip.offsetHeight > rect.height) py = Math.max(0, rect.height - tip.offsetHeight);
      tip.style.left = px + 'px';
      tip.style.top = py + 'px';
    }

    // ── the record cards: a click opens a row's card, Pin keeps it (two at most), Esc or × closes
    function label(i) {
      var v = titleName ? display(data.cols[titleName], i) : null;
      return v === null ? 'Row ' + fmtNum(i + 1) : v;
    }

    function valueNode(name, i) {
      var v = display(data.cols[name], i), dd = document.createElement('dd');
      if (v === null) { dd.textContent = '—'; dd.className = 'bf-dd__missing'; return dd; }
      if (/^https?:\/\/\S+$/i.test(v)) {  // a web address becomes a link, made only now the card is open
        var a = document.createElement('a');
        a.href = v;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.textContent = v;
        dd.appendChild(a);
      } else {
        dd.textContent = v;
      }
      return dd;
    }

    function cardFor(entry) {
      var i = entry.row, card = document.createElement('section');
      card.className = 'bf-dd__card' + (entry.pinned ? ' bf-dd__card--pinned' : '');
      card.setAttribute('aria-label', label(i));
      var head = document.createElement('div'), title = document.createElement('span');
      head.className = 'bf-dd__card-head';
      title.className = 'bf-dd__card-title';
      title.textContent = label(i);
      var pin = document.createElement('button'), close = document.createElement('button');
      pin.type = close.type = 'button';
      pin.className = 'bf-dd__card-pin';
      pin.textContent = entry.pinned ? 'Unpin' : 'Pin';
      pin.setAttribute('aria-pressed', entry.pinned ? 'true' : 'false');
      pin.title = entry.pinned ? 'Let the next dot you click replace this card' : 'Keep this card to compare it with another row';
      pin.addEventListener('click', function () { togglePin(entry); });
      close.className = 'bf-dd__card-close';
      close.textContent = '×';
      close.setAttribute('aria-label', 'Close the card of ' + label(i));
      close.addEventListener('click', function () { cards.splice(cards.indexOf(entry), 1); renderCards(); });
      head.appendChild(title); head.appendChild(pin); head.appendChild(close);
      var body = document.createElement('dl');
      body.className = 'bf-dd__card-body';
      data.names.forEach(function (name) {
        var dt = document.createElement('dt');
        dt.textContent = name;
        body.appendChild(dt);
        body.appendChild(valueNode(name, i));
      });
      card.appendChild(head);
      var cardPicture = thumbFor(i, 'bf-dd__card-thumb');
      if (cardPicture) card.appendChild(cardPicture);
      card.appendChild(body);
      return card;
    }

    function drawRings() {
      var g = svg.querySelector('.bf-dd__rings');
      if (!g) return;
      g.innerHTML = cards.filter(function (c) { return xs[c.row] === xs[c.row] && ys[c.row] === ys[c.row]; }).map(function (c) {
        return '<circle class="bf-dd__picked' + (c.pinned ? ' bf-dd__picked--pinned' : '') + '" r="' + (radius + 3.5).toFixed(1) +
          '" cx="' + xs[c.row].toFixed(1) + '" cy="' + ys[c.row].toFixed(1) + '"/>';
      }).join('');
    }

    function renderCards() {
      cardsEl.innerHTML = '';
      cards.forEach(function (entry) { cardsEl.appendChild(cardFor(entry)); });
      drawRings();
    }

    function open(i) {
      if (!cards.some(function (c) { return c.row === i; })) {
        cards = cards.filter(function (c) { return c.pinned; });  // the open, unpinned card gives way
        cards.push({ row: i, pinned: false });
      }
      renderCards();
    }

    function togglePin(entry) {
      if (!entry.pinned) {
        var pinned = cards.filter(function (c) { return c.pinned; });
        if (pinned.length >= 2) cards.splice(cards.indexOf(pinned[0]), 1);  // two at most: the oldest goes
      }
      entry.pinned = !entry.pinned;
      renderCards();
    }

    function closeAll() { cards = []; renderCards(); }

    function pick(e) {
      var rect = canvas.getBoundingClientRect(), unit = drawnW / rect.width;  // screen px -> drawing px
      return nearest((e.clientX - rect.left) * unit, (e.clientY - rect.top) * unit);
    }

    canvas.addEventListener('click', function (e) {
      if (dragged) { dragged = false; return; }  // the end of a pan, not a click on a dot
      var i = pick(e);
      if (i >= 0) { open(i); onEscape(closeAll); }
    });
    cardsEl.addEventListener('click', function () { onEscape(closeAll); });

    canvas.addEventListener('mousemove', function (e) {
      var i = pick(e);
      if (i < 0) { tip.hidden = true; hover.setAttribute('cx', '-99'); canvas.style.cursor = ''; return; }
      hover.setAttribute('cx', xs[i].toFixed(1));
      hover.setAttribute('cy', ys[i].toFixed(1));
      canvas.style.cursor = 'pointer';
      showTip(i, e);
    });
    canvas.addEventListener('mouseleave', function () { tip.hidden = true; hover.setAttribute('cx', '-99'); });

    // ── filters and search (#16): narrow or highlight the dots, without going back to Python
    function el(tag, cls, text) {
      var e = document.createElement(tag);
      if (cls) e.className = cls;
      if (text !== undefined) e.textContent = text;
      return e;
    }

    // For each text column, which of its values contain q; then whether row i has one.
    function textTest(q) {
      var hits = [];
      data.names.forEach(function (name) {
        var c = data.cols[name];
        if (c.kind !== 'categorical') return;
        var found = new Uint8Array(c.levels.length), any = false;
        for (var k = 0; k < c.levels.length; k++) if (c.levels[k].toLowerCase().indexOf(q) >= 0) { found[k] = 1; any = true; }
        if (any) hits.push({ codes: c.codes, found: found });
      });
      return function (i) {
        for (var j = 0; j < hits.length; j++) { var k = hits[j].codes[i]; if (k >= 0 && hits[j].found[k]) return true; }
        return false;
      };
    }

    function active(f) {
      return data.cols[f.name].kind === 'categorical' ? Object.keys(f.off).length > 0 : f.lo !== null || f.hi !== null;
    }

    function passes(f, i) {
      var c = data.cols[f.name];
      if (c.kind === 'categorical') return !f.off[c.codes[i] < 0 ? 'blank' : c.codes[i]];
      var v = c.values[i];
      return v !== null && (f.lo === null || v >= f.lo) && (f.hi === null || v <= f.hi);
    }

    function refilter() {
      var q = query.trim().toLowerCase(), test = q ? textTest(q) : null, on = filters.filter(active);
      var picked = Object.keys(selections).map(function (k) { return selections[k].test; });
      narrowing = !!q || on.length > 0 || picked.length > 0;
      for (var i = 0; i < n; i++) {
        var ok = !test || test(i);
        for (var f = 0; ok && f < on.length; f++) ok = passes(on[f], i);
        for (var p = 0; ok && p < picked.length; p++) ok = picked[p](i);
        match[i] = ok ? 1 : 0;
      }
      draw();
      showResults();
    }

    var bar = el('div', 'bf-dd__filters');
    var searchBox = el('div', 'bf-dd__search-box');
    var search = el('input', 'bf-dd__search');
    search.type = 'search';
    search.placeholder = 'Search';
    search.setAttribute('aria-label', 'Search the rows');
    var results = el('ul', 'bf-dd__results');
    results.hidden = true;
    results.setAttribute('aria-label', 'Rows that match');
    searchBox.appendChild(search);
    searchBox.appendChild(results);
    var add = el('select', 'bf-dd__sel bf-dd__add');
    add.setAttribute('aria-label', 'Add a filter on a column');
    add.appendChild(el('option', '', '+ Filter'));
    add.firstChild.value = '';
    data.names.forEach(function (name) { var o = el('option', '', name); o.value = name; add.appendChild(o); });
    var chips = el('div', 'bf-dd__chips');
    var modes = el('div', 'bf-dd__modes');
    modes.setAttribute('role', 'group');
    modes.setAttribute('aria-label', 'Rows that do not match');
    [['highlight', 'Highlight', 'Dim the rows that do not match'], ['filter', 'Filter', 'Hide the rows that do not match']].forEach(function (m) {
      var b = el('button', 'bf-dd__mode', m[1]);
      b.type = 'button';
      b.title = m[2];
      b.setAttribute('data-mode', m[0]);
      b.setAttribute('aria-pressed', m[0] === mode ? 'true' : 'false');
      b.addEventListener('click', function () {
        mode = m[0];
        modes.querySelectorAll('.bf-dd__mode').forEach(function (o) {
          o.setAttribute('aria-pressed', o.getAttribute('data-mode') === mode ? 'true' : 'false');
        });
        draw();
      });
      modes.appendChild(b);
    });
    bar.appendChild(searchBox); bar.appendChild(add); bar.appendChild(chips); bar.appendChild(modes);
    container.insertBefore(bar, area);

    // ── linked selection (#21, #238): a lab block's bar or cell selects rows here. Its tests
    // (one per pick) are compiled by select.js, which ships with every sender.
    function selectionTest(d) {
      var shared = window.briefingSelection;
      if (!shared || !d.any) return null;
      return shared.compile(d.any, function (name) { return data.cols.hasOwnProperty(name) ? data.cols[name] : null; });
    }

    function unselect(source, tell) {
      var sel = selections[source];
      if (!sel) return;
      delete selections[source];
      if (sel.chip.parentNode) sel.chip.parentNode.removeChild(sel.chip);
      if (tell) root.dispatchEvent(new CustomEvent('bf:unselect', { detail: { source: source } }));
      refilter();
    }

    root.addEventListener('bf:select', function (e) {
      var d = e.detail;
      if (!d || !d.targets || d.targets.indexOf(container.id) < 0) return;
      var old = selections[d.source], test = d.any && d.any.length ? selectionTest(d) : null;
      if (old && old.chip.parentNode) old.chip.parentNode.removeChild(old.chip);
      delete selections[d.source];
      if (test) {
        var chip = el('span', 'bf-dd__chip bf-dd__chip--select');
        chip.appendChild(el('span', 'bf-dd__chip-name', d.column));
        chip.appendChild(el('span', 'bf-dd__chip-picks', ' ' + d.labels.join(', ')));
        chip.appendChild(el('span', 'bf-dd__chip-from', ' \u00b7 from ' + d.from));
        var remove = el('button', 'bf-dd__chip-remove', '\u00d7');
        remove.type = 'button';
        remove.setAttribute('aria-label', 'Clear the selection from ' + d.from);
        remove.addEventListener('click', function () { unselect(d.source, true); });
        chip.appendChild(remove);
        chips.appendChild(chip);
        selections[d.source] = { test: test, chip: chip, column: d.column, labels: d.labels.slice() };
      }
      refilter();
    });

    // The rows that match the search, as buttons that open their cards.
    function showResults() {
      results.innerHTML = '';
      if (!query.trim()) { results.hidden = true; return; }
      var listed = 0;
      for (var i = 0; i < n && listed < 8; i++) {
        if (!match[i] || !shown[i]) continue;
        var item = el('li'), b = el('button', 'bf-dd__result', label(i));
        b.type = 'button';
        b.addEventListener('click', (function (row) { return function () { open(row); onEscape(closeAll); }; })(i));
        item.appendChild(b);
        results.appendChild(item);
        listed++;
      }
      if (!listed) results.appendChild(el('li', 'bf-dd__result-none', 'No row matches'));
      else if (lastLit > listed) results.appendChild(el('li', 'bf-dd__result-more', fmtNum(lastLit) + ' rows match'));
      results.hidden = false;
    }

    var typing = null;
    search.addEventListener('input', function () {
      clearTimeout(typing);
      typing = setTimeout(function () { query = search.value; refilter(); }, 120);
    });
    search.addEventListener('keydown', function (e) {
      if (e.key !== 'Enter') return;
      clearTimeout(typing);
      query = search.value;
      refilter();
      var first = results.querySelector('.bf-dd__result');
      if (first) first.click();
    });

    function chipFor(f) {
      var c = data.cols[f.name], wrap = el('span', 'bf-dd__chip');
      var remove = el('button', 'bf-dd__chip-remove', '×');
      remove.type = 'button';
      remove.setAttribute('aria-label', 'Remove the filter on ' + f.name);
      remove.addEventListener('click', function () { filters.splice(filters.indexOf(f), 1); wrap.parentNode.removeChild(wrap); refilter(); });
      if (c.kind === 'categorical') {
        var box = el('details', 'bf-dd__chip-pick'), summary = el('summary', '', f.name), body = el('div', 'bf-dd__chip-body');
        var tally = el('span', 'bf-dd__chip-count');
        summary.appendChild(tally);
        var order = c.levels.map(function (_, k) { return k; });
        order.sort(function (a, b) { return c.counts[b] - c.counts[a] || natural(c.levels[a], c.levels[b]); });
        var listed = order.slice(0, 100).map(function (k) { return { key: k, label: c.levels[k], count: c.counts[k] }; });
        if (c.blanks) listed.push({ key: 'blank', label: BLANK, count: c.blanks });
        var update = function () { tally.textContent = (listed.length - Object.keys(f.off).length) + ' of ' + listed.length; };
        listed.forEach(function (o) {
          var row = el('label', 'bf-dd__chip-option'), tick = el('input');
          tick.type = 'checkbox';
          tick.checked = true;
          tick.addEventListener('change', function () {
            if (tick.checked) delete f.off[o.key]; else f.off[o.key] = true;
            update();
            refilter();
          });
          row.appendChild(tick);
          row.appendChild(el('span', '', cut(o.label, 32)));
          row.appendChild(el('span', 'bf-dd__key-count', fmtNum(o.count)));
          body.appendChild(row);
        });
        if (order.length > 100) body.appendChild(el('span', 'bf-dd__key-more', '+' + fmtNum(order.length - 100) + ' more, always kept'));
        update();
        box.appendChild(summary);
        box.appendChild(body);
        wrap.appendChild(box);
      } else {
        var date = c.kind === 'datetime';
        wrap.appendChild(el('span', 'bf-dd__chip-name', f.name));
        ['lo', 'hi'].forEach(function (end, j) {
          var input = el('input', 'bf-dd__chip-range');
          input.type = date ? 'date' : 'number';
          if (!date) input.step = 'any';
          input.placeholder = date ? '' : fmtTick(j ? c.hi : c.lo);
          input.setAttribute('aria-label', f.name + (j ? ' at most' : ' at least'));
          input.addEventListener('change', function () {
            var v = input.value === '' ? null : date ? Date.parse(input.value + 'T00:00:00Z') + (j ? 864e5 - 1 : 0) : Number(input.value);
            f[end] = v === null || v !== v ? null : v;
            refilter();
          });
          if (j) wrap.appendChild(el('span', 'bf-dd__chip-dash', '–'));
          wrap.appendChild(input);
        });
      }
      wrap.appendChild(remove);
      return wrap;
    }

    container.addEventListener('click', function (e) {
      chips.querySelectorAll('details[open]').forEach(function (d) { if (!d.contains(e.target)) d.open = false; });
    });

    add.addEventListener('change', function () {
      var name = add.value;
      add.value = '';
      if (!name || filters.some(function (f) { return f.name === name; })) return;
      var f = { name: name, off: {}, lo: null, hi: null };
      filters.push(f);
      var chip = chipFor(f);
      chips.appendChild(chip);
      var picker = chip.querySelector('details');
      if (picker) picker.open = true;  // a category's values, listed at once to untick
      var first = chip.querySelector('summary, input');
      if (first) first.focus();
    });

    // ── controls
    function recolour() {
      colour = colouring(data, chosen('color'), look);
      hidden = {};
      drawLegend();
    }
    Object.keys(selects).forEach(function (name) {
      selects[name].addEventListener('change', function () {
        if (name === 'color') { recolour(); draw(); return; }
        view = { x0: 0, x1: 1, y0: 0, y1: 1 };  // new axes: start from the whole range
        draw(true);  // the dots move to their new places
        zoomState();
      });
    });

    // ── zoom and pan (the scatter layout): Ctrl or ⌘ + wheel (a trackpad's pinch), drag, double-click
    function clampView(v) {
      ['x', 'y'].forEach(function (a) {
        var w = Math.min(1, v[a + '1'] - v[a + '0']);
        var lo = Math.max(0, Math.min(1 - w, v[a + '0']));
        v[a + '0'] = lo; v[a + '1'] = lo + w;
      });
      return v;
    }

    // Zoom by `factor` (2: twice as close) around the point at fx, fy (fractions of a panel, y up).
    function zoomAt(factor, fx, fy) {
      var w = (view.x1 - view.x0) / factor, h = (view.y1 - view.y0) / factor;
      if (w < 0.002 || h < 0.002) return;  // as close as it goes
      var cx = view.x0 + fx * (view.x1 - view.x0), cy = view.y0 + fy * (view.y1 - view.y0);
      view = clampView({ x0: cx - fx * w, x1: cx - fx * w + w, y0: cy - fy * h, y1: cy - fy * h + h });
      draw();
      zoomState();
    }

    // Where a pointer is, as fractions of the panel under it (y up), or null outside the panels.
    function inPanel(e) {
      if (!geo) return null;
      var rect = canvas.getBoundingClientRect(), unit = drawnW / rect.width;
      var x = (e.clientX - rect.left) * unit - geo.left, y = (e.clientY - rect.top) * unit - geo.top;
      var c = Math.floor(x / (geo.pw + geo.gap)), r = Math.floor(y / (geo.ph + geo.gap));
      if (c < 0 || r < 0 || c >= geo.nc || r >= geo.nr) return null;
      return { fx: (x - c * (geo.pw + geo.gap)) / geo.pw, fy: 1 - (y - r * (geo.ph + geo.gap)) / geo.ph, unit: unit };
    }

    var hint = el('div', 'bf-dd__hint', (/Mac|iPhone|iPad/.test(navigator.platform || '') ? '⌘' : 'Ctrl') + ' + scroll to zoom');
    hint.hidden = true;
    area.appendChild(hint);
    var hintTimer = null;
    canvas.addEventListener('wheel', function (e) {
      if (layout === 'tile') return;
      if (!e.ctrlKey && !e.metaKey) {  // a plain wheel scrolls the page, as everywhere else
        hint.hidden = false;
        clearTimeout(hintTimer);
        hintTimer = setTimeout(function () { hint.hidden = true; }, 1200);
        return;
      }
      var at = inPanel(e);
      if (!at) return;
      e.preventDefault();
      zoomAt(Math.exp(-e.deltaY * 0.004), Math.max(0, Math.min(1, at.fx)), Math.max(0, Math.min(1, at.fy)));
    }, { passive: false });

    var drag = null, dragged = false;
    canvas.addEventListener('pointerdown', function (e) {
      dragged = false;
      if (layout === 'tile' || zoomed() <= 1 || e.button !== 0 || !geo) return;
      drag = { x: e.clientX, y: e.clientY, view: { x0: view.x0, x1: view.x1, y0: view.y0, y1: view.y1 } };
      if (canvas.setPointerCapture) canvas.setPointerCapture(e.pointerId);
    });
    canvas.addEventListener('pointermove', function (e) {
      if (!drag) return;
      var rect = canvas.getBoundingClientRect(), unit = drawnW / rect.width;
      var dx = (e.clientX - drag.x) * unit, dy = (e.clientY - drag.y) * unit;
      if (!dragged && Math.abs(dx) + Math.abs(dy) < 4) return;
      dragged = true;
      tip.hidden = true;
      var w = drag.view.x1 - drag.view.x0, h = drag.view.y1 - drag.view.y0;
      view = clampView({ x0: drag.view.x0 - dx / geo.pw * w, x1: drag.view.x1 - dx / geo.pw * w,
                         y0: drag.view.y0 + dy / geo.ph * h, y1: drag.view.y1 + dy / geo.ph * h });
      draw();
    });
    canvas.addEventListener('pointerup', function () { drag = null; });
    canvas.addEventListener('pointercancel', function () { drag = null; });
    canvas.addEventListener('dblclick', function () { resetZoom(); });
    canvas.style.touchAction = 'pan-y';

    function resetZoom() {
      if (zoomed() <= 1) return;
      view = { x0: 0, x1: 1, y0: 0, y1: 1 };
      draw();
      zoomState();
    }

    var zoomBar = el('div', 'bf-dd__zoom');
    zoomBar.setAttribute('role', 'group');
    zoomBar.setAttribute('aria-label', 'Zoom');
    [['+', 'Zoom in', function () { zoomAt(2, 0.5, 0.5); }], ['−', 'Zoom out', function () { zoomAt(0.5, 0.5, 0.5); }],
     ['Reset', 'Show all the data again', resetZoom]].forEach(function (z) {
      var b = el('button', 'bf-dd__zoom-btn', z[0]);
      b.type = 'button';
      b.setAttribute('aria-label', z[1]);
      b.title = z[1];
      b.addEventListener('click', z[2]);
      zoomBar.appendChild(b);
    });
    zoomBar.hidden = layout === 'tile';
    area.appendChild(zoomBar);
    // Zooming out and resetting only mean something once zoomed in.
    function zoomState() {
      var close = zoomed() > 1;
      zoomBar.querySelectorAll('.bf-dd__zoom-btn').forEach(function (b, k) { if (k) b.disabled = !close; });
    }
    zoomState();

    recolour();
    draw();
    // Redraw when the block's width changes: a window resize, or a tab or toggle that shows it.
    if (window.ResizeObserver) {
      new ResizeObserver(function () {
        if (Math.abs(area.clientWidth - drawnWidth) > 1) draw();
      }).observe(area);
    } else {
      runtime.on(window, 'resize', function () { if (Math.abs(area.clientWidth - drawnWidth) > 1) draw(); });
    }

    // Printing: the dots as SVG circles, so a PDF stays vector, when there aren't too many.
    var printing = false;
    function vector(on) {
      printing = on;
      var old = svg.querySelector('.bf-dd__print');
      if (old) old.parentNode.removeChild(old);
      canvas.style.visibility = '';
      if (!on || count > PRINT_VECTOR || pictured()) return;  // pictures print as the canvas
      var dots = [], alpha = layout === 'tile' ? 0.85 : 0.72;
      for (var i = 0; i < n; i++) {
        if (!shown[i] || xs[i] !== xs[i] || ys[i] !== ys[i]) continue;
        dots.push('<circle cx="' + xs[i].toFixed(1) + '" cy="' + ys[i].toFixed(1) + '" r="' + radius.toFixed(2) +
          '" fill="' + colour.of(i) + '"/>');
      }
      var group = svg.ownerDocument.createElementNS('http://www.w3.org/2000/svg', 'g');
      group.setAttribute('class', 'bf-dd__print');
      group.setAttribute('fill-opacity', String(alpha));
      group.innerHTML = dots.join('');
      svg.insertBefore(group, svg.firstChild);
      canvas.style.visibility = 'hidden';
    }

    // What tests and other scripts can read: how many dots are drawn, and where.
    container.briefingDive = {
      vector: vector,
      open: open,
      matches: function () { return narrowing ? lastLit : count; },
      selections: function () {
        return Object.keys(selections).map(function (k) {
          return { source: k, column: selections[k].column, labels: selections[k].labels };
        });
      },
      matched: function (i) { return !narrowing || match[i] === 1; },
      searched: function () { return query; },
      view: function () { return { x0: view.x0, x1: view.x1, y0: view.y0, y1: view.y1 }; },
      moving: function () { return moving; },
      pictured: pictured,
      cards: function () { return cards.map(function (c) { return { row: c.row, pinned: c.pinned }; }); },
      shown: function () { return count; },
      total: n,
      dot: function (i) { return { x: xs[i], y: ys[i], colour: colour.of(i), shown: !!shown[i] }; },
      radius: function () { return radius; },
      width: function () { return drawnW; }
    };
  }

  window.briefing.register('lab', function (runtime) {
    var dives = [];
    runtime.on(document, 'keydown', function (e) {
      if ((e.key === 'Escape' || e.key === 'Esc') && escape) { escape(); escape = null; }
    });
    runtime.onPrint(function () { dives.forEach(function (d) { d.briefingDive.vector(true); }); },
                    function () { dives.forEach(function (d) { d.briefingDive.vector(false); }); });
    return function (root) {
      root.querySelectorAll('.bf-datadive').forEach(function (el) {
        setupDive(el, runtime, root);
        if (el.briefingDive && dives.indexOf(el) < 0) dives.push(el);
      });
    };
  });
})();
