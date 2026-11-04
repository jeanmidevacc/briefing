/* briefing export menu (#49): only inlined in reports built with export=. Vanilla JS, no deps. */
(function () {
  'use strict';

  var menu = document.querySelector('.bf-export');
  if (!menu) return;

  // File name: the report title, plus the open page's tab label when there are pages.
  function fileName() {
    var tab = document.querySelector(
      '.bf-blocks > .bf-select:only-child > .bf-select__tablist > .bf-select__tab[aria-selected="true"]');
    var name = (document.title || 'report') + (tab ? ' ' + tab.textContent : '');
    return (name.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'report') + '.png';
  }

  // Copy a node with its computed styles inlined, so it renders the same inside an SVG.
  // Hidden elements, scripts and the menu itself are left out.
  function cloneWithStyles(node) {
    if (node.nodeType === 3) return node.cloneNode(false);
    if (node.nodeType !== 1 || node.tagName === 'SCRIPT' || node.classList.contains('bf-export')) return null;
    var style = getComputedStyle(node);
    if (style.display === 'none') return null;
    var css = '';
    for (var i = 0; i < style.length; i++) css += style[i] + ':' + style.getPropertyValue(style[i]) + ';';
    var copy;
    if (node.tagName === 'CANVAS') {
      copy = document.createElement('img');
      try { copy.src = node.toDataURL(); } catch (e) { /* a tainted or WebGL canvas stays blank */ }
    } else {
      copy = node.cloneNode(false);
      if (node.tagName === 'INPUT') copy.setAttribute('value', node.value);
    }
    copy.setAttribute('style', css);
    for (var c = node.firstChild; c; c = c.nextSibling) {
      var child = cloneWithStyles(c);
      if (child) copy.appendChild(child);
    }
    return copy;
  }

  // Draw the report as it is on screen (the open page) into a canvas at 2x and download it.
  function savePng() {
    var report = document.querySelector('.bf-report');
    var rect = report.getBoundingClientRect();
    var width = Math.ceil(rect.width), height = Math.ceil(rect.height), scale = 2;
    var background = getComputedStyle(document.body).backgroundColor;
    var copy = cloneWithStyles(report);
    copy.style.margin = '0';
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + width + '" height="' + height + '">' +
      '<foreignObject x="0" y="0" width="100%" height="100%">' +
      new XMLSerializer().serializeToString(copy) + '</foreignObject></svg>';
    var image = new Image();
    image.onload = function () {
      var canvas = document.createElement('canvas');
      canvas.width = width * scale;
      canvas.height = height * scale;
      var ctx = canvas.getContext('2d');
      ctx.fillStyle = background;
      ctx.fillRect(0, 0, canvas.width, canvas.height);
      ctx.scale(scale, scale);
      ctx.drawImage(image, 0, 0);
      canvas.toBlob(function (blob) {
        var link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = fileName();
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(function () { URL.revokeObjectURL(link.href); }, 1000);
      }, 'image/png');
    };
    image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
  }

  menu.querySelectorAll('.bf-export__btn').forEach(function (button) {
    button.addEventListener('click', function () {
      if (button.getAttribute('data-export') === 'png') savePng();
      else window.print();
    });
  });
})();
