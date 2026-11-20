/* BahonIQ Sports Hub — финальная версия (Этап 4: персонализация, доступность, производительность) */
(function () {
  'use strict';

  const FAVORITES_KEY = 'bahoniq_sports_favorites_v1';
  const SETTINGS_KEY = 'bahoniq_sports_settings_v1';
  const ANTHEM_ENABLED_KEY = 'bahoniq_sports_anthems_enabled_v1';
  const CLIENT_CACHE_TTL_MS = 120000;

  const DEFAULT_SETTINGS = {
    favoriteClub: 'real_madrid',
    favoriteF1Team: '',
    favoriteF1Driver: '',
    favoriteUfcFighter: '',
    overviewBlocks: { hero: true, clubs: true, f1_ufc: true, leaders: true, news: true },
    overviewOrder: ['hero', 'clubs', 'f1_ufc', 'leaders', 'news'],
    timeFormat: '24h',
    showCountdown: true,
    density: 'comfortable',
    animations: true,
    showImages: true,
    autoRefreshMinutes: 0,
  };

  let settings = loadSettings();
  let favorites = loadFavorites();
  let activeTab = 'real_madrid';
  let activeClub = settings.favoriteClub || 'real_madrid';
  let loadedOnce = false;
  let countdownTimer = null;
  let autoRefreshTimer = null;
  let activeAbortCtrl = null;
  let isFetching = false;
  let lastTriggerEl = null;
  let savedScrollY = 0;
  const memCache = new Map();

  const CLUB_ANTHEMS = {
    real_madrid: { title: 'Hala Madrid y nada más', src: '/assets/audio/real_madrid.mp3' },
    juventus: { title: 'Juve (storia di un grande amore)', src: '/assets/audio/juventus.mp3' },
    man_utd: { title: 'Glory Glory Man United', src: '/assets/audio/man_utd.mp3' },
  };

  function anthemEnabled() {
    return localStorage.getItem(ANTHEM_ENABLED_KEY) !== '0';
  }

  function stopClubAnthem(hide = true) {
    const audio = document.getElementById('sportsAnthemAudio');
    const bar = document.getElementById('sportsAnthemBar');
    if (audio) {
      audio.pause();
      audio.currentTime = 0;
    }
    if (hide) bar?.classList.add('hidden');
  }

  function playClubAnthem(clubId) {
    const anthem = CLUB_ANTHEMS[clubId];
    const audio = document.getElementById('sportsAnthemAudio');
    const bar = document.getElementById('sportsAnthemBar');
    const title = document.getElementById('sportsAnthemTitle');
    const toggle = document.getElementById('sportsAnthemToggle');
    if (!anthem || !audio || !bar || !anthemEnabled()) {
      stopClubAnthem(true);
      return;
    }
    if (!audio.src.endsWith(anthem.src)) {
      audio.src = anthem.src;
      audio.currentTime = 0;
    }
    if (title) title.textContent = anthem.title;
    bar.classList.remove('hidden');
    const attempt = audio.play();
    if (attempt && typeof attempt.catch === 'function') {
      attempt.then(() => { if (toggle) toggle.textContent = '⏸ Пауза'; })
        .catch(() => { if (toggle) toggle.textContent = '▶ Включить гимн'; });
    }
  }

  function cloneDefaults() {
    return JSON.parse(JSON.stringify(DEFAULT_SETTINGS));
  }

  function validateSettings(raw) {
    const base = cloneDefaults();
    if (!raw || typeof raw !== 'object') return base;
    if (['real_madrid', 'juventus', 'man_utd'].includes(raw.favoriteClub)) base.favoriteClub = raw.favoriteClub;
    if (typeof raw.favoriteF1Team === 'string') base.favoriteF1Team = raw.favoriteF1Team.slice(0, 80);
    if (typeof raw.favoriteF1Driver === 'string') base.favoriteF1Driver = raw.favoriteF1Driver.slice(0, 80);
    if (typeof raw.favoriteUfcFighter === 'string') base.favoriteUfcFighter = raw.favoriteUfcFighter.slice(0, 80);
    if (raw.overviewBlocks && typeof raw.overviewBlocks === 'object') {
      for (const k of Object.keys(base.overviewBlocks)) {
        if (typeof raw.overviewBlocks[k] === 'boolean') base.overviewBlocks[k] = raw.overviewBlocks[k];
      }
    }
    if (Array.isArray(raw.overviewOrder)) {
      const valid = raw.overviewOrder.filter(k => ['hero', 'clubs', 'f1_ufc', 'leaders', 'news'].includes(k));
      const missing = ['hero', 'clubs', 'f1_ufc', 'leaders', 'news'].filter(k => !valid.includes(k));
      base.overviewOrder = [...new Set([...valid, ...missing])];
    }
    if (raw.timeFormat === '12h' || raw.timeFormat === '24h') base.timeFormat = raw.timeFormat;
    if (typeof raw.showCountdown === 'boolean') base.showCountdown = raw.showCountdown;
    if (raw.density === 'compact' || raw.density === 'comfortable') base.density = raw.density;
    if (typeof raw.animations === 'boolean') base.animations = raw.animations;
    if (typeof raw.showImages === 'boolean') base.showImages = raw.showImages;
    if ([0, 2, 5, 15, 30].includes(Number(raw.autoRefreshMinutes))) base.autoRefreshMinutes = Number(raw.autoRefreshMinutes);
    return base;
  }

  function loadSettings() {
    try {
      const raw = localStorage.getItem(SETTINGS_KEY);
      return validateSettings(raw ? JSON.parse(raw) : null);
    } catch {
      return cloneDefaults();
    }
  }

  function saveSettings() {
    try {
      localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
    } catch {}
    applySettingsToShell();
    setupAutoRefresh();
  }

  function loadFavorites() {
    try {
      const raw = localStorage.getItem(FAVORITES_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(arr)) return [];
      const seen = new Set();
      return arr.filter(item => {
        if (!item || typeof item !== 'object' || !item.uid || seen.has(item.uid)) return false;
        seen.add(item.uid);
        return true;
      });
    } catch {
      return [];
    }
  }

  function saveFavorites() {
    try {
      localStorage.setItem(FAVORITES_KEY, JSON.stringify(favorites));
    } catch {}
    updateFavBadge();
  }

  function updateFavBadge() {
    const el = document.getElementById('sportsFavCount');
    if (el) el.textContent = String(favorites.length);
  }

  function isFavorite(type, id) {
    const uid = `${type}:${id}`;
    return favorites.some(f => f.uid === uid);
  }

  function toggleFavorite(item) {
    if (!item || !item.type || !item.id) return false;
    const uid = `${item.type}:${item.id}`;
    const idx = favorites.findIndex(f => f.uid === uid);
    if (idx >= 0) {
      favorites.splice(idx, 1);
      saveFavorites();
      return false;
    }
    favorites.unshift({
      uid,
      type: item.type,
      id: String(item.id),
      title: String(item.title || 'Без названия'),
      subtitle: String(item.subtitle || ''),
      clubId: item.clubId || '',
      url: item.url || '',
      savedAt: new Date().toISOString(),
    });
    saveFavorites();
    return true;
  }

  function favBtnHtml(type, id, title, subtitle = '', clubId = '', url = '') {
    const active = isFavorite(type, id);
    const payload = esc(JSON.stringify({ type, id: String(id), title, subtitle, clubId, url }));
    return `<button class="sports-fav-btn ${active ? 'active' : ''}" type="button" data-fav-payload="${payload}" aria-label="${active ? 'Убрать из избранного' : 'Добавить в избранное'}" title="${active ? 'Убрать из избранного' : 'В избранное'}">${active ? '★' : '☆'}</button>`;
  }

  function applySettingsToShell() {
    const shell = document.getElementById('sportsShell');
    if (!shell) return;
    shell.classList.toggle('compact', settings.density === 'compact');
    shell.classList.toggle('no-anim', !settings.animations);
    shell.classList.toggle('hide-images', !settings.showImages);
  }

  function esc(val) {
    return String(val ?? 'Нет данных')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  function formatDisplayTime(utcStr, fallbackLocal) {
    if (!utcStr) return fallbackLocal || 'Нет данных';
    const d = new Date(utcStr);
    if (Number.isNaN(d.getTime())) return fallbackLocal || 'Нет данных';
    try {
      return new Intl.DateTimeFormat('ru-RU', {
        timeZone: 'Asia/Qyzylorda',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: settings.timeFormat === '12h',
      }).format(d);
    } catch {
      return fallbackLocal || 'Нет данных';
    }
  }

  const newsStore = new Map();
  let newsFilterTopic = 'all';
  let newsFilterDate = 'all';
  let newsSearchQuery = '';
  let modalStack = [];
  let cachedNewsCenter = null;

  function renderRelatedEntitiesBtns(entities) {
    if (!Array.isArray(entities) || !entities.length) return '';
    return `
      <div class="sports-entity-chips">
        ${entities.map(ent => {
          if (ent.type === 'club') {
            return `<button class="sports-entity-btn" type="button" data-jump-tab="football" data-jump-club="${esc(ent.id)}">⚽ ${esc(ent.label)}</button>`;
          }
          if (ent.type === 'player') {
            return `<button class="sports-entity-btn" type="button" data-player-club="${esc(ent.club_id)}" data-player-id="${esc(ent.id)}">👤 ${esc(ent.label)}</button>`;
          }
          if (ent.type === 'f1_constructor') {
            return `<button class="sports-entity-btn" type="button" data-f1-constructor="${esc(ent.id)}">🏎️ ${esc(ent.label)}</button>`;
          }
          if (ent.type === 'f1_driver') {
            return `<button class="sports-entity-btn" type="button" data-f1-driver="${esc(ent.id)}">🏁 ${esc(ent.label)}</button>`;
          }
          if (ent.type === 'ufc_fighter') {
            return `<button class="sports-entity-btn" type="button" data-ufc-fighter-id="${esc(ent.id || '')}" data-ufc-fighter-name="${esc(ent.name || ent.label)}">🥊 ${esc(ent.label)}</button>`;
          }
          return '';
        }).join('')}
      </div>
    `;
  }

  function renderRelatedNewsForEntity(keywords, excludeId = '') {
    const kws = (keywords || []).filter(Boolean).map(k => String(k).toLowerCase());
    if (!kws.length) return '';
    const matches = [...newsStore.values()].filter(n => {
      if (String(n.id) === String(excludeId)) return false;
      const blob = `${n.title || ''} ${n.title_original || ''} ${n.summary || ''} ${n.related_entity || ''}`.toLowerCase();
      return kws.some(k => blob.includes(k));
    }).slice(0, 4);
    if (!matches.length) return '';
    return `
      <div class="sports-card">
        <h3><span>📰 Читайте также / Новости по теме</span></h3>
        <div class="sports-list">${matches.map(renderNewsRow).join('')}</div>
      </div>
    `;
  }

  function teamLogoHtml(logo, name, shortCode = '', accent = '#00e5ff', lg = false) {
    if (logo && settings.showImages) {
      return `<img class="sports-team-logo${lg ? ' lg' : ''}" src="${esc(logo)}" alt="${esc(name)}" loading="lazy" onerror="this.style.display='none'">`;
    }
    const code = shortCode || String(name || '?').slice(0, 3).toUpperCase();
    return `<span class="sports-f1-badge" style="background:${esc(accent)};">${esc(code)}</span>`;
  }

  function renderNewsRow(n) {
    if (!n) return '';
    newsStore.set(String(n.id), n);
    const dt = formatDisplayTime(n.published_utc, n.published_local);
    return `
      <div class="sports-list-item">
        <div class="sports-clickable" tabindex="0" role="button" data-news-id="${esc(n.id)}" style="min-width:0;flex:1;">
          <div style="font-weight:600;color:var(--text-main);">${esc(n.title)}</div>
          <div class="sports-sub">${esc(n.source)} · ${esc(n.related_entity || n.category_ru || '')} · ${esc(dt)}</div>
        </div>
        <div style="display:flex;align-items:center;gap:6px;">
          ${n.is_auto_translated ? '<span class="sports-badge">Автоперевод</span>' : ''}
          ${n.is_rumor ? '<span class="sports-badge rumor">Слух</span>' : ''}
          ${favBtnHtml('news', n.id, n.title, `${n.source} · ${dt}`, '', n.url)}
        </div>
      </div>
    `;
  }

  function openNewsModal(newsId, triggerEl) {
    const n = newsStore.get(String(newsId));
    if (!n) return;
    const dt = formatDisplayTime(n.published_utc, n.published_local);
    const entitiesHtml = renderRelatedEntitiesBtns(n.related_entities || []);
    const relatedByTopic = renderRelatedNewsForEntity(
      (n.topics || []).length ? n.topics.map(t => ({ real_madrid: 'real madrid', juventus: 'juventus', man_utd: 'manchester united', f1: 'formula 1', ufc: 'ufc' }[t] || t)) : [n.category_ru],
      n.id
    );
    openModal(n.title, `
      <div style="display:flex;flex-wrap:wrap;gap:8px;align-items:center;">
        <span class="sports-badge">${esc(n.category_ru || n.category || 'Новости')}</span>
        ${n.related_entity ? `<span class="sports-badge gold">${esc(n.related_entity)}</span>` : ''}
        ${n.is_rumor ? '<span class="sports-badge rumor">Слух / Пресса</span>' : ''}
        ${n.is_older_7d ? '<span class="sports-badge stale">Старше 7 дней</span>' : ''}
        ${n.is_auto_translated ? '<span class="sports-badge">Автоматический перевод</span>' : ''}
        <span class="sports-sub">${esc(n.source)} · ${esc(dt)}</span>
      </div>
      ${(n.image && settings.showImages) ? `<img class="sports-news-modal-img" src="${esc(n.image)}" alt="${esc(n.title)}" loading="lazy" onerror="this.style.display='none'">` : ''}
      <div class="sports-card">
        <div style="font-size:15.5px;line-height:1.65;">${esc(n.summary || 'Краткое содержание отсутствует в RSS-ленте.')}</div>
        ${n.neutral_digest ? `<div class="sports-sub" style="margin-top:10px;padding-top:10px;border-top:1px solid rgba(148,163,184,0.16);">${esc(n.neutral_digest)}</div>` : ''}
      </div>
      ${entitiesHtml ? `<div class="sports-card"><h3><span>🔗 Связанные профили и разделы</span></h3>${entitiesHtml}</div>` : ''}
      ${relatedByTopic}
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;">
        ${favBtnHtml('news', n.id, n.title, `${n.source} · ${dt}`, '', n.url)}
        ${n.url ? `<a class="sports-refresh-btn" style="text-decoration:none;" href="${esc(n.url)}" target="_blank" rel="noopener">Открыть оригинал ↗</a>` : ''}
      </div>
    `, triggerEl);
  }

  function avatarHtml(photo, name, badge = '') {
    if (photo && settings.showImages) {
      return `<img class="sports-avatar" src="${esc(photo)}" alt="${esc(name)}" loading="lazy" onerror="this.style.display='none'">`;
    }
    const initials = String(name || '?').split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase() || '?';
    return `<div class="sports-avatar-placeholder">${esc(badge || initials)}</div>`;
  }

  function setStatus(meta) {
    const el = document.getElementById('sportsUpdatedAt');
    if (!el) return;
    const ts = (meta && meta.updated_at_utc) ? formatDisplayTime(meta.updated_at_utc, meta.updated_at_local) : (meta?.updated_at_local || 'Нет данных');
    const staleTag = meta && meta.stale ? ' <span class="sports-badge stale">Кеш (офлайн/ошибка)</span>' : '';
    el.innerHTML = `Обновлено (Asia/Qyzylorda): <b>${esc(ts)}</b>${staleTag}`;
  }

  function renderSkeleton() {
    return `
      <div class="sports-grid">
        <div class="sports-skeleton"></div>
        <div class="sports-skeleton"></div>
        <div class="sports-skeleton"></div>
      </div>
    `;
  }

  function renderErrorState(msg) {
    return `
      <div class="sports-card">
        <h3><span>⚠️ Не удалось загрузить данные</span></h3>
        <div class="sports-sub">${esc(msg)}</div>
        <div><button id="sportsRetryBtn" class="sports-refresh-btn" type="button">↻ Повторить загрузку</button></div>
      </div>
    `;
  }

  function formatCountdown(utcStr) {
    if (!utcStr) return 'Нет данных';
    const targetMs = Date.parse(utcStr);
    if (Number.isNaN(targetMs)) return 'Нет данных';
    const diff = Math.floor((targetMs - Date.now()) / 1000);
    if (diff <= 0) return 'Уже началось / в эфире';
    const d = Math.floor(diff / 86400);
    const h = Math.floor((diff % 86400) / 3600);
    const m = Math.floor((diff % 3600) / 60);
    const s = diff % 60;
    return `${d > 0 ? d + 'д ' : ''}${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`;
  }

  function updateCountdowns() {
    document.querySelectorAll('[data-countdown-utc]').forEach(el => {
      el.textContent = formatCountdown(el.dataset.countdownUtc);
    });
  }

  function ensureCountdownTicker() {
    if (!settings.showCountdown) return;
    updateCountdowns();
    if (!countdownTimer) {
      countdownTimer = setInterval(updateCountdowns, 1000);
    }
  }

  function stopCountdownTicker() {
    if (countdownTimer) {
      clearInterval(countdownTimer);
      countdownTimer = null;
    }
  }

  function beginTabFetch() {
    if (activeAbortCtrl) {
      try { activeAbortCtrl.abort(); } catch {}
    }
    activeAbortCtrl = new AbortController();
    return activeAbortCtrl.signal;
  }

  async function apiGet(url, force = false, signal = null) {
    const cached = memCache.get(url);
    if (!force && cached && (Date.now() - cached.ts) < CLIENT_CACHE_TTL_MS) {
      return cached.data;
    }
    isFetching = true;
    try {
      const fullUrl = force ? (url.includes('?') ? `${url}&force=true` : `${url}?force=true`) : url;
      const res = await fetch(fullUrl, signal ? { signal } : {});
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      memCache.set(url, { ts: Date.now(), data });
      return data;
    } finally {
      isFetching = false;
    }
  }

  function updateModalBackBtn() {
    const backBtn = document.getElementById('sportsModalBackBtn');
    if (backBtn) backBtn.classList.toggle('hidden', modalStack.length === 0);
  }

  function openModal(title, bodyHtml, triggerEl = null, pushHistory = true) {
    const modal = document.getElementById('sportsDetailModal');
    const tEl = document.getElementById('sportsModalTitle');
    const bEl = document.getElementById('sportsModalBody');
    const card = modal?.querySelector('.sports-modal-card');
    if (!modal || !tEl || !bEl) return;
    const wasHidden = modal.classList.contains('hidden');
    if (triggerEl && !modal.contains(triggerEl)) {
      lastTriggerEl = triggerEl;
      modalStack = [];
    } else if (!wasHidden && pushHistory && triggerEl && modal.contains(triggerEl)) {
      modalStack.push({
        title: tEl.textContent,
        bodyHtml: bEl.innerHTML,
        scrollTop: card ? card.scrollTop : 0,
      });
    } else if (wasHidden) {
      const ae = document.activeElement;
      lastTriggerEl = (ae && !modal.contains(ae)) ? ae : null;
      modalStack = [];
    }
    if (wasHidden) {
      savedScrollY = window.scrollY || 0;
    }
    tEl.textContent = title;
    bEl.innerHTML = bodyHtml;
    modal.classList.remove('hidden');
    document.body.classList.add('sports-modal-open');
    if (card) card.scrollTop = 0;
    updateModalBackBtn();
    bindActionHandlers(bEl);
    document.getElementById('sportsModalClose')?.focus();
  }

  function goModalBack() {
    const prev = modalStack.pop();
    const modal = document.getElementById('sportsDetailModal');
    const tEl = document.getElementById('sportsModalTitle');
    const bEl = document.getElementById('sportsModalBody');
    const card = modal?.querySelector('.sports-modal-card');
    if (!prev || !tEl || !bEl) {
      updateModalBackBtn();
      return;
    }
    tEl.textContent = prev.title;
    bEl.innerHTML = prev.bodyHtml;
    updateModalBackBtn();
    bindActionHandlers(bEl);
    if (card) card.scrollTop = prev.scrollTop || 0;
  }

  function closeModal() {
    const modal = document.getElementById('sportsDetailModal');
    if (!modal || modal.classList.contains('hidden')) return;
    modalStack = [];
    updateModalBackBtn();
    modal.classList.add('hidden');
    document.body.classList.remove('sports-modal-open');
    window.scrollTo(0, savedScrollY);
    if (lastTriggerEl && typeof lastTriggerEl.focus === 'function') {
      lastTriggerEl.focus();
    }
    lastTriggerEl = null;
  }

  function renderMatchBlock(title, m, clubId) {
    if (!m) return `<div class="sports-sub">${esc(title)}: Нет данных</div>`;
    const score = (m.home_score !== null && m.home_score !== undefined) ? `${m.home_score} : ${m.away_score}` : 'vs';
    const dtText = formatDisplayTime(m.date_utc, m.date_local);
    const cdHtml = (settings.showCountdown && m.status === 'scheduled' && m.date_utc)
      ? `<div class="sports-countdown">⏱ <span data-countdown-utc="${esc(m.date_utc)}">...</span></div>`
      : '';
    return `
      <div class="sports-list-item sports-clickable" tabindex="0" role="button" data-match-club="${esc(clubId || m.club_id)}" data-match-id="${esc(m.id)}">
        <div style="min-width:0;flex:1;">
          <div class="sports-sub">${esc(title)} · ${esc(dtText)} · ${esc(m.status_label)}</div>
          <div class="sports-score-line">${esc(m.home_team)} ${score} ${esc(m.away_team)}</div>
          <div class="sports-sub">${esc(m.league)} · ${esc(m.venue)}</div>
        </div>
        <div style="display:flex;align-items:center;gap:6px;">
          ${cdHtml}
          ${favBtnHtml('match', m.id, `${m.home_team} ${score} ${m.away_team}`, `${dtText} · ${m.league}`, clubId || m.club_id)}
        </div>
      </div>
    `;
  }

  function buildFormationLines(starters, formationStr, reverseForBottom = false) {
    const nums = String(formationStr || '').split('-').map(x => parseInt(x, 10)).filter(n => n > 0);
    const pattern = nums.length ? [1, ...nums] : [1, 4, 3, 3];
    const lines = [];
    let cursor = 0;
    for (const count of pattern) {
      if (cursor >= starters.length) break;
      lines.push(starters.slice(cursor, cursor + count));
      cursor += count;
    }
    if (cursor < starters.length) {
      lines.push(starters.slice(cursor));
    }
    return reverseForBottom ? lines.slice().reverse() : lines;
  }

  function renderPitchPlayerNode(p, clubIdForLink, side = 'home') {
    const pips = [
      ...(p.goals > 0 ? [`<span class="sports-ev-pip goal" title="Гол">⚽${p.goals > 1 ? p.goals : ''}</span>`] : []),
      ...(p.yellow_cards > 0 ? [`<span class="sports-ev-pip yellow" title="Жёлтая карточка"></span>`] : []),
      ...(p.red_cards > 0 ? [`<span class="sports-ev-pip red" title="Красная карточка"></span>`] : []),
      ...(p.subbed_out ? [`<span class="sports-ev-pip sub" title="Заменён">↓</span>`] : []),
    ].join('');
    const avatar = (p.photo && settings.showImages)
      ? `<img class="sports-pitch-avatar" src="${esc(p.photo)}" alt="${esc(p.name)}" loading="lazy" onerror="this.outerHTML='<div class=\\'sports-pitch-avatar\\'>${esc(p.jersey)}</div>'">`
      : `<div class="sports-pitch-avatar">${esc(p.jersey)}</div>`;
    const attrs = (clubIdForLink && p.id) ? `data-player-club="${esc(clubIdForLink)}" data-player-id="${esc(p.id)}"` : '';
    return `
      <div class="sports-pitch-node ${side}" ${attrs} title="${esc(p.name)} (${esc(p.position)})">
        ${pips ? `<div class="sports-pitch-icons">${pips}</div>` : ''}
        ${avatar}
        <div class="sports-pitch-name">${esc(p.jersey)}. ${esc(p.short_name || p.name)}</div>
      </div>
    `;
  }

  async function openMatchDetail(clubId, eventId, triggerEl) {
    openModal('Загрузка матча...', renderSkeleton(), triggerEl);
    try {
      const res = await fetch(`/api/sports/football/${encodeURIComponent(clubId)}/match/${encodeURIComponent(eventId)}`);
      const payload = await res.json();
      const m = payload.match;
      if (!m) {
        openModal('Детали матча', '<div class="sports-sub">Нет данных по матчу</div>');
        return;
      }
      const score = (m.home_score !== null && m.home_score !== undefined) ? `${m.home_score} - ${m.away_score}` : 'vs';
      const homeKey = String(m.home_team || '').toLowerCase();
      const awayKey = String(m.away_team || '').toLowerCase();

      const formatTeamEvents = teamNameLow => {
        const gList = (m.goals || []).filter(g => String(g.team || '').toLowerCase() === teamNameLow);
        const rList = (m.cards || []).filter(c => c.is_red && String(c.team || '').toLowerCase() === teamNameLow);
        return [
          ...gList.map(g => `<div>⚽ <b>${esc(g.scorer || g.text)}</b> ${esc(g.clock)}${g.assist ? ` <span class="sports-sub">(${esc(g.assist)})</span>` : ''}</div>`),
          ...rList.map(c => `<div><span class="sports-ev-pip red" style="vertical-align:middle;margin-right:4px;"></span> <b>${esc(c.scorer || c.text)}</b> ${esc(c.clock)}</div>`),
        ].join('') || '<div class="sports-sub">—</div>';
      };

      const rosters = m.rosters || [];
      const isOurClubName = tName => {
        const low = String(tName || '').toLowerCase();
        if (clubId === 'real_madrid') return low.includes('real madrid');
        if (clubId === 'juventus') return low.includes('juventus');
        if (clubId === 'man_utd') return low.includes('manchester united');
        return false;
      };

      const pitchTopHdr = rosters.length >= 2 ? `
        <div class="sports-pitch-top">
          <div class="sports-pitch-team-hdr">
            ${teamLogoHtml(rosters[0].logo, rosters[0].team)}
            <span>${esc(rosters[0].team)}</span>
            <span class="sports-badge gold">${esc(rosters[0].formation)}</span>
          </div>
          <div class="sports-pitch-team-hdr">
            <span class="sports-badge gold">${esc(rosters[1].formation)}</span>
            <span>${esc(rosters[1].team)}</span>
            ${teamLogoHtml(rosters[1].logo, rosters[1].team)}
          </div>
        </div>
      ` : '';

      const lineupsHtml = rosters.length ? `
        <div class="sports-match-section">
          <h3>Стартовые составы</h3>
          <div class="sports-lineups-grid">
            ${rosters.slice(0, 2).map(r => {
              const linkCid = isOurClubName(r.team) ? clubId : '';
              return `<div class="sports-lineup-card">
                <div class="sports-lineup-head">${teamLogoHtml(r.logo, r.team)}<b>${esc(r.team)}</b><span class="sports-badge gold">${esc(r.formation || '—')}</span></div>
                <div class="sports-lineup-list">${(r.starters || []).map(p => `
                  <div class="sports-lineup-player" ${linkCid && p.id ? `data-player-club="${esc(linkCid)}" data-player-id="${esc(p.id)}"` : ''}>
                    ${p.photo && settings.showImages ? `<img src="${esc(p.photo)}" alt="${esc(p.name)}" loading="lazy">` : `<span class="sports-lineup-number">${esc(p.jersey)}</span>`}
                    <span><b>${esc(p.short_name || p.name)}</b><small>${esc(p.position || '')}</small></span>
                    <em>#${esc(p.jersey)}</em>
                  </div>`).join('') || '<div class="sports-sub">Состав появится ближе к матчу</div>'}</div>
              </div>`;
            }).join('')}
          </div>
        </div>` : '<div class="sports-sub">Стартовые составы появятся ближе к матчу</div>';

      const allSubsEvents = m.substitutions || [];
      const subsEventsHtml = rosters.length ? `
        <div class="sports-grid-2">
          ${rosters.slice(0, 2).map(r => {
            const tLow = String(r.team || '').toLowerCase();
            const evs = allSubsEvents.filter(s => String(s.team || '').toLowerCase() === tLow);
            const evLines = evs.map(s => `
              <div class="sports-list-item" style="padding:6px 10px;">
                <span><b>${esc(s.clock)}</b> <span style="color:#4ade80;">↑</span> ${esc(s.sub_in || s.text)}</span>
                ${s.sub_out ? `<span class="sports-sub"><span style="color:#f87171;">↓</span> ${esc(s.sub_out)}</span>` : ''}
              </div>
            `).join('');
            return `
              <div class="sports-card">
                <h3><span>🔄 Замены и запас: ${esc(r.team)}</span></h3>
                ${evLines ? `<div class="sports-list">${evLines}</div>` : ''}
                <div class="sports-sub" style="line-height:1.55;margin-top:6px;"><b>Запасные:</b> ${(r.subs || []).map(p => `#${esc(p.jersey)} ${esc(p.name)}`).join(', ') || 'Нет данных'}</div>
              </div>
            `;
          }).join('')}
        </div>
      ` : '';

      openModal(`${m.home_team} ${score} ${m.away_team}`, `
        <div class="sports-match-scoreboard">
          <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
            <span class="sports-sub">${esc(m.league)} · ${esc(formatDisplayTime(m.date_utc, m.date_local))} · ${esc(m.venue)}</span>
            <div style="display:flex;align-items:center;gap:8px;">
              <span class="sports-badge gold">${esc(m.status_label)}</span>
              ${favBtnHtml('match', m.id, `${m.home_team} ${score} ${m.away_team}`, `${formatDisplayTime(m.date_utc, m.date_local)} · ${m.league}`, clubId)}
            </div>
          </div>
          <div class="sports-match-teams-row">
            <div class="sports-match-team-col">
              ${teamLogoHtml(m.home_logo, m.home_team, '', '#fff', true)}
              <div style="font-weight:800;font-size:16px;">${esc(m.home_team)}</div>
            </div>
            <div class="sports-match-score-big">${esc(score)}</div>
            <div class="sports-match-team-col">
              ${teamLogoHtml(m.away_logo, m.away_team, '', '#fff', true)}
              <div style="font-weight:800;font-size:16px;">${esc(m.away_team)}</div>
            </div>
          </div>
          ${(m.goals?.length || m.cards?.some(c => c.is_red)) ? `
            <div class="sports-match-events-cols">
              <div>${formatTeamEvents(homeKey)}</div>
              <div style="text-align:right;">${formatTeamEvents(awayKey)}</div>
            </div>
          ` : ''}
        </div>
        ${lineupsHtml}
        ${subsEventsHtml}
      `);
    } catch (err) {
      openModal('Ошибка загрузки матча', `<div class="sports-sub">${esc(err.message)}</div>`);
    }
  }

  async function openFootballPlayer(clubId, playerId, triggerEl) {
    openModal('Загрузка профиля футболиста...', renderSkeleton(), triggerEl);
    try {
      const res = await fetch(`/api/sports/football/${encodeURIComponent(clubId)}/player/${encodeURIComponent(playerId)}`);
      const payload = await res.json();
      const p = payload.player;
      if (!p) {
        openModal('Профиль игрока', '<div class="sports-sub">Нет данных</div>');
        return;
      }
      const st = p.season_stats || {};
      const hasSeasonStats = [st.appearances, st.goals, st.assists, st.minutes].some(v => v && v !== 'Нет данных');
      const statsBlock = hasSeasonStats ? `
        <div class="sports-kv-grid">
          <div class="sports-kv-item"><small>Матчи (сезон)</small><b>${esc(st.appearances)}</b></div>
          <div class="sports-kv-item"><small>Голы</small><b>${esc(st.goals)}</b></div>
          <div class="sports-kv-item"><small>Передачи</small><b>${esc(st.assists)}</b></div>
          <div class="sports-kv-item"><small>Минуты</small><b>${esc(st.minutes)}</b></div>
          <div class="sports-kv-item"><small>ЖК / КК</small><b>${esc(st.yellow_cards)} / ${esc(st.red_cards)}</b></div>
        </div>
      ` : '';
      const nameParts = String(p.name || '').split(' ').filter(w => w.length >= 4);
      const relatedNewsHtml = renderRelatedNewsForEntity([p.name, ...nameParts, p.club]);
      openModal(`${p.name} (#${p.jersey})`, `
        <div class="sports-profile-hero">
          ${avatarHtml(p.photo, p.name, '#' + p.jersey)}
          <div style="flex:1;min-width:200px;">
            <div class="sports-score-line">${esc(p.name)} · #${esc(p.jersey)}</div>
            <div class="sports-sub">${esc(p.club)} · ${esc(p.position)}</div>
            <div class="sports-sub">Страна: ${esc(p.nationality)} · Возраст: ${esc(p.age)} (${esc(p.date_of_birth)}) · Рост: ${esc(p.height)}</div>
          </div>
          ${favBtnHtml('player', `${clubId}_${p.id}`, p.name, `${p.club} · ${p.position}`, clubId)}
        </div>
        <div class="sports-entity-chips">
          <button class="sports-entity-btn" type="button" data-jump-tab="football" data-jump-club="${esc(clubId)}">⚽ Матчи и состав ${esc(p.club)}</button>
        </div>
        ${statsBlock}
        <div class="sports-card">
          <h3><span>📖 Биография</span>${p.is_auto_translated ? '<span class="sports-badge">Автоматический перевод</span>' : ''}</h3>
          <div class="sports-sub" style="line-height:1.6;">${esc(p.bio)}</div>
          ${p.wiki_url ? `<div><a class="sports-news-link" href="${esc(p.wiki_url)}" target="_blank" rel="noopener">Источник: Wikipedia ↗</a></div>` : ''}
        </div>
        ${relatedNewsHtml}
      `);
    } catch (err) {
      openModal('Ошибка профиля', `<div class="sports-sub">${esc(err.message)}</div>`);
    }
  }

  async function openF1Round(roundNum, triggerEl) {
    openModal(`Formula 1 — Этап ${roundNum}`, renderSkeleton(), triggerEl);
    try {
      const res = await fetch(`/api/sports/f1/round/${encodeURIComponent(roundNum)}`);
      const payload = await res.json();
      const rd = payload.round || {};
      const raceRows = (rd.race_results || []).slice(0, 20).map(r => `<tr><td>${esc(r.pos)}</td><td>${esc(r.driver)}</td><td>${esc(r.team)}</td><td>${esc(r.time)}</td><td><b>${esc(r.points)}</b></td></tr>`).join('') || '<tr><td colspan="5">Нет данных</td></tr>';
      const qualRows = (rd.qualifying_results || []).slice(0, 20).map(q => `<tr><td>${esc(q.pos)}</td><td>${esc(q.driver)}</td><td>${esc(q.q1)}</td><td>${esc(q.q2)}</td><td><b>${esc(q.q3)}</b></td></tr>`).join('') || '<tr><td colspan="5">Нет данных</td></tr>';
      openModal(`${rd.race_name || 'Этап ' + roundNum}`, `
        <div style="display:flex;justify-content:flex-end;">
          ${favBtnHtml('f1_round', String(roundNum), rd.race_name || `Этап ${roundNum}`, `Formula 1 · Этап ${roundNum}`)}
        </div>
        <div class="sports-card"><h3><span>🏁 Результаты гонки</span></h3><div class="sports-table-wrap"><table class="sports-table"><thead><tr><th>#</th><th>Гонщик</th><th>Команда</th><th>Время/Статус</th><th>Очки</th></tr></thead><tbody>${raceRows}</tbody></table></div></div>
        <div class="sports-card"><h3><span>⏱ Квалификация</span></h3><div class="sports-table-wrap"><table class="sports-table"><thead><tr><th>#</th><th>Гонщик</th><th>Q1</th><th>Q2</th><th>Q3</th></tr></thead><tbody>${qualRows}</tbody></table></div></div>
      `);
    } catch (err) {
      openModal('Ошибка этапа F1', `<div class="sports-sub">${esc(err.message)}</div>`);
    }
  }

  async function openF1Driver(driverId, triggerEl) {
    openModal('Загрузка профиля гонщика F1...', renderSkeleton(), triggerEl);
    try {
      const res = await fetch(`/api/sports/f1/driver/${encodeURIComponent(driverId)}`);
      const payload = await res.json();
      const d = payload.driver || {};
      const cs = d.career_stats || {};
      const srHtml = (d.season_results || []).map(r => `<div class="sports-list-item"><span>Этап ${esc(r.round)}: ${esc(r.race_name)}</span><b>P${esc(r.position)} (${esc(r.points)} очк.)</b></div>`).join('') || '<div class="sports-sub">Нет данных</div>';
      openModal(d.name || driverId, `
        <div class="sports-profile-hero">
          ${avatarHtml(d.photo, d.name, '#' + (d.number || '?'))}
          <div style="flex:1;min-width:200px;">
            <div class="sports-score-line">${esc(d.name)} (#${esc(d.number)})</div>
            <div class="sports-sub">${esc(d.current_team)} · ${esc(d.nationality)} · ДР: ${esc(d.date_of_birth)}</div>
          </div>
          ${favBtnHtml('f1_driver', driverId, d.name || driverId, `${d.current_team} · #${d.number}`)}
        </div>
        <div class="sports-kv-grid">
          <div class="sports-kv-item"><small>Место (текущий сезон)</small><b>#${esc(d.season_pos)}</b></div>
          <div class="sports-kv-item"><small>Очки (текущий сезон)</small><b>${esc(d.season_points)}</b></div>
          <div class="sports-kv-item"><small>Старты (карьера)</small><b>${esc(cs.starts)}</b></div>
          <div class="sports-kv-item"><small>Победы / Подиумы</small><b>${esc(cs.wins)} / ${esc(cs.podiums)}</b></div>
          <div class="sports-kv-item"><small>Поулы / БК</small><b>${esc(cs.poles)} / ${esc(cs.fastest_laps)}</b></div>
        </div>
        <div class="sports-card"><h3><span>🏎️ Текущий сезон</span></h3><div class="sports-list">${srHtml}</div></div>
        <div class="sports-card">
          <h3><span>📖 Биография</span>${d.is_auto_translated ? '<span class="sports-badge">Автоматический перевод</span>' : ''}</h3>
          <div class="sports-sub" style="line-height:1.6;">${esc(d.bio)}</div>
          ${d.wiki_url ? `<div><a class="sports-news-link" href="${esc(d.wiki_url)}" target="_blank" rel="noopener">Источник: Wikipedia ↗</a></div>` : ''}
        </div>
        ${renderRelatedNewsForEntity([d.name, ...(String(d.name || '').split(' ').filter(w => w.length >= 4)), d.current_team])}
      `);
    } catch (err) {
      openModal('Ошибка профиля гонщика', `<div class="sports-sub">${esc(err.message)}</div>`);
    }
  }

  async function openF1Constructor(constructorId, triggerEl) {
    openModal('Загрузка профиля команды F1...', renderSkeleton(), triggerEl);
    try {
      const res = await fetch(`/api/sports/f1/constructor/${encodeURIComponent(constructorId)}`);
      const payload = await res.json();
      const c = payload.constructor || {};
      openModal(c.name || constructorId, `
        <div class="sports-profile-hero">
          ${avatarHtml(c.logo || c.photo, c.name, c.short || 'F1')}
          <div style="flex:1;min-width:200px;">
            <div class="sports-score-line">${esc(c.name)}</div>
            <div class="sports-sub">Страна: ${esc(c.nationality)} · База: ${esc(c.base)}</div>
            <div class="sports-sub">Руководитель: ${esc(c.team_chief)} · Силовая установка: ${esc(c.power_unit)}</div>
          </div>
          ${favBtnHtml('f1_constructor', constructorId, c.name || constructorId, `Кубок конструкторов #${c.season_pos}`)}
        </div>
        <div class="sports-kv-grid">
          <div class="sports-kv-item"><small>Позиция в Кубке</small><b>#${esc(c.season_pos)}</b></div>
          <div class="sports-kv-item"><small>Очки</small><b>${esc(c.season_points)}</b></div>
          <div class="sports-kv-item"><small>Победы</small><b>${esc(c.season_wins)}</b></div>
          <div class="sports-kv-item"><small>Гонщики</small><b>${(c.drivers || []).map(x => `${x.name} (#${x.number})`).join(', ') || 'Нет данных'}</b></div>
        </div>
        <div class="sports-card">
          <h3><span>📖 История команды</span>${c.is_auto_translated ? '<span class="sports-badge">Автоматический перевод</span>' : ''}</h3>
          <div class="sports-sub" style="line-height:1.6;">${esc(c.bio)}</div>
          ${c.wiki_url ? `<div><a class="sports-news-link" href="${esc(c.wiki_url)}" target="_blank" rel="noopener">Источник: Wikipedia ↗</a></div>` : ''}
        </div>
        ${renderRelatedNewsForEntity([c.name, 'formula 1'])}
      `);
    } catch (err) {
      openModal('Ошибка профиля команды', `<div class="sports-sub">${esc(err.message)}</div>`);
    }
  }

  async function openUfcFighter(fighterId, name, triggerEl) {
    openModal(`Загрузка профиля бойца ${name}...`, renderSkeleton(), triggerEl);
    try {
      const res = await fetch(`/api/sports/ufc/fighter?fighter_id=${encodeURIComponent(fighterId || '')}&name=${encodeURIComponent(name || '')}`);
      const payload = await res.json();
      const f = payload.fighter || {};
      openModal(f.name || name, `
        <div class="sports-profile-hero">
          ${avatarHtml(f.photo, f.name, 'UFC')}
          <div style="flex:1;min-width:200px;">
            <div class="sports-score-line">${esc(f.name)}</div>
            <div class="sports-sub">Прозвище: ${esc(f.nickname)} · Страна: ${esc(f.country)}</div>
            <div class="sports-sub">Категория: ${esc(f.weight_class)} · ${esc(f.champion_status)}</div>
          </div>
          ${favBtnHtml('ufc_fighter', fighterId || name, f.name || name, `${f.weight_class} · ${f.ranking_position}`)}
        </div>
        <div class="sports-kv-grid">
          <div class="sports-kv-item"><small>Рекорд</small><b>${esc(f.record)}</b></div>
          <div class="sports-kv-item"><small>Рейтинг</small><b>${esc(f.ranking_position)}</b></div>
          <div class="sports-kv-item"><small>Возраст</small><b>${esc(f.age)}</b></div>
          <div class="sports-kv-item"><small>Рост / Вес</small><b>${esc(f.height)} / ${esc(f.weight)}</b></div>
          <div class="sports-kv-item"><small>Размах рук</small><b>${esc(f.reach)}</b></div>
          <div class="sports-kv-item"><small>Стойка</small><b>${esc(f.stance)}</b></div>
        </div>
        <div class="sports-card">
          <h3><span>📖 Биография</span>${f.is_auto_translated ? '<span class="sports-badge">Автоматический перевод</span>' : ''}</h3>
          <div class="sports-sub" style="line-height:1.6;">${esc(f.bio)}</div>
          ${f.wiki_url ? `<div><a class="sports-news-link" href="${esc(f.wiki_url)}" target="_blank" rel="noopener">Источник: Wikipedia ↗</a></div>` : ''}
        </div>
        ${renderRelatedNewsForEntity([f.name, ...(String(f.name || '').split(' ').filter(w => w.length >= 4)), 'ufc'])}
      `);
    } catch (err) {
      openModal('Ошибка профиля бойца', `<div class="sports-sub">${esc(err.message)}</div>`);
    }
  }

  function bindActionHandlers(root) {
    if (!root) return;
    root.querySelectorAll('[data-fav-payload]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        try {
          const item = JSON.parse(btn.dataset.favPayload);
          const nowFav = toggleFavorite(item);
          btn.classList.toggle('active', nowFav);
          btn.textContent = nowFav ? '★' : '☆';
          btn.setAttribute('aria-label', nowFav ? 'Убрать из избранного' : 'Добавить в избранное');
          if (activeTab === 'favorites') renderFavorites();
        } catch {}
      });
    });

    root.querySelectorAll('[data-jump-tab]').forEach(btn => {
      btn.addEventListener('click', e => {
        e.stopPropagation();
        closeModal();
        if (btn.dataset.jumpTab === 'football' && btn.dataset.jumpClub) {
          activeClub = btn.dataset.jumpClub;
          activeTab = activeClub;
        } else {
          activeTab = btn.dataset.jumpTab;
          if (btn.dataset.jumpClub) activeClub = btn.dataset.jumpClub;
        }
        renderCurrentTab(false);
      });
    });

    root.querySelectorAll('[data-match-id]').forEach(el => {
      const open = e => { if (e && e.stopPropagation) e.stopPropagation(); openMatchDetail(el.dataset.matchClub, el.dataset.matchId, el); };
      el.addEventListener('click', open);
      el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
    });
    root.querySelectorAll('[data-player-id]').forEach(el => {
      const open = e => { if (e && e.stopPropagation) e.stopPropagation(); openFootballPlayer(el.dataset.playerClub, el.dataset.playerId, el); };
      el.addEventListener('click', open);
      el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
    });
    root.querySelectorAll('[data-f1-round]').forEach(el => {
      const open = e => { if (e && e.stopPropagation) e.stopPropagation(); openF1Round(el.dataset.f1Round, el); };
      el.addEventListener('click', open);
    });
    root.querySelectorAll('[data-f1-driver]').forEach(el => {
      const open = e => { if (e && e.stopPropagation) e.stopPropagation(); openF1Driver(el.dataset.f1Driver, el); };
      el.addEventListener('click', open);
    });
    root.querySelectorAll('[data-f1-constructor]').forEach(el => {
      const open = e => { if (e && e.stopPropagation) e.stopPropagation(); openF1Constructor(el.dataset.f1Constructor, el); };
      el.addEventListener('click', open);
    });
    root.querySelectorAll('[data-ufc-fighter-name]').forEach(el => {
      const open = e => { if (e && e.stopPropagation) e.stopPropagation(); openUfcFighter(el.dataset.ufcFighterId || '', el.dataset.ufcFighterName, el); };
      el.addEventListener('click', open);
    });
    root.querySelectorAll('[data-news-id]').forEach(el => {
      const open = () => openNewsModal(el.dataset.newsId, el);
      el.addEventListener('click', open);
      el.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(); } });
    });
  }

  async function renderOverview(force = false) {
    const body = document.getElementById('sportsContent');
    if (!body) return;
    body.innerHTML = renderSkeleton();
    const signal = beginTabFetch();
    try {
      const [data, f1Data, ufcData] = await Promise.all([
        apiGet('/api/sports/overview', force, signal),
        apiGet('/api/sports/f1', false, signal).catch(() => null),
        apiGet('/api/sports/ufc', false, signal).catch(() => null),
      ]);
      setStatus(data.meta);

      const favClubKey = settings.favoriteClub || 'real_madrid';
      const clubItems = Object.values(data.clubs || {}).sort((a, b) =>
        (a.club?.id === favClubKey ? -1 : b.club?.id === favClubKey ? 1 : 0)
      );
      const primaryClub = clubItems[0];
      const heroMatch = primaryClub?.next_match || primaryClub?.last_match;

      const blocksMap = {};

      if (settings.overviewBlocks.hero) {
        blocksMap.hero = heroMatch ? `
          <div class="sports-hero-banner">
            <div>
              <div class="sports-hero-eyebrow">★ Главное событие · ${esc(primaryClub.club?.name)}</div>
              <div class="sports-hero-title">${esc(heroMatch.home_team)} ${(heroMatch.home_score !== null && heroMatch.home_score !== undefined) ? `${heroMatch.home_score} : ${heroMatch.away_score}` : 'vs'} ${esc(heroMatch.away_team)}</div>
              <div class="sports-sub">${esc(formatDisplayTime(heroMatch.date_utc, heroMatch.date_local))} · ${esc(heroMatch.league)} · ${esc(heroMatch.venue)}</div>
            </div>
            <div class="sports-hero-actions">
              ${(settings.showCountdown && heroMatch.status === 'scheduled' && heroMatch.date_utc) ? `<span class="sports-countdown">⏱ <span data-countdown-utc="${esc(heroMatch.date_utc)}">...</span></span>` : ''}
              <button class="sports-refresh-btn" type="button" data-match-club="${esc(primaryClub.club?.id)}" data-match-id="${esc(heroMatch.id)}">Открыть матч →</button>
            </div>
          </div>
        ` : '';
      }

      if (settings.overviewBlocks.clubs) {
        const clubsHtml = clubItems.map(item => {
          const club = item.club || {};
          const formHtml = (item.form || []).map(f => `<span class="sports-form-chip ${esc(f)}">${esc(f)}</span>`).join('') || '<span class="sports-sub">Нет данных</span>';
          return `
            <div class="sports-card accent-${esc(club.id)}">
              <h3>
                <span>⚽ ${esc(club.name)}</span>
                <div style="display:flex;align-items:center;gap:6px;">
                  <span class="sports-badge">${esc(club.league_name)}</span>
                  ${favBtnHtml('club', club.id, club.name, club.league_name, club.id)}
                </div>
              </h3>
              ${renderMatchBlock('Следующий матч', item.next_match, club.id)}
              ${renderMatchBlock('Последний матч', item.last_match, club.id)}
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <div class="sports-form-row">${formHtml}</div>
                <button class="sports-refresh-btn" style="padding:5px 10px;font-size:12px;" type="button" data-jump-tab="football" data-jump-club="${esc(club.id)}">Клуб →</button>
              </div>
            </div>
          `;
        }).join('');
        blocksMap.clubs = `<div class="sports-grid">${clubsHtml}</div>`;
      }

      if (settings.overviewBlocks.f1_ufc) {
        const f1 = data.f1_next;
        const ufcEv = data.ufc_event;
        const ufcMain = data.ufc_main_event;
        const f1Card = f1 ? `
          <div class="sports-card accent-f1">
            <h3><span>🏎️ Formula 1 — Ближайший этап</span><span class="sports-badge gold">Этап ${esc(f1.round)}</span></h3>
            <div class="sports-score-line">${esc(f1.race_name)}</div>
            <div class="sports-sub">${esc(f1.circuit_name)} (${esc(f1.locality)}, ${esc(f1.country)})</div>
            <div class="sports-sub">Гонка: <b>${esc(formatDisplayTime(f1.date_utc, f1.date_local))}</b></div>
            <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;">
              ${(settings.showCountdown && f1.date_utc) ? `<span class="sports-countdown">⏱ <span data-countdown-utc="${esc(f1.date_utc)}">...</span></span>` : ''}
              <button class="sports-refresh-btn" style="padding:5px 10px;font-size:12px;" type="button" data-jump-tab="f1">Раздел F1 →</button>
            </div>
          </div>
        ` : '';
        const ufcCard = ufcEv ? `
          <div class="sports-card accent-ufc">
            <h3>
              <span>🥊 ${esc(ufcEv.name)}</span>
              <div style="display:flex;align-items:center;gap:6px;">
                <span class="sports-badge ${ufcEv.is_numbered ? 'gold' : ''}">${ufcEv.is_numbered ? 'Номерной UFC' : 'Fight Night'}</span>
                ${favBtnHtml('ufc_event', ufcEv.id || ufcEv.name, ufcEv.name, `${formatDisplayTime(ufcEv.date_utc, ufcEv.date_local)} · ${ufcEv.location}`)}
              </div>
            </h3>
            <div class="sports-sub">${esc(formatDisplayTime(ufcEv.date_utc, ufcEv.date_local))} · ${esc(ufcEv.location)}</div>
            ${ufcMain ? `<div class="sports-sub">Главный бой: <b>${esc(ufcMain.fighter_a)} vs ${esc(ufcMain.fighter_b)}</b></div>` : ''}
            <div style="display:flex;justify-content:space-between;align-items:center;gap:8px;flex-wrap:wrap;">
              ${(settings.showCountdown && ufcEv.date_utc) ? `<span class="sports-countdown">⏱ <span data-countdown-utc="${esc(ufcEv.date_utc)}">...</span></span>` : ''}
              <button class="sports-refresh-btn" style="padding:5px 10px;font-size:12px;" type="button" data-jump-tab="ufc">Кард UFC →</button>
            </div>
          </div>
        ` : '';
        blocksMap.f1_ufc = `<div class="sports-grid">${f1Card}${ufcCard}</div>`;
      }

      if (settings.overviewBlocks.leaders) {
        const topDrivers = ((f1Data && f1Data.drivers) || []).slice(0, 5).map(d =>
          `<div class="sports-list-item sports-clickable" data-f1-driver="${esc(d.driver_id)}"><span><b>#${esc(d.pos)} ${esc(d.name)}</b> (${esc(d.team)})</span><b>${esc(d.points)} очк.</b></div>`
        ).join('') || '<div class="sports-sub">Нет данных</div>';
        const topChamps = ((ufcData && ufcData.rankings) || []).filter(r => r.champion).slice(0, 5).map(r =>
          `<div class="sports-list-item sports-clickable" data-ufc-fighter-id="${esc(r.champion.id || '')}" data-ufc-fighter-name="${esc(r.champion.name)}"><span>${esc(r.name)}</span><b>${esc(r.champion.name)}</b></div>`
        ).join('') || '<div class="sports-sub">Нет данных</div>';
        blocksMap.leaders = `
          <div class="sports-grid">
            <div class="sports-card accent-f1"><h3><span>🏆 Лидеры Formula 1</span></h3><div class="sports-list">${topDrivers}</div></div>
            <div class="sports-card accent-ufc"><h3><span>👑 Действующие чемпионы UFC</span></h3><div class="sports-list">${topChamps}</div></div>
          </div>
        `;
      }

      body.innerHTML = settings.overviewOrder.filter(k => k !== 'news').map(k => blocksMap[k] || '').join('');
      bindActionHandlers(body);
      ensureCountdownTicker();
    } catch (err) {
      if (err.name === 'AbortError') return;
      body.innerHTML = renderErrorState(err.message);
      body.querySelector('#sportsRetryBtn')?.addEventListener('click', () => renderOverview(true));
    }
  }

  function renderPlayerCard(p) {
    const thumb = (p.photo && settings.showImages)
      ? `<img class="sports-player-thumb" src="${esc(p.photo)}" alt="${esc(p.name)}" onerror="this.style.display='none'">`
      : `<div class="sports-player-thumb-fallback">#${esc(p.jersey)}</div>`;
    return `
      <div class="sports-player-card" tabindex="0" role="button" data-player-club="${esc(activeClub)}" data-player-id="${esc(p.id)}">
        ${thumb}
        <div style="min-width:0;flex:1;">
          <div style="font-weight:700;font-size:13.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">#${esc(p.jersey)} ${esc(p.name)}</div>
          <div class="sports-sub">${esc(p.position)} · ${esc(p.nationality)}</div>
          <div class="sports-sub">Возраст: ${esc(p.age)}</div>
        </div>
        ${favBtnHtml('player', `${activeClub}_${p.id}`, p.name, `${p.club} · ${p.position}`, activeClub)}
      </div>
    `;
  }

  async function renderFootball(force = false) {
    const body = document.getElementById('sportsContent');
    if (!body) return;
    body.innerHTML = renderSkeleton();
    const signal = beginTabFetch();
    try {
      const data = await apiGet(`/api/sports/football/${encodeURIComponent(activeClub)}`, force, signal);
      setStatus(data.meta);

      const clubRow = (data.standings || []).find(r =>
        String(r.team_id) === String(data.club?.espn_id) ||
        String(r.team || '').toLowerCase().includes(String(data.club?.name || '').toLowerCase())
      );

      const formHtml = (data.form || []).map(f => `<span class="sports-form-chip ${esc(f)}">${esc(f)}</span>`).join('') || '<span class="sports-sub">Нет данных</span>';

      const standingsRows = (data.standings || []).map(r => {
        const isClub = clubRow && String(r.team) === String(clubRow.team);
        return `
          <tr class="${isClub ? 'sports-row-highlight' : ''}">
            <td>${esc(r.pos)}</td>
            <td><div style="display:flex;align-items:center;gap:8px;">${teamLogoHtml(r.logo, r.team)}<span>${esc(r.team)}</span></div></td>
            <td>${esc(r.played)}</td>
            <td>${esc(r.wins ?? '0')}</td>
            <td>${esc(r.draws ?? '0')}</td>
            <td>${esc(r.losses ?? '0')}</td>
            <td>${esc(r.goals || `${r.gf ?? 0}:${r.ga ?? 0}`)}</td>
            <td>${esc(r.gd)}</td>
            <td><b>${esc(r.points)}</b></td>
          </tr>
        `;
      }).join('') || '<tr><td colspan="9">Нет данных</td></tr>';

      const upcomingAll = data.upcoming_matches || [];
      const recentAll = data.recent_results || [];
      const upcomingHtml = upcomingAll.slice(0, 3).map(m => renderMatchBlock('Будущий матч', m, activeClub)).join('') || '<div class="sports-sub">Будущих матчей в текущем диапазоне не найдено</div>';
      const recentThreeHtml = recentAll.slice(0, 3).map(m => renderMatchBlock('Последний матч', m, activeClub)).join('') || '<div class="sports-sub">Нет завершённых матчей</div>';
      const seasonResultsHtml = (data.season_results || recentAll).map(m => renderMatchBlock('Результат сезона', m, activeClub)).join('') || '<div class="sports-sub">Нет результатов текущего сезона</div>';

      const grouped = data.roster_grouped || {};
      const playersAll = data.players || [];
      const gkList = grouped.gk || playersAll.filter(p => p.position_group === 'gk');
      const defList = grouped.def || playersAll.filter(p => p.position_group === 'def');
      const midList = grouped.mid || playersAll.filter(p => p.position_group === 'mid');
      const fwdList = grouped.fwd || playersAll.filter(p => p.position_group === 'fwd');
      const otherList = grouped.other || playersAll.filter(p => !['gk', 'def', 'mid', 'fwd'].includes(p.position_group));

      const renderPosGroup = (title, list) => list.length ? `
        <div style="display:flex;flex-direction:column;gap:8px;">
          <div class="sports-sub" style="font-weight:700;color:var(--text-main);">${esc(title)} (${list.length})</div>
          <div class="sports-roster-grid">${list.map(renderPlayerCard).join('')}</div>
        </div>
      ` : '';

      const coachText = (data.coaches || []).map(c => c.name).filter(Boolean).join(', ') || 'Нет данных';

      const confirmedInHtml = (data.transfers_confirmed_in || []).map(renderNewsRow).join('') || '<div class="sports-sub">Подтверждённых входящих переходов для выбранного клуба в RSS-ленте не найдено.</div>';
      const confirmedOutHtml = (data.transfers_confirmed_out || []).map(renderNewsRow).join('') || '<div class="sports-sub">Подтверждённых исходящих переходов для выбранного клуба в RSS-ленте не найдено.</div>';
      const rumorsHtml = (data.transfer_rumors || []).map(renderNewsRow).join('') || '<div class="sports-sub">Слухов, связанных именно с выбранным клубом, в текущей RSS-ленте нет.</div>';
      const clubNewsHtml = (data.news || []).map(renderNewsRow).join('') || '<div class="sports-sub">Свежих новостей по выбранному клубу в подключённой RSS-ленте сейчас нет.</div>';

      const injuriesHtml = (data.injuries || []).length
        ? data.injuries.map(i => `<div class="sports-list-item"><b>${esc(i.player)}</b><span class="sports-sub">${esc(i.status)}</span></div>`).join('')
        : '<div class="sports-sub">Нет данных о травмах/дисквалификациях</div>';

      body.innerHTML = `
        <div class="sports-stack">
          <!-- 1. Широкая клубная шапка -->
          <div class="sports-club-banner accent-${esc(activeClub)}">
            <div class="sports-club-banner-main">
              ${teamLogoHtml(data.club?.logo || clubRow?.logo, data.club?.name, '', data.club?.accent, true)}
              <div>
                <div class="sports-hero-title" style="margin:0;">${esc(data.club?.name)}</div>
                <div class="sports-sub">${esc(data.club?.league_name)} · ${esc(data.season || '')} · Тренер: <b>${esc(coachText)}</b></div>
              </div>
            </div>
            <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap;">
              ${clubRow ? `<span class="sports-badge gold">Место #${esc(clubRow.pos)} · ${esc(clubRow.points)} очк.</span>` : ''}
              ${!anthemEnabled() ? '<button id="sportsAnthemEnable" class="sports-refresh-btn" type="button">♫ Включить гимн клуба</button>' : ''}
              ${favBtnHtml('club', activeClub, data.club?.name, data.club?.league_name, activeClub)}
            </div>
          </div>

          <!-- 2. Последний и следующий матч -->
          <div class="sports-grid-2">
            <div class="sports-card">
              <h3><span>⏭ Следующий матч</span></h3>
              ${renderMatchBlock('Следующий матч', data.next_match, activeClub)}
            </div>
            <div class="sports-card">
              <h3><span>⏮ Последний матч</span></h3>
              ${renderMatchBlock('Последний матч', data.last_match, activeClub)}
            </div>
          </div>

          <!-- 3. Форма и ключевые показатели -->
          <div class="sports-card">
            <h3><span>📊 Форма и ключевые показатели</span><span class="sports-badge">${esc(data.standings_season || data.season || '')}</span></h3>
            <div style="display:flex;flex-wrap:wrap;gap:16px;align-items:center;justify-content:space-between;">
              <div style="display:flex;align-items:center;gap:10px;">
                <span class="sports-sub">Последние 5 матчей:</span>
                <div class="sports-form-row">${formHtml}</div>
              </div>
              ${clubRow ? `
                <div class="sports-kv-grid" style="flex:1;min-width:280px;">
                  <div class="sports-kv-item"><small>Игры</small><b>${esc(clubRow.played)}</b></div>
                  <div class="sports-kv-item"><small>Победы / Ничьи / Пор.</small><b>${esc(clubRow.wins)} / ${esc(clubRow.draws)} / ${esc(clubRow.losses)}</b></div>
                  <div class="sports-kv-item"><small>Мячи (РМ)</small><b>${esc(clubRow.goals)} (${esc(clubRow.gd)})</b></div>
                  <div class="sports-kv-item"><small>Очки</small><b>${esc(clubRow.points)}</b></div>
                </div>
              ` : ''}
            </div>
          </div>

          <!-- 3.5. Отдельный визуальный блок: Стадион (карусель со стрелками), реальная форма, Комната трофеев (реальные кубки) -->
          ${(() => {
            const cp = data.club_profile || {};
            const rec = cp.records || {};
            const trophies = cp.trophies || [];
            const totalTrophies = trophies.reduce((acc, t) => acc + (Number(t.count) || 0), 0);
            const clubLogoUrl = data.club?.logo || clubRow?.logo || '';
            const gallery = (cp.stadium_gallery && cp.stadium_gallery.length)
              ? cp.stadium_gallery
              : (cp.stadium_photo ? [{ url: cp.stadium_photo, caption: cp.stadium }] : []);

            const stadiumBlock = `
              <div class="sports-card">
                <h3><span>🏟 Стадион: ${esc(cp.stadium || 'Нет данных')}</span><span class="sports-badge">${esc(cp.stadium_city || data.club?.country || '')}</span></h3>
                <div class="sports-stadium-showcase">
                  ${(gallery.length && settings.showImages) ? `
                    <div class="sports-stadium-carousel" id="sportsStadiumCarousel">
                      <img id="sportsStadiumImg" class="sports-stadium-hero-photo" src="${esc(gallery[0].url)}" alt="${esc(cp.stadium)}" loading="lazy">
                      ${gallery.length > 1 ? `
                        <button id="sportsStadiumPrev" class="sports-carousel-btn prev" type="button" aria-label="Предыдущее фото стадиона">◀</button>
                        <button id="sportsStadiumNext" class="sports-carousel-btn next" type="button" aria-label="Следующее фото стадиона">▶</button>
                        <div id="sportsStadiumCounter" class="sports-carousel-counter">1 / ${gallery.length}</div>
                      ` : ''}
                    </div>
                  ` : '<div class="sports-sub">Фото стадиона недоступно</div>'}
                  <div class="sports-kv-grid">
                    <div class="sports-kv-item"><small>Название</small><b>${esc(cp.stadium || 'Нет данных')}</b></div>
                    <div class="sports-kv-item"><small>Вместимость</small><b>${esc(cp.stadium_capacity || 'Нет данных')}</b></div>
                    <div class="sports-kv-item"><small>Открыт</small><b>${esc(cp.stadium_opened || '—')}</b></div>
                    <div class="sports-kv-item"><small>Покрытие</small><b>${esc(cp.stadium_surface || 'Газон')}</b></div>
                  </div>
                </div>
              </div>
            `;

            const verifiedKits = cp.kits || [];

            const kitsBlock = `
              <div class="sports-card">
                <h3>
                  <span>👕 Форма сезона 2026/27</span>
                  <span class="sports-badge">Проверено по официальному магазину клуба</span>
                </h3>
                <div class="sports-verified-kits">
                  ${verifiedKits.map(k => `<div class="sports-verified-kit">
                    <div class="sports-shirt-shape ${esc(k.pattern || 'solid')}" style="--kit-primary:${esc(k.primary)};--kit-secondary:${esc(k.secondary)};"><span>${esc((data.club?.name || '').slice(0, 2))}</span></div>
                    <div><b>${esc(k.label)}</b><small>${esc(k.desc)}</small></div>
                  </div>`).join('') || '<div class="sports-sub">Описание формы временно недоступно</div>'}
                </div>
              </div>
            `;

            const museumBlock = trophies.length ? `
              <div class="sports-museum-hall">
                <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
                  <h3 style="margin:0;display:flex;align-items:center;gap:8px;">${teamLogoHtml(clubLogoUrl, data.club?.name)}<span>🏆 Комната трофеев — ${esc(data.club?.name)}</span></h3>
                  <span class="sports-badge gold">Всего главных трофеев: ${totalTrophies}</span>
                </div>
                <div class="sports-trophy-museum">
                  ${trophies.map(t => `
                    <div class="sports-trophy-case">
                      ${(t.img && settings.showImages)
                        ? `<img class="sports-trophy-real-img" src="${esc(t.img)}" alt="${esc(t.title)}" loading="lazy" onerror="this.outerHTML='<div class=\\'sports-trophy-icon\\'>${esc(t.icon || '🏆')}</div>'">`
                        : `<div class="sports-trophy-icon">${esc(t.icon || '🏆')}</div>`}
                      <div class="sports-trophy-count">${esc(t.count)}</div>
                      <div class="sports-trophy-title">${esc(t.title)}</div>
                      ${t.last ? `<div class="sports-trophy-last">Последний: ${esc(t.last)}</div>` : ''}
                    </div>
                  `).join('')}
                </div>
                <div class="sports-kv-grid">
                  <div class="sports-kv-item"><small>Рекордсмен по играм</small><b>${esc(rec.appearances || 'Нет данных')}</b></div>
                  <div class="sports-kv-item"><small>Лучший бомбардир в истории</small><b>${esc(rec.goals || 'Нет данных')}</b></div>
                </div>
              </div>
            ` : '';

            return `${stadiumBlock}${kitsBlock}${museumBlock}`;
          })()}

          <!-- 4. Полноценная турнирная таблица -->
          <div class="sports-card">
            <h3>
              <span>🏆 Турнирная таблица (${esc(data.standings_season || data.club?.league_name)})</span>
              <span class="sports-sub">Команд: ${(data.standings || []).length} · Обновлено: ${esc(data.standings_updated_local || data.meta?.updated_at_local || '')}</span>
            </h3>
            <div class="sports-table-wrap">
              <table class="sports-table">
                <thead><tr><th>#</th><th>Команда</th><th>И</th><th>В</th><th>Н</th><th>П</th><th>Мячи</th><th>РМ</th><th>О</th></tr></thead>
                <tbody>${standingsRows}</tbody>
              </table>
            </div>
          </div>

          <!-- 4.5. Статистика чемпионата: Бомбардиры + Ассистенты -->
          ${(() => {
            const ll = data.league_leaders || {};
            const scorers = ll.scorers || [];
            const assists = ll.assists || [];
            if (!scorers.length && !assists.length) return '';
            const renderLeaderTable = (items, colLabel) => items.length ? `
              <div class="sports-table-wrap">
                <table class="sports-table">
                  <colgroup>
                    <col style="width:28px;">
                    <col style="width:36%;">
                    <col>
                    <col style="width:34px;">
                    <col style="width:48px;">
                  </colgroup>
                  <thead><tr><th>#</th><th>Игрок</th><th>Клуб</th><th style="text-align:center;">И</th><th style="text-align:right;">${esc(colLabel)}</th></tr></thead>
                  <tbody>
                    ${items.map(it => `
                      <tr>
                        <td>${esc(it.rank)}</td>
                        <td title="${esc(it.name)}"><strong>${esc(it.name)}</strong></td>
                        <td class="sports-sub" title="${esc(it.team)}">${esc(it.team)}</td>
                        <td style="text-align:center;">${esc(it.matches)}</td>
                        <td style="text-align:right;"><b>${esc(it.value)}</b></td>
                      </tr>
                    `).join('')}
                  </tbody>
                </table>
              </div>
            ` : '<div class="sports-sub">Нет данных</div>';
            return `
              <div class="sports-grid-2">
                <div class="sports-card">
                  <h3><span>⚽ Бомбардиры (${esc(data.club?.league_name)})</span><span class="sports-badge">Топ-${scorers.length}</span></h3>
                  ${renderLeaderTable(scorers, 'Голы')}
                </div>
                <div class="sports-card">
                  <h3><span>🎯 Ассистенты (${esc(data.club?.league_name)})</span><span class="sports-badge">Топ-${assists.length}</span></h3>
                  ${renderLeaderTable(assists, 'Пасы')}
                </div>
              </div>
            `;
          })()}

          <!-- 5. Календарь и результаты (по 3 матча по умолчанию + полный список) -->
          <div class="sports-grid-2">
            <div class="sports-card">
              <h3><span>📅 Ближайшие 3 матча</span><span class="sports-badge">Показано ${Math.min(3, upcomingAll.length)} из ${upcomingAll.length}</span></h3>
              <div class="sports-list">${upcomingHtml}</div>
              ${upcomingAll.length > 3 ? `<details style="margin-top:8px;"><summary class="sports-sub" style="cursor:pointer;">Показать все будущие (${upcomingAll.length})</summary><div class="sports-list" style="margin-top:8px;">${upcomingAll.map(m => renderMatchBlock('Будущий матч', m, activeClub)).join('')}</div></details>` : ''}
            </div>
            <div class="sports-card">
              <h3><span>✅ Последние 3 матча</span><span class="sports-badge">Показано ${Math.min(3, recentAll.length)} из ${(data.season_results || recentAll).length}</span></h3>
              <div class="sports-list">${recentThreeHtml}</div>
              <details style="margin-top:8px;"><summary class="sports-sub" style="cursor:pointer;">Все результаты текущего сезона (${(data.season_results || recentAll).length})</summary><div class="sports-list" style="margin-top:8px;">${seasonResultsHtml}</div></details>
            </div>
          </div>

          <!-- 7. Травмы и дисквалификации -->
          <div class="sports-card">
            <h3><span>🩺 Травмы и дисквалификации</span></h3>
            <div class="sports-list">${injuriesHtml}</div>
          </div>
        </div>
      `;

      body.querySelectorAll('.sports-club-pill[data-club]').forEach(btn => {
        btn.addEventListener('click', () => {
          activeClub = btn.dataset.club;
          renderFootball(false);
        });
      });
      body.querySelector('#sportsAnthemEnable')?.addEventListener('click', () => {
        localStorage.setItem(ANTHEM_ENABLED_KEY, '1');
        playClubAnthem(activeClub);
        renderFootball(false);
      });

      const stGallery = (data.club_profile?.stadium_gallery || []).length
        ? data.club_profile.stadium_gallery
        : (data.club_profile?.stadium_photo ? [{ url: data.club_profile.stadium_photo }] : []);
      if (stGallery.length > 1) {
        let stIdx = 0;
        const stImg = body.querySelector('#sportsStadiumImg');
        const stCnt = body.querySelector('#sportsStadiumCounter');
        const showSlide = delta => {
          stIdx = (stIdx + delta + stGallery.length) % stGallery.length;
          if (stImg) stImg.src = stGallery[stIdx].url;
          if (stCnt) stCnt.textContent = `${stIdx + 1} / ${stGallery.length}`;
        };
        body.querySelector('#sportsStadiumPrev')?.addEventListener('click', () => showSlide(-1));
        body.querySelector('#sportsStadiumNext')?.addEventListener('click', () => showSlide(1));
      }

      bindActionHandlers(body);
      ensureCountdownTicker();
    } catch (err) {
      if (err.name === 'AbortError') return;
      body.innerHTML = renderErrorState(err.message);
      body.querySelector('#sportsRetryBtn')?.addEventListener('click', () => renderFootball(true));
    }
  }

  async function renderF1(force = false) {
    const body = document.getElementById('sportsContent');
    if (!body) return;
    body.innerHTML = renderSkeleton();
    const signal = beginTabFetch();
    try {
      const data = await apiGet('/api/sports/f1', force, signal);
      setStatus(data.meta);

      const nextRace = data.next_race;
      const sessionsHtml = (nextRace?.sessions || []).map(s => `
        <div class="sports-list-item"><span>${esc(s.name)}</span><b>${esc(formatDisplayTime(s.date_utc, s.date_local))}</b></div>
      `).join('') || '<div class="sports-sub">Нет данных</div>';

      const driversRows = (data.drivers || []).map(d => `
        <tr class="sports-clickable" data-f1-driver="${esc(d.driver_id)}">
          <td>${esc(d.pos)}</td>
          <td><b>${esc(d.name)}</b> (#${esc(d.number)})</td>
          <td><div style="display:flex;align-items:center;gap:6px;">${teamLogoHtml(d.team_logo, d.team, '', d.team_accent)}<span>${esc(d.team)}</span></div></td>
          <td><b>${esc(d.points)}</b></td>
        </tr>
      `).join('') || '<tr><td colspan="4">Нет данных</td></tr>';

      const conRows = (data.constructors || []).map(c => `
        <tr class="sports-clickable" data-f1-constructor="${esc(c.constructor_id)}">
          <td>${esc(c.pos)}</td>
          <td><div style="display:flex;align-items:center;gap:8px;">${teamLogoHtml(c.logo, c.name, c.short, c.accent)}<b>${esc(c.name)}</b></div></td>
          <td>${esc(c.wins)}</td>
          <td><b>${esc(c.points)}</b></td>
        </tr>
      `).join('') || '<tr><td colspan="4">Нет данных</td></tr>';

      const calHtml = (data.races || []).map(r => `
        <div class="sports-list-item ${r.status === 'finished' ? 'sports-clickable' : ''}" ${r.status === 'finished' ? `data-f1-round="${esc(r.round)}"` : ''}>
          <span><b>Этап ${esc(r.round)}: ${esc(r.race_name)}</b> (${esc(formatDisplayTime(r.date_utc, r.date_local))})</span>
          <div style="display:flex;align-items:center;gap:6px;">
            <span class="sports-badge ${r.status === 'finished' ? 'official' : 'gold'}">${r.status === 'finished' ? 'Результаты ↗' : 'Впереди'}</span>
            ${favBtnHtml('f1_round', String(r.round), r.race_name, `Formula 1 · Этап ${r.round}`)}
          </div>
        </div>
      `).join('') || '<div class="sports-sub">Нет данных</div>';

      const newsHtml = (data.news || []).slice(0, 10).map(renderNewsRow).join('') || '<div class="sports-sub">Нет новостей</div>';

      body.innerHTML = `
        <div class="sports-stack">
          <div class="sports-grid-2">
            <div class="sports-card accent-f1">
              <h3><span>🏎️ Следующий этап (${esc(data.season)})</span><span class="sports-badge gold">${nextRace ? 'Этап ' + esc(nextRace.round) : 'Межсезонье'}</span></h3>
              ${nextRace ? `
                <div class="sports-score-line">${esc(nextRace.race_name)}</div>
                <div class="sports-sub">${esc(nextRace.circuit_name)} · ${esc(nextRace.country)}</div>
                ${(settings.showCountdown && nextRace.date_utc) ? `<div class="sports-countdown">⏱ <span data-countdown-utc="${esc(nextRace.date_utc)}">...</span></div>` : ''}
                <div class="sports-list">${sessionsHtml}</div>
              ` : '<div class="sports-sub">Нет данных о следующем этапе</div>'}
            </div>
            <div class="sports-card">
              <h3><span>🏁 Кубок конструкторов</span><span class="sports-badge">${(data.constructors || []).length} команд</span></h3>
              <div class="sports-table-wrap"><table class="sports-table"><thead><tr><th>#</th><th>Команда</th><th>Победы</th><th>Очки</th></tr></thead><tbody>${conRows}</tbody></table></div>
            </div>
          </div>
          <div class="sports-card">
            <h3><span>🏆 Личный зачёт гонщиков (${esc(data.season)})</span><span class="sports-badge">${(data.drivers || []).length}</span></h3>
            <div class="sports-table-wrap"><table class="sports-table"><thead><tr><th>#</th><th>Гонщик</th><th>Команда</th><th>Очки</th></tr></thead><tbody>${driversRows}</tbody></table></div>
          </div>
          <div class="sports-card">
            <h3><span>📅 Календарь сезона F1</span><span class="sports-badge">${(data.races || []).length} этапов</span></h3>
            <div class="sports-list">${calHtml}</div>
          </div>
          <div class="sports-card"><h3><span>📰 Новости Formula 1</span><span class="sports-badge">На русском</span></h3><div class="sports-list">${newsHtml}</div></div>
        </div>
      `;
      bindActionHandlers(body);
      ensureCountdownTicker();
    } catch (err) {
      if (err.name === 'AbortError') return;
      body.innerHTML = renderErrorState(err.message);
      body.querySelector('#sportsRetryBtn')?.addEventListener('click', () => renderF1(true));
    }
  }

  async function renderUfc(force = false) {
    const body = document.getElementById('sportsContent');
    if (!body) return;
    body.innerHTML = renderSkeleton();
    const signal = beginTabFetch();
    try {
      const data = await apiGet('/api/sports/ufc', force, signal);
      setStatus(data.meta);

      const ev = data.event;
      const fightsHtml = (data.fights || []).map(f => {
        const badgeCls = f.status === 'canceled' ? 'canceled' : (f.status === 'postponed' ? 'stale' : (f.status === 'finished' ? 'official' : ''));
        const fightTime = f.date_utc ? formatDisplayTime(f.date_utc, f.date_local) : '';
        return `
          <div class="sports-list-item">
            <div>
              <b>
                <span class="sports-clickable" data-ufc-fighter-id="${esc(f.fighter_a_id)}" data-ufc-fighter-name="${esc(f.fighter_a)}">${esc(f.fighter_a)}</span> (${esc(f.record_a)})
                vs
                <span class="sports-clickable" data-ufc-fighter-id="${esc(f.fighter_b_id)}" data-ufc-fighter-name="${esc(f.fighter_b)}">${esc(f.fighter_b)}</span> (${esc(f.record_b)})
              </b>
              <div class="sports-sub">${esc(f.weight_class)}${fightTime ? ` · ${esc(fightTime)}` : ''} · ${esc(f.card_section)}</div>
            </div>
            <span class="sports-badge ${badgeCls}">${esc(f.status_label)}</span>
          </div>
        `;
      }).join('') || '<div class="sports-sub">Нет данных о боях</div>';

      const allDivs = data.rankings || [];
      const menDivs = allDivs.filter(d => d.gender !== 'women');
      const womenDivs = allDivs.filter(d => d.gender === 'women');

      const renderChampRow = div => {
        const ch = div.champion || {};
        const verified = Boolean(ch.verified);
        const champLabel = verified ? ch.name : 'Актуальный чемпион не подтверждён';
        const titleMeta = [
          ch.title_since ? `Титул с: ${ch.title_since}` : '',
          ch.title_defenses ? `Защиты: ${ch.title_defenses}` : '',
        ].filter(Boolean).join(' · ');
        return `
          <div class="sports-list-item">
            <div style="min-width:0;flex:1;">
              <div style="font-weight:600;">${esc(div.name)}</div>
              ${titleMeta ? `<div class="sports-sub">${esc(titleMeta)}</div>` : ''}
            </div>
            ${verified
              ? `<b class="sports-clickable" data-ufc-fighter-id="${esc(ch.id || '')}" data-ufc-fighter-name="${esc(ch.name)}">${esc(champLabel)}</b>`
              : `<span class="sports-badge stale">${esc(champLabel)}</span>`}
          </div>
        `;
      };

      const menChampsHtml = menDivs.map(renderChampRow).join('') || '<div class="sports-sub">Нет данных</div>';
      const womenChampsHtml = womenDivs.map(renderChampRow).join('') || '<div class="sports-sub">Нет данных</div>';

      const p4pHtml = (data.p4p || []).map(p => `
        <div class="sports-card">
          <h3><span>🏅 ${esc(p.name)}</span><span class="sports-badge">Отдельно от весовых категорий</span></h3>
          <div class="sports-sub" style="margin-bottom:8px;">#1: <b>${esc(p.leader)}</b></div>
          <div class="sports-list">
            ${(p.contenders || []).slice(0, 10).map(c => `<div class="sports-list-item"><span>#${esc(c.rank)} ${esc(c.name)}</span></div>`).join('') || '<div class="sports-sub">Нет данных</div>'}
          </div>
        </div>
      `).join('');

      const newsHtml = (data.news || []).slice(0, 10).map(renderNewsRow).join('') || '<div class="sports-sub">Нет новостей</div>';
      const freshBadge = data.rankings_freshness_verified
        ? `<span class="sports-badge official">Подтверждено (${esc(data.rankings_updated_local)})</span>`
        : '<span class="sports-badge stale">Свежесть не подтверждена</span>';

      body.innerHTML = `
        <div class="sports-stack">
          <div class="sports-card accent-ufc">
            <h3>
              <span>🥊 ${esc(ev?.name || 'Турнир UFC')}</span>
              <div style="display:flex;align-items:center;gap:6px;">
                <span class="sports-badge ${ev?.is_numbered ? 'gold' : ''}">${ev?.is_numbered ? 'Номерной UFC' : 'Fight Night'}</span>
                ${ev ? favBtnHtml('ufc_event', ev.id || ev.name, ev.name, `${formatDisplayTime(ev.date_utc, ev.date_local)} · ${ev.location}`) : ''}
              </div>
            </h3>
            <div class="sports-sub">Время (Asia/Qyzylorda): <b>${esc(formatDisplayTime(ev?.date_utc, ev?.date_local))}</b> · ${esc(ev?.location || 'Нет данных')}</div>
            ${ev?.date_utc ? `<div class="sports-sub">Исходное время (UTC): ${esc(ev.date_utc)}</div>` : ''}
            ${(settings.showCountdown && ev?.date_utc) ? `<div class="sports-countdown">⏱ <span data-countdown-utc="${esc(ev.date_utc)}">...</span></div>` : ''}
            <div class="sports-list">${fightsHtml}</div>
          </div>

          <div class="sports-grid-2">
            <div class="sports-card">
              <h3>
                <span>👑 Чемпионы UFC — Мужские категории</span>
                ${freshBadge}
              </h3>
              <div class="sports-list">${menChampsHtml}</div>
              ${data.rankings_source_url ? `<div style="margin-top:8px;"><a class="sports-news-link" href="${esc(data.rankings_source_url)}" target="_blank" rel="noopener">Источник: UFC.com Official Rankings ↗</a></div>` : ''}
            </div>
            <div class="sports-card">
              <h3>
                <span>👑 Чемпионы UFC — Женские категории</span>
                ${freshBadge}
              </h3>
              <div class="sports-list">${womenChampsHtml}</div>
            </div>
          </div>

          ${p4pHtml ? `<div class="sports-grid-2">${p4pHtml}</div>` : ''}

          <div class="sports-card"><h3><span>📰 Новости UFC</span><span class="sports-badge">На русском</span></h3><div class="sports-list">${newsHtml}</div></div>
        </div>
      `;
      bindActionHandlers(body);
      ensureCountdownTicker();
    } catch (err) {
      if (err.name === 'AbortError') return;
      body.innerHTML = renderErrorState(err.message);
      body.querySelector('#sportsRetryBtn')?.addEventListener('click', () => renderUfc(true));
    }
  }

  async function renderFavorites() {
    const body = document.getElementById('sportsContent');
    if (!body) return;
    if (favorites.length === 0) {
      body.innerHTML = `
        <div class="sports-card">
          <h3><span>★ Избранное пусто</span></h3>
          <div class="sports-sub">Нажимайте ☆ на карточках клубов, матчей, игроков, гонщиков, команд, бойцов или новостей, чтобы закрепить их здесь.</div>
        </div>
      `;
      return;
    }

    // Обновляем статус доступности через Sports API (мягкий background check, при сбое показываем сохранённую копию)
    let ov = null;
    try { ov = await apiGet('/api/sports/overview', false); } catch {}

    const typeLabels = {
      club: 'Клуб', player: 'Футболист', match: 'Матч',
      f1_driver: 'Гонщик F1', f1_constructor: 'Команда F1', f1_round: 'Этап F1',
      ufc_fighter: 'Боец UFC', ufc_event: 'Турнир UFC', news: 'Новость',
    };

    const cardsHtml = favorites.map(f => {
      const isUnavailable = (ov === null);
      let openAttr = '';
      if (f.type === 'club') openAttr = `data-jump-tab="football" data-jump-club="${esc(f.id)}"`;
      else if (f.type === 'match') openAttr = `data-match-club="${esc(f.clubId || 'real_madrid')}" data-match-id="${esc(f.id)}"`;
      else if (f.type === 'player') openAttr = `data-player-club="${esc(f.clubId || 'real_madrid')}" data-player-id="${esc(f.id.split('_').pop())}"`;
      else if (f.type === 'f1_driver') openAttr = `data-f1-driver="${esc(f.id)}"`;
      else if (f.type === 'f1_constructor') openAttr = `data-f1-constructor="${esc(f.id)}"`;
      else if (f.type === 'f1_round') openAttr = `data-f1-round="${esc(f.id)}"`;
      else if (f.type === 'ufc_fighter') openAttr = `data-ufc-fighter-id="${esc(/^\d+$/.test(f.id) ? f.id : '')}" data-ufc-fighter-name="${esc(f.title)}"`;

      return `
        <div class="sports-list-item ${openAttr ? 'sports-clickable' : ''}" ${openAttr}>
          <div style="min-width:0;flex:1;">
            <div>
              <span class="sports-badge">${esc(typeLabels[f.type] || f.type)}</span>
              ${isUnavailable ? '<span class="sports-badge stale">Сохранённая копия</span>' : ''}
              <b style="margin-left:6px;">${f.url ? `<a class="sports-news-link" href="${esc(f.url)}" target="_blank" rel="noopener">${esc(f.title)}</a>` : esc(f.title)}</b>
            </div>
            <div class="sports-sub">${esc(f.subtitle)}</div>
          </div>
          ${favBtnHtml(f.type, f.id, f.title, f.subtitle, f.clubId, f.url)}
        </div>
      `;
    }).join('');

    body.innerHTML = `
      <div class="sports-card">
        <h3>
          <span>★ Избранные объекты (${favorites.length})</span>
          <button id="sportsClearFavBtn" class="sports-danger-btn" type="button">Очистить всё</button>
        </h3>
        <div class="sports-list">${cardsHtml}</div>
      </div>
    `;

    bindActionHandlers(body);
    body.querySelector('#sportsClearFavBtn')?.addEventListener('click', () => {
      if (confirm('Очистить весь список избранного BahonIQ Sports?')) {
        favorites = [];
        saveFavorites();
        renderFavorites();
      }
    });
  }

  function renderSettings() {
    const body = document.getElementById('sportsContent');
    if (!body) return;
    body.innerHTML = `
      <div class="sports-settings-grid">
        <div class="sports-card">
          <h3><span>⭐ Предпочтения</span></h3>
          <div class="sports-setting-row">
            <span>Любимый футбольный клуб</span>
            <select id="setFavClub">
              <option value="real_madrid" ${settings.favoriteClub === 'real_madrid' ? 'selected' : ''}>Real Madrid</option>
              <option value="juventus" ${settings.favoriteClub === 'juventus' ? 'selected' : ''}>Juventus</option>
              <option value="man_utd" ${settings.favoriteClub === 'man_utd' ? 'selected' : ''}>Manchester United</option>
            </select>
          </div>
          <div class="sports-setting-row">
            <span>Любимая команда F1</span>
            <input id="setFavF1Team" type="text" value="${esc(settings.favoriteF1Team)}" placeholder="Например: Ferrari">
          </div>
          <div class="sports-setting-row">
            <span>Любимый гонщик F1</span>
            <input id="setFavF1Driver" type="text" value="${esc(settings.favoriteF1Driver)}" placeholder="Например: Max Verstappen">
          </div>
          <div class="sports-setting-row">
            <span>Любимый боец UFC</span>
            <input id="setFavUfc" type="text" value="${esc(settings.favoriteUfcFighter)}" placeholder="Например: Islam Makhachev">
          </div>
        </div>

        <div class="sports-card">
          <h3><span>🎛️ Отображение и время</span></h3>
          <div class="sports-setting-row">
            <span>Формат времени</span>
            <select id="setTimeFormat">
              <option value="24h" ${settings.timeFormat === '24h' ? 'selected' : ''}>24-часовой</option>
              <option value="12h" ${settings.timeFormat === '12h' ? 'selected' : ''}>12-часовой</option>
            </select>
          </div>
          <div class="sports-setting-row">
            <span>Плотность карточек</span>
            <select id="setDensity">
              <option value="comfortable" ${settings.density === 'comfortable' ? 'selected' : ''}>Комфортный</option>
              <option value="compact" ${settings.density === 'compact' ? 'selected' : ''}>Компактный</option>
            </select>
          </div>
          <div class="sports-setting-row">
            <span>Обратный отсчёт</span>
            <input id="setCountdown" type="checkbox" ${settings.showCountdown ? 'checked' : ''}>
          </div>
          <div class="sports-setting-row">
            <span>Анимации интерфейса</span>
            <input id="setAnimations" type="checkbox" ${settings.animations ? 'checked' : ''}>
          </div>
          <div class="sports-setting-row">
            <span>Показывать фотографии</span>
            <input id="setShowImages" type="checkbox" ${settings.showImages ? 'checked' : ''}>
          </div>
          <div class="sports-setting-row">
            <span>Автообновление</span>
            <select id="setAutoRefresh">
              <option value="0" ${settings.autoRefreshMinutes === 0 ? 'selected' : ''}>Выключено</option>
              <option value="2" ${settings.autoRefreshMinutes === 2 ? 'selected' : ''}>Каждые 2 мин</option>
              <option value="5" ${settings.autoRefreshMinutes === 5 ? 'selected' : ''}>Каждые 5 мин</option>
              <option value="15" ${settings.autoRefreshMinutes === 15 ? 'selected' : ''}>Каждые 15 мин</option>
              <option value="30" ${settings.autoRefreshMinutes === 30 ? 'selected' : ''}>Каждые 30 мин</option>
            </select>
          </div>
        </div>

        <div class="sports-card">
          <h3><span>🧩 Блоки главного обзора</span></h3>
          <div class="sports-setting-row"><span>Главное событие (Hero)</span><input data-block-key="hero" type="checkbox" ${settings.overviewBlocks.hero ? 'checked' : ''}></div>
          <div class="sports-setting-row"><span>Карточки 3 клубов</span><input data-block-key="clubs" type="checkbox" ${settings.overviewBlocks.clubs ? 'checked' : ''}></div>
          <div class="sports-setting-row"><span>Formula 1 и UFC</span><input data-block-key="f1_ufc" type="checkbox" ${settings.overviewBlocks.f1_ufc ? 'checked' : ''}></div>
          <div class="sports-setting-row"><span>Лидеры F1 и чемпионы UFC</span><input data-block-key="leaders" type="checkbox" ${settings.overviewBlocks.leaders ? 'checked' : ''}></div>
          <div class="sports-setting-row"><span>Свежие новости</span><input data-block-key="news" type="checkbox" ${settings.overviewBlocks.news ? 'checked' : ''}></div>
          <div style="margin-top:10px;">
            <button id="sportsResetSettingsBtn" class="sports-danger-btn" type="button">Сбросить настройки</button>
          </div>
        </div>
      </div>
    `;

    body.querySelector('#setFavClub')?.addEventListener('change', e => {
      settings.favoriteClub = e.target.value;
      activeClub = settings.favoriteClub;
      saveSettings();
    });
    body.querySelector('#setFavF1Team')?.addEventListener('input', e => { settings.favoriteF1Team = e.target.value; saveSettings(); });
    body.querySelector('#setFavF1Driver')?.addEventListener('input', e => { settings.favoriteF1Driver = e.target.value; saveSettings(); });
    body.querySelector('#setFavUfc')?.addEventListener('input', e => { settings.favoriteUfcFighter = e.target.value; saveSettings(); });
    body.querySelector('#setTimeFormat')?.addEventListener('change', e => { settings.timeFormat = e.target.value; saveSettings(); });
    body.querySelector('#setDensity')?.addEventListener('change', e => { settings.density = e.target.value; saveSettings(); });
    body.querySelector('#setCountdown')?.addEventListener('change', e => { settings.showCountdown = e.target.checked; saveSettings(); });
    body.querySelector('#setAnimations')?.addEventListener('change', e => { settings.animations = e.target.checked; saveSettings(); });
    body.querySelector('#setShowImages')?.addEventListener('change', e => { settings.showImages = e.target.checked; saveSettings(); });
    body.querySelector('#setAutoRefresh')?.addEventListener('change', e => { settings.autoRefreshMinutes = Number(e.target.value) || 0; saveSettings(); });
    body.querySelectorAll('[data-block-key]').forEach(chk => {
      chk.addEventListener('change', e => {
        settings.overviewBlocks[chk.dataset.blockKey] = e.target.checked;
        saveSettings();
      });
    });
    body.querySelector('#sportsResetSettingsBtn')?.addEventListener('click', () => {
      if (confirm('Восстановить стандартные настройки BahonIQ Sports?')) {
        settings = cloneDefaults();
        activeClub = settings.favoriteClub;
        saveSettings();
        renderSettings();
      }
    });
  }

  function setupAutoRefresh() {
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer);
      autoRefreshTimer = null;
    }
    if (!settings.autoRefreshMinutes || settings.autoRefreshMinutes <= 0) return;
    autoRefreshTimer = setInterval(() => {
      const modalOpen = !document.getElementById('sportsDetailModal')?.classList.contains('hidden');
      const sportsSection = document.getElementById('sports');
      const isActiveModule = sportsSection && sportsSection.classList.contains('active');
      if (document.visibilityState !== 'visible' || modalOpen || isFetching || !isActiveModule) return;
      if (['overview', 'football', 'f1', 'ufc', 'news'].includes(activeTab)) {
        renderCurrentTab(true);
      }
    }, settings.autoRefreshMinutes * 60 * 1000);
  }

  async function renderNewsCenter(force = false) {
    const body = document.getElementById('sportsContent');
    if (!body) return;
    body.innerHTML = renderSkeleton();
    const signal = beginTabFetch();
    try {
      const data = await apiGet('/api/sports/news', force, signal);
      cachedNewsCenter = data;
      setStatus(data.meta);

      const allItems = data.items || [];
      allItems.forEach(n => newsStore.set(String(n.id), n));

      const favNewsIds = new Set(favorites.filter(f => f.type === 'news').map(f => String(f.id)));
      const nowMs = Date.now();
      const filtered = allItems.filter(n => {
        if (newsFilterTopic === 'favorites') {
          if (!favNewsIds.has(String(n.id))) return false;
        } else if (newsFilterTopic === 'featured') {
          if (!n.is_featured) return false;
        } else if (newsFilterTopic !== 'all') {
          if (!(n.topics || []).includes(newsFilterTopic) && n.category !== newsFilterTopic) return false;
        }
        if (newsFilterDate === '24h' && n.published_utc) {
          const ms = Date.parse(n.published_utc);
          if (!Number.isNaN(ms) && (nowMs - ms) > 86400 * 1000) return false;
        } else if (newsFilterDate === '7d' && n.is_older_7d) {
          return false;
        }
        if (newsSearchQuery.trim()) {
          const q = newsSearchQuery.trim().toLowerCase();
          const blob = `${n.title || ''} ${n.summary || ''} ${n.source || ''} ${n.related_entity || ''}`.toLowerCase();
          if (!blob.includes(q)) return false;
        }
        return true;
      });

      const counts = data.counts || {};
      const filters = [
        ['all', `Все (${counts.all ?? allItems.length})`],
        ['f1', `Formula 1 (${counts.f1 ?? 0})`],
        ['ufc', `UFC (${counts.ufc ?? 0})`],
        ['featured', `Главные (${counts.featured ?? 0})`],
        ['favorites', `★ Избранные (${favNewsIds.size})`],
      ];

      const lead = filtered[0] || null;
      const featuredList = (data.featured || []).slice(0, 4);
      const trendingHtml = (data.trending || []).map(t => `
        <button class="sports-club-pill ${newsFilterTopic === t.topic ? 'active' : ''}" data-news-topic="${esc(t.topic)}" type="button">${esc(t.label)} · ${esc(t.count)}</button>
      `).join('');

      body.innerHTML = `
        <div class="sports-stack">
          <div class="sports-card">
            <h3>
              <span>📰 Новостной центр BahonIQ Sports</span>
              <span class="sports-badge official">Русский перевод · Автообновление</span>
            </h3>
            <div class="sports-news-toolbar">
              <input id="sportsNewsSearch" class="sports-news-search" type="search" placeholder="Поиск по новостям Formula 1 и UFC..." value="${esc(newsSearchQuery)}">
              <select id="sportsNewsDateFilter" class="sports-refresh-btn">
                <option value="all" ${newsFilterDate === 'all' ? 'selected' : ''}>Все даты</option>
                <option value="24h" ${newsFilterDate === '24h' ? 'selected' : ''}>За 24 часа</option>
                <option value="7d" ${newsFilterDate === '7d' ? 'selected' : ''}>За 7 дней</option>
              </select>
            </div>
            <div class="sports-club-pills" style="margin-top:4px;">
              ${filters.map(([k, lbl]) => `<button class="sports-club-pill ${newsFilterTopic === k ? 'active' : ''}" data-news-topic="${esc(k)}" type="button">${esc(lbl)}</button>`).join('')}
            </div>
          </div>

          ${lead ? `
            <div class="sports-news-hero" data-news-id="${esc(lead.id)}" tabindex="0" role="button">
              <div style="display:flex;flex-direction:column;gap:8px;justify-content:center;">
                <div style="display:flex;gap:8px;flex-wrap:wrap;align-items:center;">
                  <span class="sports-badge gold">Главная новость</span>
                  <span class="sports-badge">${esc(lead.category_ru)}</span>
                  ${lead.is_auto_translated ? '<span class="sports-badge">Автоматический перевод</span>' : ''}
                  ${lead.is_older_7d ? '<span class="sports-badge stale">Старше 7 дней</span>' : ''}
                </div>
                <div class="sports-hero-title" style="margin:0;">${esc(lead.title)}</div>
                <div class="sports-sub">${esc(lead.summary)}</div>
                <div class="sports-sub">${esc(lead.source)} · ${esc(formatDisplayTime(lead.published_utc, lead.published_local))} · ${esc(lead.related_entity)}</div>
              </div>
              <div style="display:flex;flex-direction:column;justify-content:space-between;gap:10px;">
                ${(lead.image && settings.showImages) ? `<img class="sports-news-modal-img" src="${esc(lead.image)}" alt="${esc(lead.title)}" loading="lazy" onerror="this.style.display='none'">` : `<div class="sports-sub">Источник: ${esc(lead.source)}</div>`}
                ${renderRelatedEntitiesBtns((lead.related_entities || []).slice(0, 4))}
              </div>
            </div>
          ` : ''}

          <div class="sports-grid-2">
            <div class="sports-card">
              <h3><span>🔥 Популярные темы</span></h3>
              <div class="sports-club-pills">${trendingHtml || '<span class="sports-sub">Нет тем</span>'}</div>
            </div>
            <div class="sports-card">
              <h3><span>⭐ Главные (свежие ≤ 7 дней)</span></h3>
              <div class="sports-list">${featuredList.map(renderNewsRow).join('') || '<div class="sports-sub">Нет материалов</div>'}</div>
            </div>
          </div>

          <div class="sports-card">
            <h3><span>🕒 Последние новости</span><span class="sports-badge">${filtered.length}</span></h3>
            <div class="sports-list">${filtered.map(renderNewsRow).join('') || '<div class="sports-sub">По выбранному фильтру новостей не найдено</div>'}</div>
          </div>
        </div>
      `;

      body.querySelectorAll('[data-news-topic]').forEach(btn => {
        btn.addEventListener('click', () => {
          newsFilterTopic = btn.dataset.newsTopic;
          renderNewsCenter(false);
        });
      });
      body.querySelector('#sportsNewsDateFilter')?.addEventListener('change', e => {
        newsFilterDate = e.target.value;
        renderNewsCenter(false);
      });
      body.querySelector('#sportsNewsSearch')?.addEventListener('input', e => {
        newsSearchQuery = e.target.value;
        // Перерисовываем при небольшом вводе
        clearTimeout(body._searchT);
        body._searchT = setTimeout(() => renderNewsCenter(false), 180);
      });
      bindActionHandlers(body);
    } catch (err) {
      if (err.name === 'AbortError') return;
      body.innerHTML = renderErrorState(err.message);
      body.querySelector('#sportsRetryBtn')?.addEventListener('click', () => renderNewsCenter(true));
    }
  }

  async function renderCurrentTab(force = false) {
    document.querySelectorAll('#sportsTabs .sports-tab').forEach(btn => {
      const active = btn.dataset.sportTab === activeTab;
      btn.classList.toggle('active', active);
      btn.setAttribute('aria-selected', active ? 'true' : 'false');
    });
    if (['real_madrid', 'juventus', 'man_utd'].includes(activeTab)) {
      activeClub = activeTab;
      playClubAnthem(activeClub);
      return renderFootball(force);
    }
    stopClubAnthem(true);
    if (activeTab === 'f1') return renderF1(force);
    if (activeTab === 'ufc') return renderUfc(force);
    if (activeTab === 'news') return renderNewsCenter(force);
    if (activeTab === 'favorites') return renderFavorites();
    if (activeTab === 'settings') return renderSettings();
  }

  window.loadSportsHub = function () {
    settings = loadSettings();
    favorites = loadFavorites();
    applySettingsToShell();
    updateFavBadge();

    if (!loadedOnce) {
      loadedOnce = true;
      const tabsEl = document.getElementById('sportsTabs');
      const tabBtns = tabsEl ? [...tabsEl.querySelectorAll('.sports-tab')] : [];
      tabBtns.forEach((btn, idx) => {
        btn.addEventListener('click', () => {
          activeTab = btn.dataset.sportTab || 'real_madrid';
          renderCurrentTab(false);
        });
        btn.addEventListener('keydown', e => {
          if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
            e.preventDefault();
            const nextIdx = e.key === 'ArrowRight' ? (idx + 1) % tabBtns.length : (idx - 1 + tabBtns.length) % tabBtns.length;
            tabBtns[nextIdx].focus();
            tabBtns[nextIdx].click();
          }
        });
      });

      document.getElementById('sportsRefreshBtn')?.addEventListener('click', () => renderCurrentTab(true));
      document.getElementById('sportsAnthemToggle')?.addEventListener('click', () => {
        const audio = document.getElementById('sportsAnthemAudio');
        const btn = document.getElementById('sportsAnthemToggle');
        if (!audio) return;
        if (audio.paused) {
          audio.play().then(() => { if (btn) btn.textContent = '⏸ Пауза'; }).catch(() => {});
        } else {
          audio.pause();
          if (btn) btn.textContent = '▶ Продолжить';
        }
      });
      document.getElementById('sportsAnthemDisable')?.addEventListener('click', () => {
        localStorage.setItem(ANTHEM_ENABLED_KEY, '0');
        stopClubAnthem(true);
      });
      document.getElementById('sportsModalBackBtn')?.addEventListener('click', goModalBack);
      document.getElementById('sportsModalClose')?.addEventListener('click', closeModal);
      document.getElementById('sportsDetailModal')?.addEventListener('click', e => {
        if (e.target.id === 'sportsDetailModal') closeModal();
      });
      window.addEventListener('keydown', e => { if (e.key === 'Escape') closeModal(); });
    }
    setupAutoRefresh();
    renderCurrentTab(false);
  };

  window.unloadSportsHub = function () {
    stopCountdownTicker();
    if (autoRefreshTimer) {
      clearInterval(autoRefreshTimer);
      autoRefreshTimer = null;
    }
    if (activeAbortCtrl) {
      try { activeAbortCtrl.abort(); } catch {}
      activeAbortCtrl = null;
    }
    stopClubAnthem(true);
    closeModal();
  };

  const initialSportsSec = document.getElementById('sports');
  if (initialSportsSec && (initialSportsSec.classList.contains('active') || !initialSportsSec.classList.contains('hidden'))) {
    window.loadSportsHub();
  }
})();
