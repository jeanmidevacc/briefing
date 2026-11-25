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
  var LEGEND_MAX = 24;  // categories listed before "+N more"
  var PRINT_VECTOR = 5000;  // up to this many dots print as SVG circles (vector PDFs); more print as the canvas
  var TILE_BINS = 5;    // bins for a number on a tile axis

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
    return { palette: palette, ramp: ramp };
  }

  // ── text ────────────────────────────────────────────────────────────────────

  function esc(s) {
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
  }
  function cut(s, n) { return s.length > n ? s.slice(0, n - 1) + '…' : s; }
  function thousands(s) { return s.replace(/\B(?=(\d{3})+(?!\d))/g, ','); }
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
    return { n: payload.rows, cols: cols, names: names, scale: scaleEl ? JSON.parse(scaleEl.textContent) : null };
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

  // Ticks on round dates: years, months, days or hours, at most about seven.
  function timeTicks(a, b) {
    var HOUR = 36e5, DAY = 864e5, span = b - a, out = [], d = new Date(a), step, label;
    if (span > 3 * 365 * DAY) {
      step = Math.max(1, Math.ceil(span / (365.25 * DAY) / 6));
      for (var y = d.getUTCFullYear(); ; y += step) {
        var at = Date.UTC(y, 0, 1);
        if (at > b) break;
        if (at >= a) out.push({ at: at, label: String(y) });
      }
      return out;
    }
    if (span > 60 * DAY) {
      var months = span / (30.44 * DAY);
      step = [1, 2, 3, 6, 12].filter(function (s) { return months / s <= 7; })[0] || 12;
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
    step = steps.filter(function (s) { return span / (s * unit) <= 7; })[0] || steps[steps.length - 1];
    var first = Math.ceil(a / (step * unit)) * step * unit;
    for (var v = first; v <= b; v += step * unit) {
      out.push({ at: v, label: unit === DAY ? fmtDate(v, false).slice(5) : fmtDate(v, true).slice(11) });
    }
    return out;
  }

  // Where each row sits along one axis, from lo to hi px: numbers and dates on a linear scale,
  // categories in bands with a little jitter. {pos: Float32Array (NaN when missing), ticks, title}
  function axis(col, n, lo, hi, salt) {
    var pos = new Float32Array(n), ticks = [], i;
    if (col.kind === 'categorical') {
      var order = axisLevels(col), slot = {}, bands = order.length + (col.blanks ? 1 : 0) || 1;
      order.forEach(function (k, j) { slot[k] = j; });
      var band = (hi - lo) / bands;
      for (i = 0; i < n; i++) {
        var k = col.codes[i], j = k < 0 ? bands - 1 : slot[k];
        pos[i] = lo + (j + 0.5 + jitter(i, salt) * 0.7) * band;
      }
      var every = Math.max(1, Math.ceil(bands / Math.max(2, Math.floor(Math.abs(hi - lo) / 60))));
      order.forEach(function (k, j) {
        if (j % every === 0) ticks.push({ at: lo + (j + 0.5) * band, label: cut(col.levels[k], 14), grid: false });
      });
      if (col.blanks) ticks.push({ at: lo + (bands - 0.5) * band, label: BLANK, grid: false });
      return { pos: pos, ticks: ticks };
    }
    var a = col.lo, b = col.hi;
    if (col.empty) { a = 0; b = 1; }
    if (a === b) { var w = col.kind === 'datetime' ? 864e5 : Math.abs(a) || 1; a -= w; b += w; }
    var padding = (b - a) * 0.03;
    a -= padding; b += padding;
    var scale = (hi - lo) / (b - a);
    for (i = 0; i < n; i++) {
      var v = col.values[i];
      pos[i] = v === null ? NaN : lo + (v - a) * scale;
    }
    var marks = col.kind === 'datetime' ? timeTicks(a, b) : niceTicks(a, b, 6).map(function (v) {
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

  function setupDive(container, runtime) {
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
    var colour = null, hidden = {}, drawnWidth = 0, drawnW = 620;
    var xs = new Float32Array(n), ys = new Float32Array(n), shown = new Uint8Array(n), count = 0;
    var grid = null, cell = 12, radius = 3, hover = null;

    function visible(i) {
      return colour.kind !== 'categorical' || !hidden[colour.code(i)];
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
    function placeScatter(W, H) {
      var ML = 58, MR = 16, MT = 12, MB = 46;
      var xCol = data.cols[chosen('x')], yCol = data.cols[chosen('y')];
      var parts = [];
      if (!xCol || !yCol) { for (var m = 0; m < n; m++) xs[m] = ys[m] = NaN; return parts; }
      var ax = axis(xCol, n, ML, W - MR, 0), ay = axis(yCol, n, H - MB, MT, 1);
      for (var i = 0; i < n; i++) { xs[i] = ax.pos[i]; ys[i] = ay.pos[i]; }
      ax.ticks.forEach(function (t) {
        if (t.grid) parts.push('<line class="bf-dd__grid" x1="' + t.at.toFixed(1) + '" y1="' + MT + '" x2="' + t.at.toFixed(1) + '" y2="' + (H - MB) + '"/>');
        parts.push('<text class="bf-dd__tick" x="' + t.at.toFixed(1) + '" y="' + (H - MB + 16) + '" text-anchor="middle">' + esc(t.label) + '</text>');
      });
      ay.ticks.forEach(function (t) {
        if (t.grid) parts.push('<line class="bf-dd__grid" x1="' + ML + '" y1="' + t.at.toFixed(1) + '" x2="' + (W - MR) + '" y2="' + t.at.toFixed(1) + '"/>');
        parts.push('<text class="bf-dd__tick" x="' + (ML - 6) + '" y="' + t.at.toFixed(1) + '" text-anchor="end" dominant-baseline="middle">' + esc(t.label) + '</text>');
      });
      parts.push('<line class="bf-dd__axis" x1="' + ML + '" y1="' + (H - MB) + '" x2="' + (W - MR) + '" y2="' + (H - MB) + '"/>');
      parts.push('<line class="bf-dd__axis" x1="' + ML + '" y1="' + MT + '" x2="' + ML + '" y2="' + (H - MB) + '"/>');
      parts.push('<text class="bf-dd__title" x="' + ((ML + W - MR) / 2) + '" y="' + (H - 8) + '" text-anchor="middle">' + esc(chosen('x')) + '</text>');
      parts.push('<text class="bf-dd__title" transform="rotate(-90)" x="' + (-(MT + H - MB) / 2) + '" y="14" text-anchor="middle">' + esc(chosen('y')) + '</text>');
      return parts;
    }

    // The categories of a tile axis: a column's levels, or a number's bins. {labels, of(i) -> index}
    function tileAxis(col) {
      if (!col) return { labels: [''], of: function () { return 0; } };
      if (col.kind === 'categorical') {
        var order = axisLevels(col), slot = {};
        order.forEach(function (k, j) { slot[k] = j; });
        var labels = order.map(function (k) { return col.levels[k]; });
        if (col.blanks) labels.push(BLANK);
        return { labels: labels, of: function (i) { var k = col.codes[i]; return k < 0 ? labels.length - 1 : slot[k]; } };
      }
      if (col.empty) return { labels: [BLANK], of: function () { return 0; } };
      var a = col.lo, b = col.hi, bins = a === b ? 1 : TILE_BINS, step = (b - a) / bins || 1;
      var show = col.kind === 'datetime' ? function (v) { return fmtDate(v, false); } : fmtTick;
      var names = [];
      for (var k = 0; k < bins; k++) names.push(bins === 1 ? show(a) : show(a + k * step) + '–' + show(a + (k + 1) * step));
      var hasBlank = col.values.some(function (v) { return v === null; });
      if (hasBlank) names.push(BLANK);
      return {
        labels: names,
        of: function (i) {
          var v = col.values[i];
          if (v === null) return names.length - 1;
          return Math.max(0, Math.min(bins - 1, Math.floor((v - a) / step)));
        }
      };
    }

    function placeTile(W, H) {
      var LX = 96, LY = 42, PAD = 5;
      var xCol = data.cols[chosen('x')], yCol = chosen('y') ? data.cols[chosen('y')] : null;
      var parts = [];
      if (!xCol) return parts;
      var tx = tileAxis(xCol), ty = tileAxis(yCol);
      var cw = (W - LX) / tx.labels.length, ch = (H - LY) / ty.labels.length;
      var cells = {}, most = 1, i;
      for (i = 0; i < n; i++) {
        xs[i] = ys[i] = NaN;
        if (!shown[i]) continue;
        var key = tx.of(i) + ',' + ty.of(i);
        (cells[key] || (cells[key] = [])).push(i);
      }
      Object.keys(cells).forEach(function (k) { most = Math.max(most, cells[k].length); });
      var room = Math.max(1, (cw - 2 * PAD) * (ch - 2 * PAD));
      var step = Math.max(1.5, Math.min(11, Math.floor(Math.sqrt(room / most) * 10) / 10));
      radius = Math.max(0.6, step * 0.42);
      var rank = colour.kind === 'categorical' ? function (r) { var k = colour.code(r); return k < 0 ? 1e9 : k; } : function (r) { return 0; };
      Object.keys(cells).forEach(function (key) {
        var at = key.split(','), cx = +at[0], cy = +at[1];
        var list = cells[key].slice().sort(function (p, q) { return rank(p) - rank(q) || p - q; });
        var per = Math.max(1, Math.floor((cw - 2 * PAD) / step));
        list.forEach(function (r, d) {
          xs[r] = LX + cx * cw + PAD + (d % per) * step + step / 2;
          ys[r] = LY + cy * ch + PAD + Math.floor(d / per) * step + step / 2;
          if (ys[r] > LY + (cy + 1) * ch) { xs[r] = ys[r] = NaN; }
        });
      });
      tx.labels.forEach(function (label, j) {
        var x0 = LX + j * cw;
        parts.push('<line class="bf-dd__grid" x1="' + x0.toFixed(1) + '" y1="' + LY + '" x2="' + x0.toFixed(1) + '" y2="' + H + '"/>');
        parts.push('<text class="bf-dd__head" x="' + (x0 + cw / 2).toFixed(1) + '" y="' + (LY - 8) + '" text-anchor="middle">' + esc(cut(label, Math.max(4, Math.floor(cw / 7)))) + '</text>');
      });
      ty.labels.forEach(function (label, j) {
        var y0 = LY + j * ch;
        parts.push('<line class="bf-dd__grid" x1="' + LX + '" y1="' + y0.toFixed(1) + '" x2="' + W + '" y2="' + y0.toFixed(1) + '"/>');
        if (yCol) parts.push('<text class="bf-dd__head" x="' + (LX - 8) + '" y="' + (y0 + ch / 2).toFixed(1) + '" text-anchor="end" dominant-baseline="middle">' + esc(cut(label, 13)) + '</text>');
      });
      parts.push('<rect class="bf-dd__frame" x="' + LX + '" y="' + LY + '" width="' + (W - LX) + '" height="' + (H - LY) + '"/>');
      parts.push('<text class="bf-dd__title" x="' + (LX + (W - LX) / 2) + '" y="11" text-anchor="middle">' + esc(chosen('x')) + '</text>');
      if (yCol) parts.push('<text class="bf-dd__title" transform="rotate(-90)" x="' + (-(LY + H) / 2) + '" y="12" text-anchor="middle">' + esc(chosen('y')) + '</text>');
      return parts;
    }

    // ── drawing
    function draw() {
      var W = Math.max(280, Math.round(area.clientWidth || 620));
      var H = Math.round(Math.max(240, Math.min(640, W * (layout === 'tile' ? 0.6 : 0.62))));
      drawnWidth = area.clientWidth;
      drawnW = W;
      var dpr = Math.min(3, window.devicePixelRatio || 1);
      canvas.width = Math.round(W * dpr);
      canvas.height = Math.round(H * dpr);
      svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);

      count = 0;
      for (var i = 0; i < n; i++) { shown[i] = visible(i) ? 1 : 0; count += shown[i]; }
      var parts = layout === 'tile' ? placeTile(W, H) : placeScatter(W, H);
      if (layout !== 'tile') radius = count > 20000 ? 1.4 : count > 5000 ? 2 : count > 1000 ? 2.8 : 3.6;

      var ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, W, H);
      ctx.globalAlpha = layout === 'tile' ? 0.85 : count > 20000 ? 0.55 : 0.72;
      var groups = {}, order = [];
      grid = {};
      cell = Math.max(8, radius * 3);
      for (i = 0; i < n; i++) {
        if (!shown[i] || xs[i] !== xs[i] || ys[i] !== ys[i]) continue;
        var c = colour.of(i);
        if (!groups[c]) { groups[c] = []; order.push(c); }
        groups[c].push(i);
        var key = Math.floor(xs[i] / cell) + ',' + Math.floor(ys[i] / cell);
        (grid[key] || (grid[key] = [])).push(i);
      }
      var square = radius < 1.8;
      order.forEach(function (c) {
        ctx.fillStyle = c;
        var list = groups[c];
        if (square) {
          for (var j = 0; j < list.length; j++) ctx.fillRect(xs[list[j]] - radius, ys[list[j]] - radius, radius * 2, radius * 2);
          return;
        }
        ctx.beginPath();
        for (var k = 0; k < list.length; k++) {
          var p = list[k];
          ctx.moveTo(xs[p] + radius, ys[p]);
          ctx.arc(xs[p], ys[p], radius, 0, 2 * Math.PI);
        }
        ctx.fill();
      });
      ctx.globalAlpha = 1;

      parts.push('<circle class="bf-dd__hover" r="' + (radius + 2.5) + '" cx="-99" cy="-99"/>');
      svg.innerHTML = parts.join('');
      hover = svg.querySelector('.bf-dd__hover');
      footer.textContent = count === n ? fmtNum(n) + ' rows' : fmtNum(count) + ' of ' + fmtNum(n) + ' shown';
      var described = layout === 'tile' ? 'DataDive tiles by ' + chosen('x') + (chosen('y') ? ' and ' + chosen('y') : '')
        : 'DataDive scatter plot of ' + chosen('y') + ' against ' + chosen('x');
      canvas.setAttribute('aria-label', described + (chosen('color') ? ', coloured by ' + chosen('color') : '') +
        ': ' + fmtNum(count) + ' of ' + fmtNum(n) + ' dots');
      tip.hidden = true;
      if (printing) vector(true);  // printing narrows the page: a redraw keeps the printed circles
    }

    // ── hover
    function nearest(x, y) {
      var gx = Math.floor(x / cell), gy = Math.floor(y / cell), best = -1, bestD = (radius + 4) * (radius + 4);
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

    function showTip(i, e) {
      tip.innerHTML = '';
      data.names.slice(0, 10).forEach(function (name) {
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

    canvas.addEventListener('mousemove', function (e) {
      var rect = canvas.getBoundingClientRect(), unit = drawnW / rect.width;  // screen px -> drawing px
      var i = nearest((e.clientX - rect.left) * unit, (e.clientY - rect.top) * unit);
      if (i < 0) { tip.hidden = true; hover.setAttribute('cx', '-99'); canvas.style.cursor = ''; return; }
      hover.setAttribute('cx', xs[i].toFixed(1));
      hover.setAttribute('cy', ys[i].toFixed(1));
      canvas.style.cursor = 'pointer';
      showTip(i, e);
    });
    canvas.addEventListener('mouseleave', function () { tip.hidden = true; hover.setAttribute('cx', '-99'); });

    // ── controls
    function recolour() {
      colour = colouring(data, chosen('color'), look);
      hidden = {};
      drawLegend();
    }
    Object.keys(selects).forEach(function (name) {
      selects[name].addEventListener('change', function () {
        if (name === 'color') recolour();
        draw();
      });
    });

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
      if (!on || count > PRINT_VECTOR) return;
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
      shown: function () { return count; },
      total: n,
      dot: function (i) { return { x: xs[i], y: ys[i], colour: colour.of(i), shown: !!shown[i] }; },
      radius: function () { return radius; },
      width: function () { return drawnW; }
    };
  }

  window.briefing.register('lab', function (runtime) {
    var dives = [];
    runtime.onPrint(function () { dives.forEach(function (d) { d.briefingDive.vector(true); }); },
                    function () { dives.forEach(function (d) { d.briefingDive.vector(false); }); });
    return function (root) {
      root.querySelectorAll('.bf-datadive').forEach(function (el) {
        setupDive(el, runtime);
        if (el.briefingDive && dives.indexOf(el) < 0) dives.push(el);
      });
    };
  });
})();
