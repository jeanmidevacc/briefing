/* Grow each live example's iframe to the height of the report inside it.
   The report is served from the same site, so its document is readable. */
(function () {
  'use strict';
  function fit(frame) {
    var doc;
    try { doc = frame.contentDocument; } catch (e) { return; }
    if (!doc || !doc.body) return;  // e.g. a file:// build, where frames are cross-origin
    function resize() {
      var style = doc.defaultView.getComputedStyle(doc.body);
      var height = doc.body.offsetHeight + parseFloat(style.marginTop) + parseFloat(style.marginBottom);
      frame.style.height = Math.ceil(height) + 'px';
    }
    resize();
    if (window.ResizeObserver) new ResizeObserver(resize).observe(doc.body);
  }
  function init() {
    var frames = document.querySelectorAll('iframe.bf-example__frame');
    for (var i = 0; i < frames.length; i++) {
      (function (frame) {
        frame.addEventListener('load', function () { fit(frame); });
        if (frame.contentDocument && frame.contentDocument.readyState === 'complete') fit(frame);
      })(frames[i]);
    }
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
