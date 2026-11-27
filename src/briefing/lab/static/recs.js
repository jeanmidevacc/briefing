/* briefing lab: RecInspector (#18) — pick a user to see their history and each model's list,
   search the users, and switch items between their titles and their ids. Python drew the first
   user; this script draws the others from script.bf-recs__data with the same markup as
   user_html() in lab/_render_recs.py (a browser test compares the two for every user). Vanilla JS. */
(function () {
  'use strict';

  function thousands(n) { return String(n).replace(/\B(?=(\d{3})+(?!\d))/g, ','); }

  function count(n, one, many) { return thousands(n) + ' ' + (n === 1 ? one : many); }

  function el(doc, tag, cls, text) {
    var node = doc.createElement(tag);
    if (cls) node.setAttribute('class', cls);
    if (text !== undefined) node.textContent = text;
    return node;
  }

  // An item's title and id (CSS shows one of them), and a tooltip with both and its popularity.
  function name(doc, data, item) {
    var it = data.items[item], id = it[0], title = it[1];
    var interactions = count(it[2], 'interaction', 'interactions');
    var span = el(doc, 'span', 'bf-recs__name');
    span.setAttribute('title', (title ? id + ' · ' + title : id) + ' · ' + interactions + ' in the history');
    if (title) span.appendChild(el(doc, 'span', 'bf-recs__title', title));
    span.appendChild(el(doc, 'span', 'bf-recs__id', id));
    return span;
  }

  function mark(doc, kind, tip) {
    var span = el(doc, 'span', 'bf-recs__mark bf-recs__mark--' + kind, kind);
    span.setAttribute('title', tip);
    return span;
  }

  function heading(doc, text) { return el(doc, 'div', 'bf-recs__heading', text); }

  // The children of the section that shows user *index*, as user_html() writes them.
  function userNodes(doc, data, index) {
    var user = data.users[index], frag = doc.createDocumentFragment();
    var history = {};
    user.history.forEach(function (row) { history[row[0]] = true; });

    var who = el(doc, 'div', 'bf-recs__who');
    who.appendChild(el(doc, 'span', 'bf-recs__user-id', user.id));
    who.appendChild(el(doc, 'small', null, count(user.history.length, 'interaction', 'interactions') +
                       ' in the history'));
    frag.appendChild(who);

    var past = el(doc, 'div', 'bf-recs__history');
    if (user.history.length) {
      past.appendChild(heading(doc, 'History, most recent first'));
      var strip = el(doc, 'ol', 'bf-recs__strip');
      user.history.forEach(function (row) {
        var li = el(doc, 'li', 'bf-recs__item');
        li.setAttribute('data-item', data.items[row[0]][0]);
        li.appendChild(name(doc, data, row[0]));
        li.appendChild(el(doc, 'span', 'bf-recs__when', row[1]));
        strip.appendChild(li);
      });
      past.appendChild(strip);
    } else {
      past.appendChild(heading(doc, 'History'));
      past.appendChild(el(doc, 'p', 'bf-recs__none', 'No history.'));
    }
    frag.appendChild(past);

    var sets = user.lists.map(function (rows) {
      if (!rows) return null;
      var set = {};
      rows.forEach(function (row) { set[row[0]] = true; });
      return set;
    });
    var models = el(doc, 'div', 'bf-recs__models');
    data.models.forEach(function (model, k) {
      var column = el(doc, 'div', 'bf-recs__model');
      column.setAttribute('data-k', String(k));
      column.appendChild(heading(doc, model));
      var rows = user.lists[k];
      if (!rows) {
        column.appendChild(el(doc, 'p', 'bf-recs__none', 'No list.'));
        models.appendChild(column);
        return;
      }
      var list = el(doc, 'ol', 'bf-recs__list');
      rows.forEach(function (row) {
        var item = row[0], seen = !!history[item];
        var others = [];
        sets.forEach(function (set, o) { if (o !== k && set && set[item]) others.push(data.models[o]); });
        var li = el(doc, 'li', 'bf-recs__item' + (seen ? ' bf-recs__item--seen' : '') +
                    (others.length ? ' bf-recs__item--shared' : ''));
        li.setAttribute('data-item', data.items[item][0]);
        li.appendChild(el(doc, 'span', 'bf-recs__rank', row[1]));
        li.appendChild(name(doc, data, item));
        if (seen) li.appendChild(mark(doc, 'seen', 'Already in ' + user.id + '’s history'));
        if (others.length) li.appendChild(mark(doc, 'shared', 'Also recommended by ' + others.join(', ')));
        list.appendChild(li);
      });
      column.appendChild(list);
      models.appendChild(column);
    });
    frag.appendChild(models);
    return frag;
  }

  function setup(block) {
    var script = block.querySelector('script.bf-recs__data');
    var controls = block.querySelector('.bf-recs__controls');
    var section = block.querySelector('.bf-recs__user');
    if (!script || !controls || !section) return;
    var data;
    try { data = JSON.parse(script.textContent); } catch (e) { return; }
    var pick = controls.querySelector('.bf-recs__pick');
    var search = controls.querySelector('.bf-recs__search');
    var shown = controls.querySelector('.bf-recs__shown');
    controls.hidden = false;

    function show(index) {
      if (!data.users[index]) return;
      while (section.firstChild) section.removeChild(section.firstChild);
      section.appendChild(userNodes(section.ownerDocument, data, index));
      section.setAttribute('data-user', String(index));
      pick.value = String(index);
    }

    pick.addEventListener('change', function () { show(+pick.value); });
    search.addEventListener('input', function () {
      var query = search.value.trim().toLowerCase(), visible = 0, first = null;
      Array.prototype.forEach.call(pick.options, function (option) {
        var hit = data.users[+option.value].id.toLowerCase().indexOf(query) !== -1;
        option.hidden = !hit;
        option.disabled = !hit;
        if (hit) { visible += 1; if (first === null) first = +option.value; }
      });
      shown.textContent = visible === data.users.length ? '' :
        visible ? visible + ' of ' + data.users.length + ' users' : 'No user matches';
      if (first !== null && pick.options[pick.selectedIndex].hidden) show(first);
    });
    controls.querySelectorAll('.bf-recs__show').forEach(function (button) {
      button.addEventListener('click', function () {
        block.setAttribute('data-show', button.getAttribute('data-show'));
        controls.querySelectorAll('.bf-recs__show').forEach(function (b) {
          b.setAttribute('aria-pressed', String(b === button));
        });
      });
    });
    block.briefingRecs = { show: show, users: data.users.length };  // for tests
  }

  window.briefing.register('recs', function () {
    return function (root) {
      root.querySelectorAll('.bf-recs').forEach(setup);
    };
  });
})();
