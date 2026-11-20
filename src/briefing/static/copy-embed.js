/* briefing copy-embed (#124): only inlined in reports built with export=("embed",). Vanilla JS, no deps.
   Each block marked data-bf-embed gets a "</>" button that copies it as an embed fragment (#122). The
   fragment is cut from the untouched copy the report carries (script.bf-copy-data: gzip, base64), not
   from the page, so it is the report as rendered, before any sort, tab or chart drawing changed it. */
(function () {
  'use strict';

  // "<" spelled as an escape, so the tags this script writes never end the report's own script.
  var LT = '\x3C';
  // The copied fragment's own last line, as text: it initialises that fragment on the host page.
  var INIT = 'briefing.init(' + 'document' + '.getElementById("';
  var copies = typeof WeakMap === 'function' ? new WeakMap() : null;

  // The report's untouched copy, decompressed once per root (a promise of its JSON).
  function untouched(root) {
    if (copies && copies.has(root)) return copies.get(root);
    var el = root.querySelector('script.bf-copy-data');
    var promise = Promise.resolve().then(function () {
      var raw = atob(JSON.parse(el.textContent));
      var bytes = new Uint8Array(raw.length);
      for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
      var stream = new Blob([bytes]).stream().pipeThrough(new DecompressionStream('gzip'));
      return new Response(stream).text();
    }).then(JSON.parse);
    if (copies) copies.set(root, promise);
    return promise;
  }

  // FNV-1a, 32 bits: a short, stable id for an unnamed block.
  function hash(text) {
    var h = 0x811c9dc5;
    for (var i = 0; i < text.length; i++) h = Math.imul(h ^ text.charCodeAt(i), 0x01000193) >>> 0;
    return ('0000000' + h.toString(16)).slice(-8);
  }

  // Block n of the untouched copy, as a fragment like bf.stringify(block, full_html=False).
  function fragment(root, data, n) {
    var doc = new DOMParser().parseFromString(data.body, 'text/html');
    var block = doc.querySelector('[data-bf-embed-id="' + n + '"]');
    var named = block.hasAttribute('data-bf-link') ? block.id.split('/').pop() : '';
    var id = named || 'bf-e' + hash(block.outerHTML);
    // Its links point at its own ids, which now start with its embed id (as in Python's fragments).
    var links = {};
    var linked = [block].concat(Array.prototype.slice.call(block.querySelectorAll('[data-bf-link]')));
    linked.forEach(function (el) {
      if (!el.hasAttribute('data-bf-link')) return;
      links[el.id] = true;
      el.id = id + '-' + el.id;
    });
    block.querySelectorAll('a[href^="#"]').forEach(function (a) {
      var target = a.getAttribute('href').slice(1);
      if (links[target]) a.setAttribute('href', '#' + id + '-' + target);
    });
    [block].concat(Array.prototype.slice.call(block.querySelectorAll('[data-bf-embed]'))).forEach(function (el) {
      el.removeAttribute('data-bf-embed');
      el.removeAttribute('data-bf-embed-id');
    });
    var html = block.outerHTML.split(data.prefix).join(id + '-');
    var info = data.blocks[n];
    var runtimes = info.runtimes.map(function (name) {
      var source = root.querySelector('script[data-bf-runtime="' + name + '"]');
      return source ? LT + 'script>if (!window.' + name + ') (function (define, module, exports) {\n' +
        source.textContent + '\n}).call(window);' + LT + '/script>\n' : '';
    }).join('');
    var scripts = info.scripts.map(function (i) {
      return root.querySelector('script[data-bf-script="' + i + '"]').textContent;
    }).join('\n');
    return LT + '!-- briefing ' + data.version + ' embed: ' + id + ' -->\n' +
      LT + 'div class="bf-embed" id="' + id + '" data-bf-version="' + data.version + '">\n' +
      LT + 'style>\n' + data.css + LT + '/style>\n' + runtimes +
      LT + 'script>' + scripts + LT + '/script>\n' +
      LT + 'style>\n' + data.theme.split(data.token).join(id) + LT + '/style>\n' +
      LT + 'div class="bf-embed__body">' + LT + 'div class="bf-blocks">' + html + LT + '/div>' + LT + '/div>\n' +
      LT + 'div class="bf-embed__footer">' + data.footer + LT + '/div>\n' +
      LT + 'script>' + INIT + id + '"));' + LT + '/script>\n' +
      LT + '/div>\n';
  }

  function sizeOf(text) {
    var kb = new Blob([text]).size / 1024;
    return kb < 1000 ? Math.max(1, Math.round(kb)) + ' KB' : (kb / 1024).toFixed(1) + ' MB';
  }

  // The clipboard, else the older copy command, else false.
  function copy(root, text) {
    var doc = root.ownerDocument || root;
    var written = navigator.clipboard && navigator.clipboard.writeText
      ? navigator.clipboard.writeText(text) : Promise.reject(new Error('no clipboard'));
    return written.then(function () { return true; }, function () {
      var area = doc.createElement('textarea');
      area.className = 'bf-copy bf-copy__scratch';
      area.value = text;
      area.setAttribute('readonly', '');
      (root.body || root).appendChild(area);
      area.select();
      var ok = false;
      try { ok = doc.execCommand('copy'); } catch (e) { ok = false; }
      area.remove();
      return ok;
    });
  }

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

  // When both copies are refused (a sandboxed notebook frame): the code, selected, to copy by hand.
  function dialog(root, text, label) {
    var doc = root.ownerDocument || root;
    var box = doc.createElement('dialog');
    box.className = 'bf-copy bf-copy__dialog';
    box.setAttribute('aria-label', 'Embed code for ' + label);
    var note = doc.createElement('p');
    note.textContent = 'Copy this embed code (Ctrl+C or ⌘C) and paste it into another page.';
    var code = doc.createElement('textarea');
    code.className = 'bf-copy__code';
    code.readOnly = true;
    code.value = text;
    var close = doc.createElement('button');
    close.type = 'button';
    close.className = 'bf-copy__close';
    close.textContent = 'Close';
    close.addEventListener('click', function () { box.close(); });
    box.addEventListener('close', function () { box.remove(); });
    box.appendChild(note);
    box.appendChild(code);
    box.appendChild(close);
    (root.body || root).appendChild(box);
    box.showModal();
    code.focus();
    code.select();
  }

  function addButton(root, block) {
    var doc = root.ownerDocument || root;
    var label = block.getAttribute('data-bf-embed');
    var button = doc.createElement('button');
    button.type = 'button';
    button.className = 'bf-copy bf-copy__button';
    button.setAttribute('aria-label', 'Copy embed code for ' + label);
    button.title = 'Copy embed code';
    button.textContent = '</>';
    button.addEventListener('click', function (e) {
      e.stopPropagation();
      untouched(root).then(function (data) {
        var code = fragment(root, data, block.getAttribute('data-bf-embed-id'));
        return copy(root, code).then(function (copied) {
          if (copied) toast(root, 'Embed code copied, ' + sizeOf(code));
          else dialog(root, code, label);
        });
      });
    });
    block.appendChild(button);
  }

  window.briefing.register('copy-embed', function () {
    return function (root) {
      if (!root.querySelector('script.bf-copy-data')) return;  // never in fragments
      root.querySelectorAll('[data-bf-embed]').forEach(function (block) { addButton(root, block); });
    };
  });
})();
