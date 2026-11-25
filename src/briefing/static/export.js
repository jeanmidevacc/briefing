/* briefing export menu (#49) and snapshots (#215): only inlined with export="png" or "snapshot".
   "png": the header's "Save as PNG" button saves the open page. "snapshot": a camera button on each
   block marked data-bf-snap copies that block as a PNG to the clipboard, or downloads it when the
   clipboard is refused. Vanilla JS, no deps. */
(function () {
  'use strict';

  function slug(text) {
    return text.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_+|_+$/g, '');
  }

  // File name: the report title, plus the open page's tab label when there are pages, or the
  // label of the block it shows.
  function fileName(root, label) {
    var title = root.querySelector('.bf-report__title');
    var name = (title && title.textContent) || 'report';
    if (label) {
      name += ' ' + label.replace(/^this |^the | page$/g, '');
    } else {
      var tab = root.querySelector(
        '.bf-blocks > .bf-select:only-child > .bf-select__tablist > .bf-select__tab[aria-selected="true"]');
      if (tab) name += ' ' + tab.textContent;
    }
    return (slug(name) || 'report') + '.png';
  }

  // Copy a node with its computed styles inlined, so it renders the same inside an SVG.
  // Hidden elements, scripts, the menu itself, the block buttons (#124, #215), tables' CSV
  // buttons (#34) and Plotly's toolbar are left out.
  function cloneWithStyles(node) {
    if (node.nodeType === 3) return node.cloneNode(false);
    if (node.nodeType !== 1 || node.tagName === 'SCRIPT' || node.classList.contains('bf-export') ||
        node.classList.contains('bf-copy') || node.classList.contains('bf-dt__csv') ||
        node.classList.contains('bf-dt__csv-note') || node.classList.contains('modebar-container')) return null;
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

  // The colour behind an element: its own background, else the first ancestor's that is not
  // transparent, else the page's.
  function backgroundOf(el, root) {
    for (var node = el; node && node.nodeType === 1; node = node.parentNode) {
      var colour = getComputedStyle(node).backgroundColor;
      if (colour && colour !== 'transparent' && !/^rgba\(.*,\s*0\)$/.test(colour)) return colour;
    }
    return getComputedStyle(root.body || root.ownerDocument.body).backgroundColor;
  }

  // Draw an element as it is on screen into a canvas at 2x, with *margin* CSS px of the colour
  // behind it on every side, so content never touches the image's edge. A promise of a PNG blob.
  function drawPng(root, el, margin) {
    var rect = el.getBoundingClientRect();
    var width = Math.ceil(rect.width), height = Math.ceil(rect.height), scale = 2;
    var background = backgroundOf(el, root);
    var copy = cloneWithStyles(el);
    copy.style.margin = '0';
    var svg = '<svg xmlns="http://www.w3.org/2000/svg" width="' + width + '" height="' + height + '">' +
      '<foreignObject x="0" y="0" width="100%" height="100%">' +
      new XMLSerializer().serializeToString(copy) + '</foreignObject></svg>';
    return new Promise(function (resolve, reject) {
      var image = new Image();
      image.onload = function () {
        var canvas = document.createElement('canvas');
        canvas.width = (width + 2 * margin) * scale;
        canvas.height = (height + 2 * margin) * scale;
        var ctx = canvas.getContext('2d');
        ctx.fillStyle = background;
        ctx.fillRect(0, 0, canvas.width, canvas.height);
        ctx.scale(scale, scale);
        ctx.drawImage(image, margin, margin);
        canvas.toBlob(function (blob) {
          if (blob) resolve(blob); else reject(new Error('the image could not be drawn'));
        }, 'image/png');
      };
      image.onerror = function () { reject(new Error('the image could not be drawn')); };
      image.src = 'data:image/svg+xml;charset=utf-8,' + encodeURIComponent(svg);
    });
  }

  function download(root, blob, name) {
    var doc = root.ownerDocument || root;
    var link = doc.createElement('a');
    link.className = 'bf-copy';
    link.href = URL.createObjectURL(blob);
    link.download = name;
    (root.body || root).appendChild(link);
    link.click();
    link.remove();
    setTimeout(function () { URL.revokeObjectURL(link.href); }, 1000);
  }

  // The page's margin around the report in "Save as PNG" (its own top padding), and the
  // smaller one around a block's snapshot, in CSS px.
  var MARGIN = 32, BLOCK_MARGIN = 16;

  function savePng(root) {
    drawPng(root, root.querySelector('.bf-report'), MARGIN).then(function (blob) {
      download(root, blob, fileName(root));
    });
  }

  // The toast copy-embed.js uses too: one per root, whichever script makes it first.
  function toast(root, message) {
    var doc = root.ownerDocument || root;
    var el = root.querySelector('.bf-copy__toast');
    if (!el) {
      el = doc.createElement('div');
      el.className = 'bf-copy bf-copy__toast';
      el.setAttribute('role', 'status');
      (root.body || root).appendChild(el);
    }
    el.textContent = message;
    el.hidden = false;
    clearTimeout(el.bfTimer);
    el.bfTimer = setTimeout(function () { el.hidden = true; }, 3000);
  }

  // The block's toolbar, shared with the copy-embed button (#124): made by whichever comes first.
  function toolbar(block) {
    for (var c = block.firstElementChild; c; c = c.nextElementSibling) {
      if (c.classList.contains('bf-copy__tools')) return c;
    }
    var tools = block.ownerDocument.createElement('div');
    tools.className = 'bf-copy bf-copy__tools';
    block.appendChild(tools);
    return tools;
  }

  // Copy the block's image to the clipboard; when that is refused, download it. The clipboard
  // gets a promise of the image, so the write starts while the click still counts as one.
  function snapshot(root, block) {
    var label = block.getAttribute('data-bf-snap');
    var png = drawPng(root, block, BLOCK_MARGIN);
    var name = fileName(root, label);
    var copied;
    try {
      copied = navigator.clipboard.write([new window.ClipboardItem({ 'image/png': png })]);
    } catch (e) {
      copied = Promise.reject(e);
    }
    copied.then(function () {
      toast(root, 'Image copied to the clipboard');
    }, function () {
      return png.then(function (blob) {
        download(root, blob, name);
        toast(root, 'Image saved as ' + name);
      });
    }).catch(function () {
      toast(root, 'This part could not be drawn as an image');
    });
  }

  // A camera, drawn with lines in the text colour.
  var CAMERA = '<svg viewBox="0 0 16 16" width="14" height="14" aria-hidden="true" fill="none" ' +
    'stroke="currentColor" stroke-width="1.4" stroke-linejoin="round">' +
    '<path d="M2 5h2.5l1.2-1.8h4.6L11.5 5H14v8H2z"/><circle cx="8" cy="9" r="2.3"/></svg>';

  function addButton(root, block) {
    var doc = root.ownerDocument || root;
    var button = doc.createElement('button');
    button.type = 'button';
    button.className = 'bf-copy bf-copy__button bf-copy__button--image';
    button.setAttribute('aria-label', 'Copy ' + block.getAttribute('data-bf-snap') + ' as an image');
    button.title = 'Copy as an image';
    button.innerHTML = CAMERA;
    button.addEventListener('click', function (e) {
      e.stopPropagation();
      snapshot(root, block);
    });
    toolbar(block).appendChild(button);
  }

  window.briefing.register('export', function () {
    return function (root) {
      var menu = root.querySelector('.bf-export');
      var png = menu && menu.querySelector('.bf-export__btn[data-export="png"]');
      if (png) png.addEventListener('click', function () { savePng(root); });
      root.querySelectorAll('[data-bf-snap]').forEach(function (block) { addButton(root, block); });
    };
  });
})();
