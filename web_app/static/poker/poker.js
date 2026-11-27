/* Poker Club — клиентская часть. Вся игровая логика на сервере: клиент только показывает состояние
   и отправляет выбранное действие. Деньги, карты и ходы ботов клиенту не подвластны. */
(function () {
  'use strict';
  const A = window.PokerAssets, AU = window.PokerAudio;
  const $ = (s, r) => (r || document).querySelector(s);
  const E = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html != null) e.innerHTML = html; return e; };
  const fmt = n => Math.round(n).toLocaleString('ru-RU').replace(/[\u00a0\u202f]/g, ' ');
  const clamp = (v, a, b) => Math.max(a, Math.min(b, v));

  // Координаты внутри сцены 1280×720 (поддержка 5-max и 9-max столов)
  const LAYOUTS = {
    5: {
      SEAT_POS: [[640, 586], [185, 415], [295, 138], [985, 138], [1095, 415]],
      CARDS_SIDE: ['above', 'right', 'right', 'left', 'left'],
      BET_POS: [[505, 462], [412, 395], [435, 220], [845, 220], [868, 395]],
      DEALER_POS: [[520, 590], [270, 455], [380, 175], [900, 175], [1010, 455]],
    },
    9: {
      SEAT_POS: [
        [640, 588], [290, 530], [136, 384], [176, 198], [445, 92],
        [835, 92], [1104, 198], [1144, 384], [990, 530],
      ],
      CARDS_SIDE: ['above', 'right', 'right', 'right', 'below', 'below', 'left', 'left', 'left'],
      BET_POS: [
        [510, 468], [360, 444], [306, 360], [346, 240], [495, 194],
        [785, 194], [934, 240], [974, 360], [920, 444],
      ],
      DEALER_POS: [
        [522, 588], [376, 514], [244, 384], [274, 210], [544, 134],
        [736, 134], [1006, 210], [1036, 384], [904, 514],
      ],
    },
  };
  let CUR_LAYOUT = LAYOUTS[5];
  const POT_POS = [640, 242], DECK = [640, 224];
  const CHIP_COLORS = ['#E8E2D0', '#9E3A3A', '#26684E', '#252B29', '#B99A5E'];
  const STREET_NAME = { preflop: 'Префлоп', flop: 'Флоп', turn: 'Тёрн', river: 'Ривер', complete: 'Раздача завершена', idle: '' };
  const TINTS = ['#1f6a4f', '#1d6048', '#1a5642', '#174B3A', '#143f31'];

  const S = { state: null, timer: null, leaveTimer: null, busy: false, lockUntil: 0, scale: 1, t: null,
              betValue: 0, betSeq: -1, panelKey: '', resultKey: '', justJoined: false, bankruptOpen: false, modalClose: null,
              preAction: null };

  /* ---------------------------------------------------------------- сеть */
  async function api(path, body) {
    const opt = body === undefined ? { method: 'GET' } :
      { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) };
    let res;
    try { res = await fetch('/api/poker/' + path, opt); } catch (e) { return { ok: false, error: 'Нет связи с локальным сервером' }; }
    let data = {};
    try { data = await res.json(); } catch (e) { /* пустой ответ */ }
    if (!res.ok && !data.error) data.error = 'Ошибка ' + res.status;
    return data;
  }
  async function call(path, body) {
    const d = await api(path, body);
    if (d.state) applyState(d.state);
    if (!d.ok && d.error) toast(d.error);
    return d;
  }

  /* ---------------------------------------------------------------- общие элементы */
  function fit() {
    const s = Math.max(0.5, Math.min(window.innerWidth / 1280, window.innerHeight / 720));
    S.scale = s;
    $('#stage').style.transform = 'translate(-50%, -50%) scale(' + s + ')';
  }
  let toastTimer = null;
  function toast(msg) {
    const t = $('#toast'); t.textContent = msg; t.classList.add('show');
    clearTimeout(toastTimer); toastTimer = setTimeout(() => t.classList.remove('show'), 3200);
  }
  function center(el) {
    const r = el.getBoundingClientRect(), st = $('#stage').getBoundingClientRect();
    return { x: (r.left + r.width / 2 - st.left) / S.scale, y: (r.top + r.height / 2 - st.top) / S.scale };
  }
  function closeModal() { $('#modalRoot').innerHTML = ''; S.modalClose = null; }
  function openModal(html, onMount, cls) {
    const root = $('#modalRoot'); root.innerHTML = '';
    const bd = E('div', 'backdrop'); const m = E('div', 'modal ' + (cls || ''), html);
    bd.appendChild(m); root.appendChild(bd);
    if (onMount) onMount(m);
    return m;
  }
  function flyChips(from, to, count) {
    const layer = $('#flyLayer');
    for (let k = 0; k < count; k++) {
      const c = E('div', 'fly'); c.style.setProperty('--c', CHIP_COLORS[k % CHIP_COLORS.length]);
      c.style.left = (from[0] + Math.random() * 16 - 8) + 'px'; c.style.top = (from[1] + Math.random() * 10 - 5) + 'px';
      layer.appendChild(c);
      const dx = to[0] - from[0] + Math.random() * 14 - 7, dy = to[1] - from[1] + Math.random() * 10 - 5;
      setTimeout(() => { c.style.transform = 'translate(' + dx + 'px,' + dy + 'px)'; c.style.opacity = '0.9'; }, 20 + k * 45);
      setTimeout(() => c.remove(), 720 + k * 45);
    }
  }
  function dealAnimate(card, delay) {
    const c = center(card);
    card.style.setProperty('--dx', (DECK[0] - c.x) + 'px'); card.style.setProperty('--dy', (DECK[1] - c.y) + 'px');
    card.style.animationDelay = delay + 'ms'; card.classList.add('dealing');
    setTimeout(() => AU.play('deal'), delay);
    setTimeout(() => { card.classList.remove('dealing'); card.style.animationDelay = ''; }, delay + 560);
  }
  const SOUND_ON = '<svg viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16 9c1.5 1.5 1.5 4.500 0 6M18.500 6.500c3 3 3 8 0 11"/></svg>';
  const SOUND_OFF = '<svg viewBox="0 0 24 24"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M17 9l5 6M22 9l-5 6"/></svg>';
  const MUSIC_ICON = '<svg viewBox="0 0 24 24"><path d="M9 18V5l12-2v13"/><circle cx="6" cy="18" r="3"/><circle cx="18" cy="16" r="3"/></svg>';
  function updateSoundIcon() { $('#btnSound').innerHTML = AU.isEnabled() ? SOUND_ON : SOUND_OFF; }
  function updateMusicIcon() {
    const b = $('#btnMusic');
    b.innerHTML = MUSIC_ICON;
    b.classList.toggle('active', AU.isMusicEnabled());
    b.title = AU.isMusicEnabled() ? 'Музыка за столом: вкл' : 'Музыка за столом: выкл';
  }

  /* ---------------------------------------------------------------- применение состояния */
  function showScreen(name) {
    $('#lobby').classList.toggle('hidden', name !== 'lobby');
    $('#table').classList.toggle('hidden', name !== 'table');
  }
  function applyState(st) {
    const prev = S.state; S.state = st;
    AU.setEnabled(st.profile.settings.sound); updateSoundIcon();
    $('#balanceValue').textContent = fmt(st.profile.balance);
    const sess = st.session;
    if (!sess) {
      clearTimeout(S.timer); clearTimeout(S.leaveTimer);
      if (S.t) { $('#table').innerHTML = ''; S.t = null; S.resultKey = ''; S.panelKey = ''; }
      showScreen('lobby'); renderLobby(st);
      if (st.profile.bankrupt && !S.bankruptOpen) openBankrupt();
      return;
    }
    S.bankruptOpen = false;
    if (S.modalClose === 'buyin') closeModal();
    showScreen('table');
    renderTable(prev && prev.session, sess);
    schedule();
  }

  /* ---------------------------------------------------------------- лобби */
  function renderLobby(st) {
    const wrap = $('#lobbyTables'); wrap.innerHTML = '';
    st.tables.forEach((t, idx) => {
      const c = E('div', 'tcard' + (t.available ? '' : ' locked'));
      const dots = [[46, 38], [116, 22], [186, 38], [46, 112], [116, 128], [186, 112]]
        .map((p, i) => '<span class="dot" style="left:' + (p[0] - 7) + 'px;top:' + (p[1] - 7) + 'px;' + (i === 4 ? 'background:#B99A5E' : '') + '"></span>').join('');
      c.innerHTML =
        '<div class="art"><div class="oval" style="--tint:' + TINTS[idx] + '"></div>' + dots + '<span class="lvl">УРОВЕНЬ ' + t.level + '</span></div>' +
        '<div class="body"><h2>' + t.name + '</h2><div class="tag">' + t.tagline + '</div>' +
        '<dl><dt>Блайнды</dt><dd class="money">' + fmt(t.sb) + ' / ' + fmt(t.bb) + '</dd>' +
        '<dt>Бай-ин</dt><dd class="money">' + fmt(t.min_buyin) + ' – ' + fmt(t.max_buyin) + '</dd>' +
        '<dt>Соперники</dt><dd>' + t.level_name + '</dd></dl></div>' +
        '<div class="status">' + (t.available ? 'ДОСТУПЕН' : 'Недостаточно средств') + '</div>';
      c.title = t.available ? '' : t.lock_reason;
      c.onclick = () => {
        AU.unlock(); AU.play('click');
        if (!t.available) { toast(t.lock_reason); return; }
        openBuyin(t);
      };
      wrap.appendChild(c);
    });
    const p = st.profile.stats;
    $('#lobbyFooter').innerHTML =
      '<div><span class="stat">Раздач:<b>' + p.hands + '</b></span><span class="stat">Побед:<b>' + p.wins + '</b></span>' +
      '<span class="stat">Поражений:<b>' + p.losses + '</b></span><span class="stat">Крупнейший банк:<b>' + fmt(p.biggest_pot) + '</b></span>' +
      '<span class="stat">Выиграно всего:<b>' + fmt(p.total_won) + '</b></span><span class="stat">Проиграно всего:<b>' + fmt(p.total_lost) + '</b></span></div>' +
      '<button class="linkbtn" id="btnRestart" type="button">Начать заново…</button>';
    $('#btnRestart').onclick = openRestartConfirm;
  }

  function openBuyin(t) {
    const bal = S.state.profile.balance, maxAllowed = Math.min(t.max_buyin, bal);
    const rec = clamp(Math.round((t.min_buyin + (t.max_buyin - t.min_buyin) * 0.4) / t.bb) * t.bb, t.min_buyin, maxAllowed);
    S.modalClose = 'buyin';
    openModal(
      '<h3>' + t.name + '</h3><p>Блайнды ' + fmt(t.sb) + ' / ' + fmt(t.bb) + ' · соперники: ' + t.level_name.toLowerCase() + '</p>' +
      '<div class="row"><span>Доступно на балансе</span><b>' + fmt(bal) + '</b></div>' +
      '<div class="row"><span>Бай-ин</span><b id="biValue">' + fmt(rec) + '</b></div>' +
      '<input id="biRange" type="range" min="' + t.min_buyin + '" max="' + maxAllowed + '" step="' + t.bb + '" value="' + rec + '">' +
      '<input id="biNum" type="number" min="' + t.min_buyin + '" max="' + maxAllowed + '" value="' + rec + '">' +
      '<div class="row"><span>Рекомендуем: ' + fmt(rec) + '</span><span>' + fmt(t.min_buyin) + ' – ' + fmt(maxAllowed) + '</span></div>' +
      '<div class="row"><span>Размер стола</span><div style="display:flex;gap:8px;">' +
      '<button class="qbtn" id="sz5" type="button" style="border-color:var(--brass);color:var(--text);">5 игроков</button>' +
      '<button class="qbtn" id="sz9" type="button">9 игроков</button></div></div>' +
      '<div class="btns"><button class="act" id="biCancel" type="button">Отмена</button><button class="act accent" id="biGo" type="button">Сесть за стол</button></div>',
      m => {
        let seatsCount = 5;
        const r = $('#biRange', m), n = $('#biNum', m), v = $('#biValue', m);
        const sz5 = $('#sz5', m), sz9 = $('#sz9', m);
        const setSz = k => {
          seatsCount = k;
          sz5.style.borderColor = k === 5 ? 'var(--brass)' : '';
          sz5.style.color = k === 5 ? 'var(--text)' : '';
          sz9.style.borderColor = k === 9 ? 'var(--brass)' : '';
          sz9.style.color = k === 9 ? 'var(--text)' : '';
        };
        sz5.onclick = () => setSz(5);
        sz9.onclick = () => setSz(9);
        const sync = x => { x = clamp(Math.round(Number(x) || t.min_buyin), t.min_buyin, maxAllowed); r.value = x; n.value = x; v.textContent = fmt(x); return x; };
        r.oninput = () => sync(r.value); n.onchange = () => sync(n.value);
        $('#biCancel', m).onclick = closeModal;
        $('#biGo', m).onclick = async ev => {
          const btn = ev.currentTarget; if (btn.disabled) return; btn.disabled = true;
          S.justJoined = true;
          const d = await call('join', { table_id: t.id, buyin: sync(n.value), seats: seatsCount });
          if (!d.ok) { btn.disabled = false; S.justJoined = false; }
        };
      });
  }

  function openRestartConfirm() {
    openModal('<h3>Начать заново?</h3><p>Текущий баланс и статистика будут удалены. Начать новую игру с капиталом 50 000?</p>' +
      '<div class="btns"><button class="act" id="rsNo" type="button">Отмена</button><button class="act danger" id="rsYes" type="button">Начать заново</button></div>',
      m => {
        $('#rsNo', m).onclick = () => { closeModal(); if (S.state && S.state.profile.bankrupt) { S.bankruptOpen = false; openBankrupt(); } };
        $('#rsYes', m).onclick = async ev => {
          ev.currentTarget.disabled = true; S.bankruptOpen = false;
          closeModal(); await call('reset', { confirm: true });
        };
      });
  }
  function openBankrupt() {
    S.bankruptOpen = true;
    openModal('<h3>Банк исчерпан</h3><p>На балансе ' + fmt(S.state.profile.balance) +
      '. Этого не хватает даже на самый дешёвый стол (от 1 000). Можно начать новую игру с капиталом 50 000.</p>' +
      '<div class="btns"><button class="act" id="bkExit" type="button">Выйти в Work Center</button><button class="act accent" id="bkNew" type="button">Начать заново</button></div>',
      m => {
        $('#bkExit', m).onclick = exitModule;
        $('#bkNew', m).onclick = () => { closeModal(); openRestartConfirm(); };
      }, 'alert');
  }
  function exitModule() {
    if (window.parent !== window) window.parent.postMessage({ type: 'poker:exit' }, '*');
    else window.location.href = '/';
  }

  /* ---------------------------------------------------------------- стол: каркас */
  function buildTable(seatCount) {
    CUR_LAYOUT = LAYOUTS[seatCount === 5 ? 5 : 9];
    const root = $('#table'); root.innerHTML = '';
    root.appendChild(E('div', 'rail')); const felt = E('div', 'rail'); felt.style.background = 'none'; felt.style.boxShadow = 'none';
    felt.appendChild(E('div', 'felt')); felt.firstChild.style.zIndex = 0; felt.querySelector('.felt').style.inset = '24px';
    felt.className = 'rail-felt'; felt.style.cssText = 'position:absolute;left:195px;top:122px;width:890px;height:396px;border-radius:50%;pointer-events:none';
    root.appendChild(felt);
    const T = { seatCount: seatCount === 5 ? 5 : 9, seats: [], slots: [], codes: [] };
    T.wm = E('div', 'wm'); root.appendChild(T.wm);
    T.pot = E('div', 'pot'); root.appendChild(T.pot);
    T.board = E('div', 'board');
    for (let k = 0; k < 5; k++) { const sl = E('div', 'slot'); T.board.appendChild(sl); T.slots.push(sl); }
    root.appendChild(T.board);
    T.tinfo = E('div', 'tinfo'); root.appendChild(T.tinfo);
    T.bets = [];
    for (let i = 0; i < T.seatCount; i++) {
      const b = E('div', 'bet'); b.style.left = CUR_LAYOUT.BET_POS[i][0] + 'px'; b.style.top = CUR_LAYOUT.BET_POS[i][1] + 'px'; b.style.display = 'none';
      root.appendChild(b); T.bets.push({ el: b, amount: 0 });
    }
    for (let i = 0; i < T.seatCount; i++) {
      const seat = E('div', 'seat s' + i); seat.style.left = CUR_LAYOUT.SEAT_POS[i][0] + 'px'; seat.style.top = CUR_LAYOUT.SEAT_POS[i][1] + 'px';
      seat.innerHTML = '<div class="capsule"></div><div class="avatar"></div><div class="info"><div class="role"></div><div class="nm"></div><div class="stk"></div></div>' +
        '<div class="atag"></div><div class="badge">ВА-БАНК</div><div class="hole ' + CUR_LAYOUT.CARDS_SIDE[i] + '"></div>';
      root.appendChild(seat);
      T.seats.push({ root: seat, avatar: $('.avatar', seat), role: $('.role', seat), nm: $('.nm', seat), stk: $('.stk', seat),
                     atag: $('.atag', seat), hole: $('.hole', seat), codes: [], persona: null });
    }
    T.dealer = E('div', 'dealer', 'D'); root.appendChild(T.dealer);
    T.hist = E('div', 'hist'); root.appendChild(T.hist);
    T.combo = E('div', 'combo-pill'); root.appendChild(T.combo);
    T.panel = E('div', 'panel'); root.appendChild(T.panel);
    S.t = T;
    return T;
  }

  /* ---------------------------------------------------------------- стол: отрисовка */
  function renderTable(prevS, s) {
    const sc = s.seats.length === 5 ? 5 : 9;
    const T = (S.t && S.t.seatCount === sc) ? S.t : buildTable(sc);
    const first = !prevS;
    const newHand = !prevS || prevS.hand_no !== s.hand_no || prevS.table.id !== s.table.id;
    const animate = !first || S.justJoined;
    if (newHand) {
      T.seats.forEach(r => { r.codes = []; r.hole.innerHTML = ''; });
      T.slots.forEach(sl => { sl.innerHTML = ''; sl.dataset.code = ''; });
      T.bets.forEach(b => { b.amount = 0; b.el.style.display = 'none'; });
      S.resultKey = ''; S.panelKey = ''; S.preAction = null;
      const old = $('.result', $('#table')); if (old) old.remove();
    }
    if (prevS && prevS.phase !== s.phase) {
      S.preAction = null;
    }
    if (S.preAction && S.preAction.mode === 'call_exact' && s.current_bet > S.preAction.lockedBet) {
      S.preAction = null;
      toast('Ставка выросла — выберите действие вручную');
    }
    T.wm.textContent = s.table.name;
    T.tinfo.textContent = s.table.name + '  ·  блайнды ' + fmt(s.table.sb) + ' / ' + fmt(s.table.bb) + '  ·  ' + (STREET_NAME[s.phase] || '');
    T.pot.innerHTML = '';
    T.pot.appendChild(A.chipStack(s.pot)); T.pot.appendChild(E('span', '', 'Банк')); T.pot.appendChild(E('b', '', fmt(s.pot)));

    const winners = new Set(s.phase === 'complete' && s.result ? s.result.winners.map(w => w.seat) : []);
    s.seats.forEach((sd, i) => updateSeat(i, sd, prevS && !newHand ? prevS.seats[i] : null, s, newHand && animate, winners.has(i), animate));

    // общие карты
    let nIdx = 0;
    for (let k = 0; k < 5; k++) {
      const code = s.board[k], sl = T.slots[k];
      if (code) {
        if (sl.dataset.code !== code) {
          sl.innerHTML = ''; const card = A.cardFace(code, 'md'); sl.appendChild(card); sl.dataset.code = code;
          if (animate) { card.classList.add('flipping'); card.style.animationDelay = (nIdx * 140) + 'ms'; setTimeout(() => AU.play('deal'), nIdx * 140); nIdx++; setTimeout(() => card.classList.remove('flipping'), 700 + nIdx * 140); }
        }
      } else if (sl.dataset.code) { sl.innerHTML = ''; sl.dataset.code = ''; }
    }

    // дилер
    T.dealer.style.left = CUR_LAYOUT.DEALER_POS[s.dealer][0] + 'px'; T.dealer.style.top = CUR_LAYOUT.DEALER_POS[s.dealer][1] + 'px';

    // сбор ставок и выплата
    if (prevS && !newHand && prevS.phase !== s.phase) {
      let any = false;
      prevS.seats.forEach((ps, i) => { if (ps.bet > 0) { flyChips(CUR_LAYOUT.BET_POS[i], POT_POS, 3); any = true; } });
      if (any) AU.play('chips');
      if (s.phase === 'complete') onComplete(s);
    } else if (first && s.phase === 'complete') { /* восстановление после перезагрузки — без анимации */ }

    // история и подсказка комбинации прямо на сукне под бордом
    T.hist.innerHTML = ''; s.log.slice(-3).forEach(t => T.hist.appendChild(E('div', '', t.replace(/</g, '&lt;'))));
    T.combo.innerHTML = s.hint ? s.hint + (s.draws && s.draws.length ? '<span>' + s.draws.join(' · ') + '</span>' : '') : '';

    renderResult(s);
    renderPanel(s);
    S.justJoined = false;
  }

  function updateSeat(i, sd, prevSd, s, dealNow, isWinner, animate) {
    const R = S.t.seats[i];
    const portraitKey = sd.is_human ? 'human' : sd.name;
    if (R.persona !== portraitKey) { R.persona = portraitKey; R.avatar.innerHTML = A.avatarSVG(portraitKey); }
    R.role.textContent = sd.is_human ? 'ИГРОК · ' + sd.position : sd.label + ' · ' + sd.position;
    R.nm.textContent = sd.name; R.stk.textContent = fmt(sd.stack);
    R.root.title = sd.trait || '';
    R.root.classList.toggle('active', s.to_act === i && s.phase !== 'complete');
    R.root.classList.toggle('folded', sd.folded);
    R.root.classList.toggle('allin', sd.all_in && !sd.folded);
    R.root.classList.toggle('winner', isWinner);
    R.atag.textContent = sd.folded ? 'Сброс' : (sd.last_action || '');

    // звуки действий
    if (prevSd && animate && sd.last_action && sd.last_action !== prevSd.last_action) {
      const a = sd.last_action;
      AU.play(a === 'Чек' ? 'check' : a === 'Сброс' ? 'fold' : 'chips');
    }
    if (prevSd && animate && sd.folded && !prevSd.folded) AU.play('fold');

    // ставка перед игроком
    const B = S.t.bets[i];
    if (sd.bet > 0) {
      B.el.style.display = 'flex'; B.el.innerHTML = '';
      B.el.appendChild(A.chipStack(sd.bet)); B.el.appendChild(E('span', '', fmt(sd.bet)));
      if (B.amount !== sd.bet && animate) { B.el.classList.remove('bump'); void B.el.offsetWidth; B.el.classList.add('bump'); }
      B.amount = sd.bet;
    } else { B.el.style.display = 'none'; B.amount = 0; }

    // карты
    const codes = sd.cards, prevCodes = R.codes; R.codes = codes.slice();
    const sz = i === 0 ? 'lg' : 'sm';
    const mk = c => (c === '??' ? A.cardBack(sz) : A.cardFace(c, sz));
    if (!codes.length) { R.hole.innerHTML = ''; return; }
    if (prevCodes.length !== codes.length) {
      R.hole.innerHTML = '';
      const sc = S.t.seatCount;
      const order = (i - (s.dealer + 1) + sc) % sc;
      codes.forEach((c, k) => {
        const w = E('div', 'cardwrap'); const card = mk(c); w.appendChild(card); R.hole.appendChild(w);
        if (dealNow) dealAnimate(card, (k * sc + order) * 65 + 40);
      });
    } else {
      codes.forEach((c, k) => {
        if (c !== prevCodes[k]) {
          const w = R.hole.children[k]; w.innerHTML = ''; const card = mk(c); w.appendChild(card);
          if (animate) { card.classList.add('flipping'); setTimeout(() => card.classList.remove('flipping'), 520); }
        }
      });
    }
  }

  function onComplete(s) {
    const res = s.result; if (!res) return;
    setTimeout(() => { res.winners.forEach(w => flyChips(POT_POS, CUR_LAYOUT.SEAT_POS[w.seat], 4)); AU.play('chips'); }, 650);
    if (res.net[0] > 0) setTimeout(() => AU.play('win'), 950);
    S.lockUntil = performance.now() + 1300;
    setTimeout(() => { if (S.state && S.state.session) renderPanel(S.state.session, true); }, 1350);
  }

  function renderResult(s) {
    const root = $('#table');
    if (s.phase !== 'complete' || !s.result) { const o = $('.result', root); if (o) o.remove(); S.resultKey = ''; return; }
    const key = s.table.id + ':' + s.hand_no;
    if (S.resultKey === key) return;
    S.resultKey = key;
    const res = s.result, net = res.net[0], human = s.seats[0];
    let title;
    if (human.folded && net < 0) title = 'Вы сбросили карты';
    else if (net > 0) title = 'Вы выиграли ' + fmt(net);
    else if (net < 0) title = 'Вы проиграли ' + fmt(-net);
    else title = 'Вы остались при своих';
    const lines = res.winners.map(w => '<div class="l">' + w.name + (w.hand ? ' — <span>' + w.hand + '</span>' : '') + ' &nbsp;+' + fmt(w.amount) + '</div>').join('');
    const el = E('div', 'result', '<div class="t">' + title + '</div>' + lines +
      (res.pots.length > 1 ? '<div class="l"><span>Побочных банков: ' + (res.pots.length - 1) + '</span></div>' : ''));
    const delay = S.state.session && S.t ? 700 : 0;
    el.style.animationDelay = delay + 'ms';
    root.appendChild(el);
    if (delay) { el.style.opacity = '0'; setTimeout(() => { el.style.opacity = ''; }, delay); }
  }

  /* ---------------------------------------------------------------- панель действий */
  function renderPanel(s, force) {
    const T = S.t; if (!T) return;
    const locked = performance.now() < S.lockUntil;
    const preKey = S.preAction ? S.preAction.mode + ':' + S.preAction.lockedBet : '';
    const key = [s.seq, s.phase, s.to_act, S.busy, locked, s.leave_requested, s.busted, preKey].join('|');
    if (!force && key === S.panelKey) return;
    S.panelKey = key;
    if (S.betSeq !== s.seq) { S.betSeq = s.seq; S.betValue = 0; }
    const P = T.panel; P.innerHTML = '';
    const left = E('div', 'left'), consoleEl = E('div', 'console');
    P.appendChild(left); P.appendChild(consoleEl);

    // выход со стола
    let leaveBtn;
    if (s.can_leave_now) { leaveBtn = E('button', 'ghost', 'Покинуть стол'); leaveBtn.onclick = () => { if (!S.busy) call('leave', {}); }; }
    else if (s.leave_requested) { leaveBtn = E('button', 'ghost', 'Отменить выход'); leaveBtn.onclick = () => call('cancel_leave', {}); }
    else { leaveBtn = E('button', 'ghost', 'Выйти после раздачи'); leaveBtn.onclick = () => call('leave', {}); }
    left.appendChild(leaveBtn);

    if (s.phase === 'complete') {
      const row = E('div', 'btnrow');
      if (s.busted || s.leave_requested) {
        consoleEl.appendChild(E('div', 'waiting', s.busted ? 'Фишки за столом закончились' : 'Выход из-за стола после этой раздачи…'));
        const b = E('button', 'act accent', 'К столам'); b.onclick = () => call('leave', {}); row.appendChild(b);
      } else {
        const b = E('button', 'act accent', 'Следующая раздача'); b.disabled = S.busy || locked;
        b.onclick = nextHand; row.appendChild(b);
      }
      consoleEl.appendChild(row);
      return;
    }

    const human = s.seats[0];
    if (s.to_act !== 0 || !s.legal) {
      const who = s.to_act == null ? null : s.seats[s.to_act].name;
      consoleEl.appendChild(E('div', 'waiting', who ? 'Ходит ' + who + '…' : (s.auto_runout ? 'Открываем карты…' : 'Раздача карт…')));
      if (s.to_act != null && !human.folded && !human.all_in && !s.auto_runout) {
        const row = E('div', 'btnrow');
        const cfSel = S.preAction && S.preAction.mode === 'check_fold';
        const cfBtn = E('button', 'act pre' + (cfSel ? ' selected' : ''), 'Чек / Сброс');
        cfBtn.onclick = () => {
          S.preAction = cfSel ? null : { mode: 'check_fold', lockedBet: s.current_bet };
          renderPanel(s, true);
        };
        row.appendChild(cfBtn);

        const callAmt = Math.min(s.to_call, human.stack);
        const ceSel = S.preAction && S.preAction.mode === 'call_exact';
        const ceLabel = callAmt > 0 ? 'Уравнять ' + fmt(callAmt) : 'Авто-чек';
        const ceBtn = E('button', 'act pre' + (ceSel ? ' selected' : ''), ceLabel);
        ceBtn.onclick = () => {
          S.preAction = ceSel ? null : { mode: 'call_exact', lockedBet: s.current_bet };
          renderPanel(s, true);
        };
        row.appendChild(ceBtn);
        consoleEl.appendChild(row);
      }
      return;
    }

    // Исполнение пред-действия, если очередь дошла до игрока
    if (S.preAction && !S.busy) {
      const pa = S.preAction;
      S.preAction = null;
      if (pa.mode === 'check_fold') {
        setTimeout(() => act(s.legal.check ? 'check' : 'fold'), 120);
        return;
      }
      if (pa.mode === 'call_exact' && s.current_bet === pa.lockedBet) {
        if (s.legal.check) { setTimeout(() => act('check'), 120); return; }
        if (s.legal.call != null) { setTimeout(() => act('call'), 120); return; }
      }
    }

    const L = s.legal, dis = S.busy || locked;
    const key2 = L.raise ? 'raise' : L.bet ? 'bet' : null;
    let raiseBtn = null;
    if (key2) {
      const [lo, hi] = L[key2], sb = s.table.sb;
      if (!S.betValue) S.betValue = lo;
      S.betValue = clamp(S.betValue, lo, hi);
      const sizing = E('div', 'sizing');
      const range = E('input'); range.type = 'range'; range.min = lo; range.max = hi; range.step = sb; range.value = S.betValue;
      const num = E('input'); num.type = 'number'; num.min = lo; num.max = hi; num.value = S.betValue;
      const frac = f => clamp(Math.round((key2 === 'bet' ? f * s.pot : s.current_bet + f * (s.pot + s.to_call)) / sb) * sb, lo, hi);
      const upd = v => { S.betValue = clamp(Math.round(Number(v) || lo), lo, hi); range.value = S.betValue; num.value = S.betValue;
        if (raiseBtn) raiseBtn.textContent = (key2 === 'bet' ? 'Ставка ' : 'Повысить до ') + fmt(S.betValue); };
      range.oninput = () => upd(range.value); num.onchange = () => upd(num.value);
      sizing.appendChild(range); sizing.appendChild(num);
      consoleEl.appendChild(sizing);

      const qg = E('div', 'qgroup');
      [['½', 0.5], ['¾', 0.75], ['Банк', 1]].forEach(([t, f]) => { const q = E('button', 'qbtn', t); q.onclick = () => upd(frac(f)); qg.appendChild(q); });
      const qa = E('button', 'qbtn', 'Ва-банк'); qa.onclick = () => upd(hi); qg.appendChild(qa);
      consoleEl.appendChild(qg);
    }
    const row = E('div', 'btnrow');
    if (L.fold) { const b = E('button', 'act danger', 'Сбросить'); b.disabled = dis; b.onclick = () => act('fold'); row.appendChild(b); }
    if (L.check) { const b = E('button', 'act', 'Чек'); b.disabled = dis; b.onclick = () => act('check'); row.appendChild(b); }
    if (L.call != null) { const b = E('button', 'act primary', 'Уравнять ' + fmt(L.call)); b.disabled = dis; b.onclick = () => act('call'); row.appendChild(b); }
    if (key2) {
      raiseBtn = E('button', 'act accent', (key2 === 'bet' ? 'Ставка ' : 'Повысить до ') + fmt(S.betValue)); raiseBtn.disabled = dis;
      raiseBtn.onclick = () => act(key2, S.betValue); row.appendChild(raiseBtn);
    }
    if (L.allin != null && !(L.call != null && L.call === L.allin)) {
      const b = E('button', 'act', 'Ва-банк ' + fmt(L.allin)); b.disabled = dis; b.onclick = () => act('allin'); row.appendChild(b);
    }
    consoleEl.appendChild(row);
  }

  async function act(action, amount) {
    if (S.busy || performance.now() < S.lockUntil) return;
    const s = S.state.session; if (!s) return;
    S.busy = true; renderPanel(s, true);
    AU.play(action === 'check' ? 'check' : action === 'fold' ? 'fold' : 'chips');
    try { await call('action', { seq: s.seq, action, amount }); }
    finally { S.busy = false; if (S.state && S.state.session) renderPanel(S.state.session, true); }
  }
  async function nextHand() {
    if (S.busy || performance.now() < S.lockUntil) return;
    const s = S.state && S.state.session; if (!s || s.phase !== 'complete') return;
    S.busy = true; renderPanel(s, true); AU.play('click');
    try { await call('next_hand', { seq: s.seq }); }
    finally { S.busy = false; if (S.state && S.state.session) renderPanel(S.state.session, true); }
  }

  /* ---------------------------------------------------------------- автопилот: ходы ботов и доигрывание */
  function schedule() {
    clearTimeout(S.timer); clearTimeout(S.leaveTimer);
    const s = S.state && S.state.session; if (!s) return;
    if (s.phase === 'complete') {
      if (s.leave_requested) S.leaveTimer = setTimeout(() => call('leave', {}), 2600);
      return;
    }
    if (s.to_act === 0) return;
    const delay = s.to_act == null ? 1100 : 650 + Math.random() * 450, seq = s.seq;
    S.timer = setTimeout(async () => {
      const d = await call('advance', { seq });
      if (!d.state) S.timer = setTimeout(schedule, 1500);
    }, delay);
  }

  /* ---------------------------------------------------------------- старт */
  $('#brandMark').innerHTML = A.SPADE_MARK;
  $('#btnBack').onclick = exitModule;
  const DECKS = [
    { cls: '', name: 'Обсидиан' },
    { cls: 'deck-navy', name: 'Сапфир' },
    { cls: 'deck-wine', name: 'Бордо' },
  ];
  let deckIdx = Number(localStorage.getItem('poker_deck_idx') || 0) % DECKS.length;
  function applyDeck() {
    document.body.classList.remove('deck-navy', 'deck-wine');
    if (DECKS[deckIdx].cls) document.body.classList.add(DECKS[deckIdx].cls);
    $('#btnDeck').textContent = 'Колода: ' + DECKS[deckIdx].name;
  }
  applyDeck();
  $('#btnDeck').onclick = () => {
    deckIdx = (deckIdx + 1) % DECKS.length;
    localStorage.setItem('poker_deck_idx', deckIdx);
    applyDeck();
    AU.play('click');
  };
  updateMusicIcon();
  $('#btnMusic').onclick = () => {
    AU.unlock();
    AU.setMusicEnabled(!AU.isMusicEnabled());
    updateMusicIcon();
  };
  $('#btnSound').onclick = async () => {
    AU.unlock(); const next = !AU.isEnabled(); AU.setEnabled(next); updateSoundIcon();
    if (next) AU.play('click');
    await call('settings', { sound: next });
  };
  window.addEventListener('resize', fit);
  window.addEventListener('keydown', e => {
    if ((e.code === 'Space' || e.code === 'Enter') && S.state && S.state.session && S.state.session.phase === 'complete' &&
        !(e.target && /INPUT|BUTTON/.test(e.target.tagName)) && !$('#modalRoot').firstChild) { e.preventDefault(); nextHand(); }
  });
  document.addEventListener('pointerdown', () => AU.unlock(), { once: true });
  fit();

  (async function init() {
    const d = await api('state');
    if (!d.state) { toast(d.error || 'Не удалось связаться с сервером'); return; }
    applyState(d.state);
    const q = new URLSearchParams(location.search);          // удобно для отладки: ?table=rookie&buyin=2000
    if (q.get('table') && !d.state.session) { S.justJoined = true; await call('join', { table_id: q.get('table'), buyin: Number(q.get('buyin')) }); }
  })();
})();
