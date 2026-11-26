/* briefing lab: linked selection (#21) — a bar of a DataProfile or a DataCompare built with
   selects= highlights its rows in a DataDive. A click selects a bar (its range or its value);
   Shift+click adds another bar of the same column; clicking it again, the chip's × in the
   DataDive, or Esc clears. The selection travels as a bf:select event on the report's root,
   which the DataDive (lab.js) listens for, so nothing crosses into another report. Vanilla JS. */
(function () {
  'use strict';

  var senders = [];  // every sender's clear(), for Esc

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
      var detail = { targets: targets, source: source, from: from, column: null, test: null, picks: [], labels: [] };
      if (state.chart && state.picks.length) {
        detail.column = state.chart.getAttribute('data-bf-column');
        try { detail.test = JSON.parse(state.chart.getAttribute('data-bf-test')); } catch (e) { return; }
        detail.picks = state.picks.slice();
        hitsOf(state.chart).forEach(function (hit) {
          if (detail.picks.indexOf(hit.getAttribute('data-bf-pick')) >= 0) detail.labels.push(hit.getAttribute('data-bf-label'));
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

    // A click selects this bar; again, unselects it. Shift adds it to the bars of the same column.
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
    // The DataDive's × on the chip: forget the selection, without sending it again.
    root.addEventListener('bf:unselect', function (e) {
      if (e.detail && e.detail.source === source) clear(true);
    });
    senders.push(clear);
  }

  window.briefing.register('select', function (runtime) {
    runtime.on(document, 'keydown', function (e) {
      if (e.key === 'Escape' || e.key === 'Esc') senders.forEach(function (clear) { clear(false); });
    });
    return function (root) {
      root.querySelectorAll('[data-bf-selects]').forEach(function (block) { setup(root, block); });
    };
  });
})();
