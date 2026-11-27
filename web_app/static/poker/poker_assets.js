/* Графика Poker Club: карты, объёмные фишки, клубные портреты (SVG, 100% офлайн). */
window.PokerAssets = (function () {
  const SUITS = {
    h: '<path d="M12 21.2C4.6 15.2 2 11.7 2 8.3 2 5.4 4.2 3.4 6.8 3.4c2 0 3.8 1.1 5.2 3.2 1.4-2.1 3.2-3.2 5.2-3.2 2.6 0 4.8 2 4.8 4.9 0 3.4-2.6 6.9-10 12.9z"/>',
    d: '<path d="M12 1.5 20.5 12 12 22.5 3.5 12z"/>',
    s: '<path d="M12 1.8C12 1.8 3 8.6 3 13.9a4.6 4.6 0 0 0 8 3.1c-.2 2.2-1 3.8-2.6 5.2h7.2c-1.6-1.4-2.4-3-2.6-5.2a4.6 4.6 0 0 0 8-3.1C21 8.6 12 1.8 12 1.8z"/>',
    c: '<circle cx="12" cy="7.3" r="4.6"/><circle cx="6.8" cy="14.2" r="4.6"/><circle cx="17.2" cy="14.2" r="4.6"/><path d="M12 11.5l-3 10.6h6z"/>',
  };

  function suitSVG(s) {
    return '<svg class="suit" viewBox="0 0 24 24" aria-hidden="true">' + SUITS[s] + '</svg>';
  }

  function cardFace(code, size) {
    const r = code[0], s = code[1];
    const rl = r === 'T' ? '10' : r;
    const isCourt = r === 'J' || r === 'Q' || r === 'K';
    const isAce = r === 'A';
    const el = document.createElement('div');
    el.className = 'card face ' + (s === 'h' || s === 'd' ? 'red' : 'black') + (isCourt ? ' court' : '') + ' ' + size;
    el.dataset.code = code;
    const centerHtml = isCourt
      ? '<div class="court-frame"><span class="court-letter">' + rl + '</span>' + suitSVG(s) + '</div>'
      : '<div class="pip' + (isAce ? ' ace' : '') + '">' + suitSVG(s) + '</div>';
    el.innerHTML =
      '<div class="corner tl"><span class="rk">' + rl + '</span>' + suitSVG(s) + '</div>' +
      centerHtml +
      '<div class="corner br"><span class="rk">' + rl + '</span>' + suitSVG(s) + '</div>';
    return el;
  }

  function cardBack(size) {
    const el = document.createElement('div');
    el.className = 'card back ' + size;
    el.dataset.code = '??';
    return el;
  }

  const CHIP_COLORS = ['#E8E2D0', '#9E3A3A', '#26684E', '#252B29', '#B99A5E'];

  function chipStack(amount) {
    const n = Math.max(1, Math.min(4, 1 + Math.floor(Math.log10(Math.max(1, amount)) / 1.35)));
    const wrap = document.createElement('div');
    wrap.className = 'chips';
    for (let i = 0; i < n; i++) {
      const c = document.createElement('div');
      c.className = 'chip';
      c.style.setProperty('--c', CHIP_COLORS[(i + n) % CHIP_COLORS.length]);
      c.style.bottom = (i * 3) + 'px';
      wrap.appendChild(c);
    }
    return wrap;
  }

  const AVATAR_FILES = {
    human:   '/poker/static/avatars/avatar_0.jpg',
    'Баке':  '/poker/static/avatars/avatar_1.jpg',
    'Жаке':  '/poker/static/avatars/avatar_2.jpg',
    'Моля':  '/poker/static/avatars/avatar_3.jpg',
    'Тима':  '/poker/static/avatars/avatar_5.jpg',
    'Алтуна':'/poker/static/avatars/avatar_7.jpg',
    'Айдон': '/poker/static/avatars/avatar_8.jpg',
    'Абеке': '/poker/static/avatars/avatar_4.jpg',
    'Венди': '/poker/static/avatars/avatar_3.jpg',
  };

  function avatarSVG(nameOrPersona) {
    const src = AVATAR_FILES[nameOrPersona] || AVATAR_FILES.human;
    return '<img src="' + src + '" alt="" draggable="false" />';
  }

  const SPADE_MARK = '<svg viewBox="0 0 24 24" aria-hidden="true">' + SUITS.s + '</svg>';

  return { suitSVG, cardFace, cardBack, chipStack, avatarSVG, SPADE_MARK };
})();
