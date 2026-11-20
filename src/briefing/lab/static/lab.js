/* briefing.lab — DataDive interactive dot explorer. Vanilla JS, no deps.
   Inlined into a report only when a DataDive block is present. */
(function () {
  'use strict';

  function setupDive(container) {
    var dataEl = container.querySelector('.bf-dd__data');
    var metaEl = container.querySelector('.bf-dd__meta');
    var svgEl  = container.querySelector('.bf-dd__plot');
    var tip    = container.querySelector('.bf-dd__tooltip');
    if (!dataEl || !metaEl || !svgEl) return;

    var layout = container.dataset.layout || 'scatter';
    var rows = JSON.parse(dataEl.textContent);
    var meta = JSON.parse(metaEl.textContent);
    var cols = Object.keys(meta);
    var selects = {};

    container.querySelectorAll('.bf-dd__sel').forEach(function (sel) {
      selects[sel.dataset.axis] = sel;
      sel.addEventListener('change', render);
    });

    // ── viewport constants
    var ML = 52, MR = 16, MT = 16, MB = 44;
    var VW = 620, VH = 400;
    var PW = VW - ML - MR;
    var PH = VH - MT - MB;

    // ── colour palette (10 accessible hues)
    var PAL = ['#4F46E5','#10b981','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#f97316','#84cc16','#ec4899','#6b7280'];

    function getVal(axis) { return selects[axis] ? selects[axis].value : ''; }

    function isNum(col) { return meta[col] === 'numeric'; }

    // ── linear scale [mn,mx] → [a,b]
    function linearScale(vals, a, b) {
      var valid = vals.filter(function (v) { return v !== null && v !== undefined && !isNaN(+v); });
      if (!valid.length) return function () { return (a + b) / 2; };
      var mn = Math.min.apply(null, valid), mx = Math.max.apply(null, valid);
      if (mn === mx) return function (v) { return v === null ? null : (a + b) / 2; };
      return function (v) { return v === null ? null : a + (v - mn) / (mx - mn) * (b - a); };
    }

    // ── ordinal scale: unique values → evenly spaced positions
    function ordinalScale(vals, a, b) {
      var seen = [], map = {};
      vals.forEach(function (v) { var s = v === null ? '__null__' : String(v); if (!(s in map)) { map[s] = seen.length; seen.push(s); } });
      var n = seen.length || 1;
      return function (v) {
        var s = v === null ? '__null__' : String(v);
        return s in map ? a + (map[s] + 0.5) / n * (b - a) : null;
      };
    }

    // ── ordinal tick labels (up to 8)
    function ordinalTicks(vals, scale, axis) {
      var seen = [], map = {};
      vals.forEach(function (v) { var s = v === null ? '__null__' : String(v); if (!(s in map)) { map[s] = seen.length; seen.push(s); } });
      var MAX = 8, step = Math.max(1, Math.ceil(seen.length / MAX));
      var out = '';
      for (var i = 0; i < seen.length; i += step) {
        var pos = scale(seen[i] === '__null__' ? null : seen[i]);
        if (pos === null) continue;
        var lbl = seen[i].length > 12 ? seen[i].slice(0, 11) + '…' : seen[i];
        if (axis === 'x') {
          out += '<text x="' + pos.toFixed(1) + '" y="' + (PH + 18) + '" text-anchor="middle" font-size="10" fill="var(--bf-muted)">' + _esc(lbl) + '</text>';
        } else {
          out += '<text x="-6" y="' + pos.toFixed(1) + '" text-anchor="end" dominant-baseline="middle" font-size="10" fill="var(--bf-muted)">' + _esc(lbl) + '</text>';
        }
      }
      return out;
    }

    // ── numeric tick labels (up to 6)
    function numericTicks(vals, scale, axis) {
      var valid = vals.filter(function (v) { return v !== null && !isNaN(+v); });
      if (!valid.length) return '';
      var mn = Math.min.apply(null, valid), mx = Math.max.apply(null, valid);
      var TICKS = 5, out = '';
      for (var i = 0; i <= TICKS; i++) {
        var v = mn + (mx - mn) * i / TICKS;
        var pos = scale(v);
        var lbl = Math.abs(v) >= 1e4 ? v.toExponential(1) : +v.toPrecision(3) + '';
        if (axis === 'x') {
          out += '<text x="' + pos.toFixed(1) + '" y="' + (PH + 18) + '" text-anchor="middle" font-size="10" fill="var(--bf-muted)">' + lbl + '</text>';
          out += '<line x1="' + pos.toFixed(1) + '" y1="0" x2="' + pos.toFixed(1) + '" y2="' + PH + '" stroke="var(--bf-border)" stroke-width="0.5" stroke-dasharray="3,3"/>';
        } else {
          out += '<text x="-6" y="' + pos.toFixed(1) + '" text-anchor="end" dominant-baseline="middle" font-size="10" fill="var(--bf-muted)">' + lbl + '</text>';
          out += '<line x1="0" y1="' + pos.toFixed(1) + '" x2="' + PW + '" y2="' + pos.toFixed(1) + '" stroke="var(--bf-border)" stroke-width="0.5" stroke-dasharray="3,3"/>';
        }
      }
      return out;
    }

    // ── colour function
    function makeColor(colorCol, colorVals) {
      if (!colorCol) return function () { return PAL[0]; };
      if (isNum(colorCol)) {
        var valid = colorVals.filter(function (v) { return v !== null; });
        var mn = Math.min.apply(null, valid), mx = Math.max.apply(null, valid), rng = mx - mn || 1;
        return function (v) {
          if (v === null) return '#9ca3af';
          var t = (v - mn) / rng;
          // indigo → amber gradient
          var r = Math.round(79  + t * (245 - 79));
          var g = Math.round(70  + t * (158 - 70));
          var b = Math.round(229 + t * (11  - 229));
          return 'rgb(' + r + ',' + g + ',' + b + ')';
        };
      } else {
        var map = {};
        var idx = 0;
        return function (v) {
          var s = v === null ? '' : String(v);
          if (!(s in map)) map[s] = idx++ % PAL.length;
          return PAL[map[s]];
        };
      }
    }

    function _esc(s) {
      return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
    }

    function render() {
      var xCol    = getVal('x');
      var yCol    = getVal('y');
      var colorCol = getVal('color');
      if (!xCol || !yCol || !rows.length) { svgEl.innerHTML = ''; return; }

      var xVals = rows.map(function (r) { return r[xCol]; });
      var yVals = rows.map(function (r) { return r[yCol]; });
      var cVals = colorCol ? rows.map(function (r) { return r[colorCol]; }) : null;

      var xScale = isNum(xCol) ? linearScale(xVals, 0, PW) : ordinalScale(xVals, 0, PW);
      var yScale = isNum(yCol) ? linearScale(yVals, PH, 0) : ordinalScale(yVals, PH, 0);
      var colorFn = makeColor(colorCol, cVals);

      var xTicks = isNum(xCol) ? numericTicks(xVals, xScale, 'x') : ordinalTicks(xVals, xScale, 'x');
      var yTicks = isNum(yCol) ? numericTicks(yVals, yScale, 'y') : ordinalTicks(yVals, yScale, 'y');

      // Axes
      var axes = (
        '<line x1="0" y1="' + PH + '" x2="' + PW + '" y2="' + PH + '" stroke="var(--bf-border)"/>' +
        '<line x1="0" y1="0" x2="0" y2="' + PH + '" stroke="var(--bf-border)"/>' +
        xTicks + yTicks
      );

      // Axis labels
      var xLbl = '<text x="' + (PW/2) + '" y="' + (PH + 38) + '" text-anchor="middle" font-size="12" fill="var(--bf-muted)">' + _esc(xCol) + '</text>';
      var yLbl = '<text transform="rotate(-90)" x="-' + (PH/2) + '" y="-42" text-anchor="middle" font-size="12" fill="var(--bf-muted)">' + _esc(yCol) + '</text>';

      // Dots
      var dots = '';
      for (var i = 0; i < rows.length; i++) {
        var cx = xScale(xVals[i]);
        var cy = yScale(yVals[i]);
        if (cx === null || cy === null) continue;
        var fill = cVals ? colorFn(cVals[i]) : PAL[0];
        dots += '<circle class="bf-dd__dot" cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) + '" r="3.5" fill="' + fill + '" fill-opacity="0.72" data-i="' + i + '"/>';
      }

      svgEl.innerHTML = (
        '<g transform="translate(' + ML + ',' + MT + ')">' +
        axes + yLbl + xLbl + dots +
        '</g>'
      );

      // Hover tooltip
      svgEl.querySelectorAll('.bf-dd__dot').forEach(function (dot) {
        dot.addEventListener('mouseenter', function (e) {
          var row = rows[parseInt(dot.dataset.i, 10)];
          var lines = Object.keys(row).slice(0, 10).map(function (k) {
            return '<b>' + _esc(k) + '</b>: ' + _esc(row[k] === null ? '—' : row[k]);
          });
          tip.innerHTML = lines.join('<br>');
          tip.hidden = false;
          var rect = svgEl.getBoundingClientRect();
          var px = e.clientX - rect.left + 10;
          var py = e.clientY - rect.top  - 8;
          if (px + 180 > rect.width)  px = e.clientX - rect.left - 190;
          if (py + 140 > rect.height) py = e.clientY - rect.top  - 150;
          tip.style.left = px + 'px';
          tip.style.top  = py + 'px';
        });
        dot.addEventListener('mouseleave', function () { tip.hidden = true; });
      });
    }

    // ── tile layout (Facets Dive–style packed dots) ────────────────────────

    // Map a numeric column's values to N evenly-spaced bin labels.
    // Returns { labels: string[], fn: (rawValue) → binLabel }
    function bucketize(col, nBins) {
      var vals = rows.map(function (r) { return r[col]; }).filter(function (v) { return v !== null && !isNaN(+v); });
      if (!vals.length) return { labels: ['(no data)'], fn: function () { return '(no data)'; } };
      var mn = Math.min.apply(null, vals), mx = Math.max.apply(null, vals);
      if (mn === mx) {
        var lbl = String(+mn.toPrecision(4));
        return { labels: [lbl], fn: function () { return lbl; } };
      }
      var step = (mx - mn) / nBins;
      // Format a boundary value compactly
      function fmt(v) {
        if (Math.abs(v) >= 1e4 || (Math.abs(v) < 0.01 && v !== 0)) return +v.toPrecision(3) + '';
        return Math.round(v * 100) / 100 + '';
      }
      var labels = [];
      for (var b = 0; b < nBins; b++) {
        labels.push(fmt(mn + b * step) + '–' + fmt(mn + (b + 1) * step));
      }
      return {
        labels: labels,
        fn: function (v) {
          if (v === null || isNaN(+v)) return '(blank)';
          var b = Math.floor((+v - mn) / step);
          if (b < 0) b = 0;
          if (b >= nBins) b = nBins - 1;
          return labels[b];
        }
      };
    }

    function renderTile() {
      var xCol    = getVal('x');
      var colorCol = getVal('color');
      var yCol    = getVal('y');  // optional in tile mode
      if (!xCol || !rows.length) { svgEl.innerHTML = ''; return; }

      var colorFn = makeColor(colorCol, colorCol ? rows.map(function (r) { return r[colorCol]; }) : []);

      // Auto-bucketize numeric columns; keep categorical/datetime as-is
      var N_BINS = 5;
      var xBucket = isNum(xCol) ? bucketize(xCol, N_BINS) : null;
      var yBucket = (yCol && isNum(yCol)) ? bucketize(yCol, N_BINS) : null;

      function xKey(r) {
        var v = r[xCol];
        return xBucket ? xBucket.fn(v) : (v === null ? '(blank)' : String(v));
      }
      function yKey(r) {
        if (!yCol) return '';
        var v = r[yCol];
        return yBucket ? yBucket.fn(v) : (v === null ? '(blank)' : String(v));
      }

      // Collect unique category values (preserving bin order for numeric)
      var xCats = xBucket ? xBucket.labels : (function () {
        var seen = {}, out = [];
        rows.forEach(function (r) { var s = xKey(r); if (!(s in seen)) { seen[s] = 1; out.push(s); } });
        return out.sort();
      }());
      var yCats = !yCol ? [''] : (yBucket ? yBucket.labels : (function () {
        var seen = {}, out = [];
        rows.forEach(function (r) { var s = yKey(r); if (!(s in seen)) { seen[s] = 1; out.push(s); } });
        return out.sort();
      }()));

      // Layout constants
      var LABEL_X  = 90;   // px reserved for Y-axis labels
      var LABEL_Y  = 30;   // px reserved for X-axis labels (top)
      var CELL_PAD = 6;    // inner cell padding
      var DOT_R    = 4;    // dot radius
      var DOT_STEP = DOT_R * 2 + 2;  // dot centre-to-centre spacing

      var viewW = parseFloat(svgEl.getAttribute('viewBox').split(' ')[2]);
      var viewH = parseFloat(svgEl.getAttribute('viewBox').split(' ')[3]);

      var cellW = Math.max(40, (viewW - LABEL_X) / xCats.length);
      var cellH = Math.max(40, (viewH - LABEL_Y) / yCats.length);
      var dotsPerRow = Math.max(1, Math.floor((cellW - CELL_PAD * 2) / DOT_STEP));

      // Group rows into cells
      var cells = {};
      rows.forEach(function (row, i) {
        var k = xKey(row) + '|||' + yKey(row);
        if (!cells[k]) cells[k] = [];
        cells[k].push(i);
      });

      var out = '';

      // X-axis column headers
      xCats.forEach(function (xCat, xi) {
        var cx = LABEL_X + xi * cellW + cellW / 2;
        var lbl = xCat.length > 14 ? xCat.slice(0, 13) + '…' : xCat;
        out += '<text x="' + cx.toFixed(1) + '" y="' + (LABEL_Y - 6) + '" text-anchor="middle" font-size="11" font-weight="600" fill="var(--bf-text)">' + _esc(lbl) + '</text>';
        // Column divider
        var dx = LABEL_X + xi * cellW;
        out += '<line x1="' + dx + '" y1="' + LABEL_Y + '" x2="' + dx + '" y2="' + viewH + '" stroke="var(--bf-border)" stroke-width="0.5"/>';
      });
      // X-axis column header label
      out += '<text x="' + (LABEL_X + (viewW - LABEL_X) / 2) + '" y="12" text-anchor="middle" font-size="10" fill="var(--bf-muted)">' + _esc(xCol) + '</text>';

      // Y-axis row headers
      yCats.forEach(function (yCat, yi) {
        var cy = LABEL_Y + yi * cellH + cellH / 2;
        var lbl = yCat.length > 12 ? yCat.slice(0, 11) + '…' : yCat;
        out += '<text x="' + (LABEL_X - 8) + '" y="' + cy.toFixed(1) + '" text-anchor="end" dominant-baseline="middle" font-size="11" font-weight="600" fill="var(--bf-text)">' + _esc(lbl) + '</text>';
        // Row divider
        var dy = LABEL_Y + yi * cellH;
        out += '<line x1="' + LABEL_X + '" y1="' + dy + '" x2="' + viewW + '" y2="' + dy + '" stroke="var(--bf-border)" stroke-width="0.5"/>';
      });
      if (yCol) {
        out += '<text transform="rotate(-90)" x="-' + (LABEL_Y + (viewH - LABEL_Y) / 2) + '" y="12" text-anchor="middle" font-size="10" fill="var(--bf-muted)">' + _esc(yCol) + '</text>';
      }

      // Outer border
      out += '<rect x="' + LABEL_X + '" y="' + LABEL_Y + '" width="' + (viewW - LABEL_X) + '" height="' + (viewH - LABEL_Y) + '" fill="none" stroke="var(--bf-border)"/>';

      // Dots per cell
      var dotEls = [];
      xCats.forEach(function (xCat, xi) {
        yCats.forEach(function (yCat, yi) {
          var k = xCat + '|||' + yCat;
          var cellRows = cells[k] || [];
          var originX = LABEL_X + xi * cellW + CELL_PAD;
          var originY = LABEL_Y + yi * cellH + CELL_PAD;

          cellRows.forEach(function (ri, di) {
            var col = di % dotsPerRow;
            var row = Math.floor(di / dotsPerRow);
            var cx = originX + col * DOT_STEP + DOT_R;
            var cy = originY + row * DOT_STEP + DOT_R;
            if (cy + DOT_R > LABEL_Y + (yi + 1) * cellH - 1) return; // clip

            var cVal = colorCol ? rows[ri][colorCol] : null;
            var fill = colorCol ? colorFn(cVal) : PAL[0];
            var el = '<circle class="bf-dd__dot" cx="' + cx.toFixed(1) + '" cy="' + cy.toFixed(1) +
              '" r="' + DOT_R + '" fill="' + fill + '" fill-opacity="0.8" data-i="' + ri + '"/>';
            out += el;
            dotEls.push(ri);
          });
        });
      });

      svgEl.innerHTML = out;

      // Tooltip
      svgEl.querySelectorAll('.bf-dd__dot').forEach(function (dot) {
        dot.addEventListener('mouseenter', function (e) {
          var row = rows[parseInt(dot.dataset.i, 10)];
          var lines = Object.keys(row).slice(0, 10).map(function (k) {
            return '<b>' + _esc(k) + '</b>: ' + _esc(row[k] === null ? '—' : row[k]);
          });
          tip.innerHTML = lines.join('<br>');
          tip.hidden = false;
          var rect = svgEl.getBoundingClientRect();
          var px = e.clientX - rect.left + 10;
          var py = e.clientY - rect.top  - 8;
          if (px + 200 > rect.width)  px = e.clientX - rect.left - 210;
          if (py + 150 > rect.height) py = e.clientY - rect.top  - 160;
          tip.style.left = px + 'px';
          tip.style.top  = py + 'px';
        });
        dot.addEventListener('mouseleave', function () { tip.hidden = true; });
      });
    }

    // ── dispatch based on layout ───────────────────────────────────────────

    function redraw() {
      if (layout === 'tile') renderTile(); else render();
    }

    container.querySelectorAll('.bf-dd__sel').forEach(function (sel) {
      sel.removeEventListener('change', render);
      sel.addEventListener('change', redraw);
    });

    redraw();
  }

  window.briefing.register('lab', function () {
    return function (root) { root.querySelectorAll('.bf-datadive').forEach(setupDive); };
  });

})();
