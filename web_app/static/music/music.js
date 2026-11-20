/* BahonIQ Музыка в авто - Премиум PWA плеер (Версия: 20261117_v15) */
(function() {
  'use strict';

  // --- Вспомогательные селекторы ---
  const $ = id => document.getElementById(id);

  // --- DOM элементы главного экрана ---
  const audio = $('carAudioElement');
  const coverImg = $('carCoverImg');
  const trackTitle = $('carTrackTitle');
  const trackArtist = $('carTrackArtist');
  const timeCurrent = $('carTimeCurrent');
  const timeTotal = $('carTimeTotal');
  const seekBar = $('carSeekBar');
  const progressWrap = $('carProgressWrap');
  const controlsSub = $('carControlsSub');
  const offlineStatus = $('carOfflineStatus');
  const offlineText = $('carOfflineText');

  // Кнопки управления воспроизведением
  const btnPlay = $('carBtnPlay');
  const iconPlay = $('carIconPlay');
  const iconPause = $('carIconPause');
  const btnPrev = $('carBtnPrev');
  const btnNext = $('carBtnNext');
  const btnShuffle = $('carBtnShuffle');
  const btnRepeat = $('carBtnRepeat');
  const btnFav = $('carBtnFav');
  const btnDownloadActive = $('carBtnDownloadActive') || $('carBtnDownload');

  // Модальные окна и шторки
  const btnPlaylist = $('carBtnPlaylist');
  const catalogDrawer = $('carCatalogDrawer');
  const btnCloseCatalog = $('carBtnCloseCatalog');
  const searchInput = $('carSearchInput');
  const tracksListEl = $('carTracksList');
  const btnSound = $('carBtnSound');
  const soundModal = $('carSoundModal');
  const btnCloseSound = $('carBtnCloseSound');
  const btnDiag = $('carBtnDiag');
  const diagModal = $('carDiagModal');
  const btnCloseDiag = $('carBtnCloseDiag');
  const authModal = $('carAuthModal');
  const authForm = $('carAuthForm');
  const authPassword = $('carAuthPassword');

  // Элементы звукового процессора
  const bassSlider = $('carBassSlider');
  const trebleSlider = $('carTrebleSlider');
  const bassValEl = $('carBassVal');
  const trebleValEl = $('carTrebleVal');
  const presetBtns = document.querySelectorAll('.car-sound-preset, .car-preset-btn');

  // Элементы диагностики
  const diagCurrentTrack = $('diagCurrentTrack');
  const diagAudioStatus = $('diagAudioStatus');
  const diagStorageEngine = $('diagStorageEngine');
  const diagOfflineCount = $('diagOfflineCount');
  const diagLastCmd = $('diagLastCmd');
  const diagCmdTime = $('diagCmdTime');

  // Кнопка «Скачать все»
  const btnDownloadAll = $('carBtnDownloadAll');

  // --- Состояние приложения ---
  let playlist = [];
  let filteredPlaylist = [];
  let currentIndex = -1;
  let isShuffle = localStorage.getItem('bahoniq_shuffle') === 'true';
  let repeatMode = localStorage.getItem('bahoniq_repeat') || 'none'; // 'none' | 'all' | 'one'
  let activeTab = 'all'; // 'all' | 'downloaded' | 'favorites'
  let isDownloadingAll = false;
  let playRequestId = 0;
  const streamRetryByTrack = new Map();

  const OFFLINE_IDS_STORAGE_KEY = 'bahoniq_offline_track_ids';
  const CACHED_PLAYLIST_KEY = 'bahoniq_cached_playlist';
  const FAVORITES_STORAGE_KEY = 'bahoniq_favorite_track_ids';
  const RECENT_STORAGE_KEY = 'bahoniq_recent_track_ids';
  const LAST_POS_STORAGE_KEY = 'bahoniq_last_track_pos';

  const offlineTrackIds = new Set();
  const downloadingTrackIds = new Set();
  const downloadPromises = new Map();
  const downloadAbortControllers = new Map();
  const favorites = new Set();
  const recentTrackIds = [];
  const playbackHistory = [];
  let shuffleBag = [];
  let playbackContextTab = 'all'; // 'all' | 'downloaded' | 'recent' | 'favorites'
  let toastTimer = null;

  const repeatOneBadge = $('carRepeatOneBadge');
  const toastEl = $('carToast');
  const metaDurationEl = $('carMetaDuration');
  const inlineStatusEl = $('carInlineStatus');
  const waveformBarsEl = $('carWaveformBars');
  const btnDriveMode = $('carBtnDriveMode');
  const driveModeLabel = $('carDriveModeLabel');
  const btnFavDrive = $('carBtnFavDrive');
  const upNextStrip = $('carUpNextStrip');
  const upNextTitleEl = $('carUpNextTitle');
  const upNextMetaEl = $('carUpNextMeta');

  // --- Элементы и состояние Онлайн-Радио ---
  const btnRadio = $('carBtnRadio');
  const radioDrawer = $('carRadioDrawer');
  const btnCloseRadio = $('carBtnCloseRadio');
  const btnExitRadio = $('carBtnExitRadio');
  const radioListEl = $('carRadioList');
  const radioTabsEl = $('carRadioTabs');
  const radioSubgroupsEl = $('carRadioSubgroups');
  const radioSearch = $('carRadioSearch');
  const radioSearchClear = $('carRadioSearchClear');
  const btnAddRadio = $('carBtnAddRadio');
  const radioModal = $('carRadioModal');
  const btnCloseRadioModal = $('carBtnCloseRadioModal');
  const customRadioForm = $('carCustomRadioForm');
  const customRadioEditId = $('carCustomRadioEditId');
  const customRadioName = $('carCustomRadioName');
  const customRadioUrl = $('carCustomRadioUrl');
  const customRadioFreq = $('carCustomRadioFreq');
  const customRadioGenre = $('carCustomRadioGenre');
  const customRadioCountry = $('carCustomRadioCountry');
  const radioFormError = $('carRadioFormError');

  const CUSTOM_RADIO_KEY = 'bahoniq_custom_radio_stations';
  const RADIO_FAVORITES_KEY = 'bahoniq_favorite_radio_ids';
  const LAST_RADIO_KEY = 'bahoniq_last_radio_id';
  let radioMode = false;
  let radioStations = [];
  let customRadioStations = [];
  const favoriteRadioIds = new Set();
  let currentRadioIndex = -1;
  let radioFilter = 'all';
  let radioSubgroup = 'all';
  let radioMetadataTimer = null;
  let radioPlayTimeout = null;

  // --- Палитры живой атмосферы и генератор обложек для треков ---
  const AMBIENT_PALETTES = [
    { bg1: '#58082c', bg2: '#1a0b2e', accent: '#ff2a85', amb: ['#ff1e6b', '#00e5ff', '#7928ca'] },
    { bg1: '#063b2d', bg2: '#0f2438', accent: '#fbbf24', amb: ['#10b981', '#f59e0b', '#0284c7'] },
    { bg1: '#1e1b4b', bg2: '#09192f', accent: '#38bdf8', amb: ['#6366f1', '#00e5ff', '#ec4899'] },
    { bg1: '#3b0764', bg2: '#0c192c', accent: '#c084fc', amb: ['#a855f7', '#00e5ff', '#f43f5e'] },
    { bg1: '#451a03', bg2: '#111827', accent: '#fb923c', amb: ['#f97316', '#eab308', '#0ea5e9'] },
    { bg1: '#0f172a', bg2: '#064e3b', accent: '#2dd4bf', amb: ['#14b8a6', '#38bdf8', '#6366f1'] }
  ];

  function hashTrackString(str) {
    let h = 2166136261;
    const s = String(str || '');
    for (let i = 0; i < s.length; i++) {
      h ^= s.charCodeAt(i);
      h = Math.imul(h, 16777619);
    }
    return Math.abs(h);
  }

  function makeTrackArtworkSvgDataUri(track) {
    const title = String(track?.title || 'Музыка').trim();
    const artist = String(track?.artist || 'BahonIQ Music').trim();
    const h = hashTrackString(`${artist}::${title}`);
    const pal = AMBIENT_PALETTES[h % AMBIENT_PALETTES.length];
    const shortTitle = title.length > 22 ? title.slice(0, 21) + '…' : title;
    const shortArtist = artist.length > 28 ? artist.slice(0, 27) + '…' : artist;

    const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 600" width="600" height="600">
      <defs>
        <linearGradient id="g" x1="0%" y1="0%" x2="100%" y2="100%">
          <stop offset="0%" stop-color="${pal.bg1}"/>
          <stop offset="55%" stop-color="${pal.bg2}"/>
          <stop offset="100%" stop-color="#050811"/>
        </linearGradient>
        <radialGradient id="glow" cx="72%" cy="28%" r="55%">
          <stop offset="0%" stop-color="${pal.accent}" stop-opacity="0.65"/>
          <stop offset="100%" stop-color="${pal.accent}" stop-opacity="0"/>
        </radialGradient>
      </defs>
      <rect width="600" height="600" fill="url(#g)"/>
      <rect width="600" height="600" fill="url(#glow)"/>
      <circle cx="430" cy="180" r="150" fill="none" stroke="rgba(255,255,255,0.12)" stroke-width="2"/>
      <circle cx="430" cy="180" r="105" fill="none" stroke="rgba(255,255,255,0.18)" stroke-width="1.5"/>
      <circle cx="430" cy="180" r="55" fill="${pal.accent}" fill-opacity="0.28" stroke="${pal.accent}" stroke-width="3"/>
      <text x="48" y="475" fill="rgba(255,255,255,0.78)" font-family="Segoe UI, sans-serif" font-size="22" font-weight="600" letter-spacing="1.5">${escapeHtml(shortArtist.toUpperCase())}</text>
      <text x="48" y="528" fill="#ffffff" font-family="Segoe UI, sans-serif" font-size="38" font-weight="900">${escapeHtml(shortTitle)}</text>
    </svg>`;
    return 'data:image/svg+xml;utf8,' + encodeURIComponent(svg);
  }

  function applyTrackAmbientAndCover(track) {
    if (!track) return;
    const tid = Number(track.id);
    const h = hashTrackString(`${track.artist || ''}::${track.title || ''}`);
    const pal = AMBIENT_PALETTES[h % AMBIENT_PALETTES.length];
    document.documentElement.style.setProperty('--amb-1', pal.amb[0]);
    document.documentElement.style.setProperty('--amb-2', pal.amb[1]);
    document.documentElement.style.setProperty('--amb-3', pal.amb[2]);

    const generatedCover = makeTrackArtworkSvgDataUri(track);
    coverImg.onerror = () => {
      coverImg.onerror = () => {
        coverImg.onerror = null;
        coverImg.src = '/music/assets/logo.png';
      };
      coverImg.src = generatedCover;
    };
    // Если на сервере есть реальная обложка в MP3/Telegram — загрузится она, иначе сработает fallback=404 -> стильная обложка трека
    if (!Number.isFinite(tid) || track.isRadio) {
      coverImg.onerror = null;
      coverImg.src = generatedCover;
      return;
    }
    coverImg.src = `/api/music/tracks/${tid}/cover?fallback=404&v=${encodeURIComponent(track.cover_version || 0)}`;
  }

  // --- Анимированная звуковая волна (Waveform) ---
  const WAVEFORM_BARS_COUNT = 48;
  let currentWaveformHeights = [];
  let currentProgressRatio = 0;

  function buildWaveformShapeForTrack(track) {
    const seed = hashTrackString(`${track?.id || 0}::${track?.title || ''}`);
    const arr = [];
    for (let i = 0; i < WAVEFORM_BARS_COUNT; i++) {
      const wave1 = Math.sin((i / WAVEFORM_BARS_COUNT) * Math.PI) * 55;
      const wave2 = Math.abs(Math.sin(seed * 0.01 + i * 0.65)) * 38;
      arr.push(Math.max(18, Math.min(100, Math.round(16 + wave1 + wave2))));
    }
    currentWaveformHeights = arr;
    renderWaveformBars(currentProgressRatio);
  }

  function renderWaveformBars(ratio = 0) {
    if (!waveformBarsEl) return;
    currentProgressRatio = Math.max(0, Math.min(1, Number(ratio) || 0));
    if (currentWaveformHeights.length === 0) {
      buildWaveformShapeForTrack(playlist[currentIndex] || { id: 1, title: 'BahonIQ' });
      return;
    }
    if (waveformBarsEl.children.length !== WAVEFORM_BARS_COUNT) {
      waveformBarsEl.innerHTML = '';
      for (let i = 0; i < WAVEFORM_BARS_COUNT; i++) {
        const bar = document.createElement('div');
        bar.className = 'wf-bar';
        waveformBarsEl.appendChild(bar);
      }
    }
    const headIdx = Math.min(WAVEFORM_BARS_COUNT - 1, Math.floor(currentProgressRatio * WAVEFORM_BARS_COUNT));
    const children = waveformBarsEl.children;
    for (let i = 0; i < WAVEFORM_BARS_COUNT; i++) {
      const bar = children[i];
      const h = currentWaveformHeights[i] || 40;
      if (radioMode) {
        bar.className = 'wf-bar radio-live';
        bar.style.height = `${Math.max(12, Math.round((h / 100) * 40))}px`;
        bar.style.setProperty('--radio-wave-delay', `${(i % 12) * -0.075}s`);
        continue;
      }
      bar.className = 'wf-bar' + (i < headIdx ? ' played' : '') + (i === headIdx && currentProgressRatio > 0 ? ' head' : '');
      bar.style.height = `${Math.max(10, Math.round((h / 100) * 40))}px`;
      bar.style.removeProperty('--radio-wave-delay');
    }
  }

  if (waveformBarsEl) {
    const seekFromPointer = (clientX) => {
      if (radioMode) return;
      const rect = waveformBarsEl.getBoundingClientRect();
      if (!rect.width) return;
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      renderWaveformBars(ratio);
      if (!isNaN(audio.duration) && audio.duration > 0) {
        audio.currentTime = ratio * audio.duration;
        timeCurrent.textContent = formatTime(audio.currentTime);
        try { localStorage.setItem(LAST_POS_STORAGE_KEY, String(Math.floor(audio.currentTime))); } catch {}
      }
    };
    let isSeekingWave = false;
    waveformBarsEl.addEventListener('pointerdown', e => {
      isSeekingWave = true;
      seekFromPointer(e.clientX);
    });
    window.addEventListener('pointermove', e => {
      if (isSeekingWave) seekFromPointer(e.clientX);
    });
    window.addEventListener('pointerup', () => {
      isSeekingWave = false;
    });
  }

  // Плавное дыхание звуковой волны во время воспроизведения
  setInterval(() => {
    if (audio.paused || !waveformBarsEl || currentWaveformHeights.length === 0) return;
    const headIdx = Math.min(WAVEFORM_BARS_COUNT - 1, Math.floor(currentProgressRatio * WAVEFORM_BARS_COUNT));
    const children = waveformBarsEl.children;
    for (let i = 0; i <= headIdx && i < children.length; i++) {
      const base = currentWaveformHeights[i] || 50;
      const jitter = Math.sin(Date.now() / 180 + i * 0.7) * 11;
      const h = Math.max(12, Math.min(42, Math.round(((base + jitter) / 100) * 40)));
      children[i].style.height = `${h}px`;
    }
  }, 140);

  // --- Обновление строки «Далее в очереди» ---
  function peekNextTrackInQueue() {
    if (playlist.length === 0) return null;
    const queue = getActiveQueueIndices();
    if (queue.length === 0) return null;
    if (isShuffle) {
      const validSet = new Set(queue);
      shuffleBag = shuffleBag.filter(i => validSet.has(i) && i !== currentIndex);
      if (shuffleBag.length === 0 && queue.length > 1) {
        shuffleBag = queue.filter(i => i !== currentIndex);
        for (let i = shuffleBag.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [shuffleBag[i], shuffleBag[j]] = [shuffleBag[j], shuffleBag[i]];
        }
      }
      const nextIdx = shuffleBag.length > 0 ? shuffleBag[shuffleBag.length - 1] : queue[0];
      return playlist[nextIdx] || null;
    }
    const pos = queue.indexOf(currentIndex);
    const nextIdx = pos >= 0 ? queue[(pos + 1) % queue.length] : (currentIndex + 1) % playlist.length;
    return playlist[nextIdx] || null;
  }

  function updateUpNextStrip() {
    if (!upNextTitleEl) return;
    const nextTrack = peekNextTrackInQueue();
    if (!nextTrack) {
      upNextTitleEl.textContent = '—';
      if (upNextMetaEl) upNextMetaEl.textContent = '';
      return;
    }
    const ntid = Number(nextTrack.id);
    const isOff = offlineTrackIds.has(ntid);
    upNextTitleEl.textContent = `${nextTrack.title || 'Без названия'} — ${nextTrack.artist || 'Музыка ДИТ'}`;
    if (upNextMetaEl) {
      upNextMetaEl.textContent = `(${formatTime(nextTrack.duration)} · ${isOff ? 'офлайн' : 'онлайн'})`;
    }
  }

  if (upNextStrip) {
    upNextStrip.addEventListener('click', () => {
      playNextTrack();
    });
  }

  // --- Переключатель двух режимов: Обычный / В дороге ---
  let isDriveMode = localStorage.getItem('bahoniq_drive_mode') === 'true';
  function syncDriveModeUI() {
    document.body.classList.toggle('drive-mode', isDriveMode);
    if (btnDriveMode) btnDriveMode.classList.toggle('active', isDriveMode);
    if (driveModeLabel) driveModeLabel.textContent = isDriveMode ? 'Обычный вид' : 'В дороге';
  }
  syncDriveModeUI();
  if (btnDriveMode) {
    btnDriveMode.addEventListener('click', () => {
      isDriveMode = !isDriveMode;
      localStorage.setItem('bahoniq_drive_mode', isDriveMode ? 'true' : 'false');
      syncDriveModeUI();
      showCarToast(isDriveMode ? '🚗 Режим «В дороге»: крупные кнопки' : '🎛️ Обычный режим плеера');
    });
  }

  function showCarToast(msg) {
    if (!toastEl) return;
    toastEl.textContent = msg;
    toastEl.classList.remove('hidden');
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(() => {
      toastEl.classList.add('hidden');
    }, 2000);
  }

  function persistFavorites() {
    try {
      localStorage.setItem(FAVORITES_STORAGE_KEY, JSON.stringify(Array.from(favorites)));
    } catch {}
    if (idb && idb.objectStoreNames.contains('favorites')) {
      try {
        const tx = idb.transaction('favorites', 'readwrite');
        const store = tx.objectStore('favorites');
        store.clear();
        favorites.forEach(id => store.put({ id: Number(id) }));
      } catch {}
    }
    updateTabCounters();
  }

  function loadFavoritesFromStorage() {
    try {
      const raw = localStorage.getItem(FAVORITES_STORAGE_KEY);
      if (raw) {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr)) {
          arr.forEach(id => favorites.add(Number(id)));
        }
      }
    } catch {}
  }

  function persistRecentTracks() {
    try {
      localStorage.setItem(RECENT_STORAGE_KEY, JSON.stringify(recentTrackIds.slice(0, 50)));
    } catch {}
    updateTabCounters();
  }

  function loadRecentTracksFromStorage() {
    try {
      const raw = localStorage.getItem(RECENT_STORAGE_KEY);
      if (raw) {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr)) {
          recentTrackIds.length = 0;
          arr.forEach(id => {
            const n = Number(id);
            if (n && !recentTrackIds.includes(n)) recentTrackIds.push(n);
          });
        }
      }
    } catch {}
  }

  function recordRecentTrack(trackId) {
    const tid = Number(trackId);
    if (!tid) return;
    const existingIdx = recentTrackIds.indexOf(tid);
    if (existingIdx !== -1) recentTrackIds.splice(existingIdx, 1);
    recentTrackIds.unshift(tid);
    if (recentTrackIds.length > 50) recentTrackIds.length = 50;
    persistRecentTracks();
  }

  function updateTabCounters() {
    document.querySelectorAll('.car-tab[data-tab]').forEach(btn => {
      const tab = btn.dataset.tab;
      let count = 0;
      if (tab === 'all') count = playlist.length;
      else if (tab === 'downloaded') count = playlist.filter(t => offlineTrackIds.has(Number(t.id))).length;
      else if (tab === 'recent') count = recentTrackIds.filter(id => playlist.some(t => Number(t.id) === Number(id))).length;
      else if (tab === 'favorites') count = playlist.filter(t => favorites.has(Number(t.id))).length;

      const labels = {
        all: 'Все треки',
        downloaded: 'Скачанные (Офлайн)',
        recent: 'Недавние',
        favorites: 'Избранное'
      };
      const base = labels[tab] || btn.textContent;
      btn.innerHTML = `${base} <span class="car-tab-count">${count}</span>`;
    });
  }

  // Кэш сгенерированных Object URL в оперативной памяти (для мгновенного старта 0мс)
  const memoryBlobUrls = new Map();

  // --- Персистентность реестра офлайн-треков ---
  function persistOfflineTrackIds() {
    try {
      localStorage.setItem(OFFLINE_IDS_STORAGE_KEY, JSON.stringify(Array.from(offlineTrackIds)));
    } catch {}
    if (diagOfflineCount) {
      diagOfflineCount.textContent = `${offlineTrackIds.size} треков`;
    }
  }

  function loadOfflineTrackIdsFromStorage() {
    try {
      const raw = localStorage.getItem(OFFLINE_IDS_STORAGE_KEY);
      if (raw) {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr)) {
          arr.forEach(id => offlineTrackIds.add(Number(id)));
        }
      }
    } catch {}
    if (diagOfflineCount) {
      diagOfflineCount.textContent = `${offlineTrackIds.size} треков`;
    }
  }

  function persistCachedPlaylist() {
    try {
      localStorage.setItem(CACHED_PLAYLIST_KEY, JSON.stringify(playlist));
    } catch {}
  }

  function loadCachedPlaylistFromStorage() {
    if (playlist.length > 0) return;
    try {
      const raw = localStorage.getItem(CACHED_PLAYLIST_KEY);
      if (raw) {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr) && arr.length > 0) {
          playlist = arr;
          filteredPlaylist = [...playlist];
        }
      }
    } catch {}
  }

  // --- IndexedDB Хранилище ---
  const DB_NAME = 'bahoniq_music_store';
  const DB_VERSION = 1;
  let idb = null;

  function initIndexedDB() {
    return new Promise((resolve) => {
      try {
        const req = indexedDB.open(DB_NAME, DB_VERSION);
        req.onupgradeneeded = e => {
          const db = e.target.result;
          if (!db.objectStoreNames.contains('tracks_meta')) {
            db.createObjectStore('tracks_meta', { keyPath: 'id' });
          }
          if (!db.objectStoreNames.contains('tracks_blobs')) {
            db.createObjectStore('tracks_blobs', { keyPath: 'id' });
          }
          if (!db.objectStoreNames.contains('favorites')) {
            db.createObjectStore('favorites', { keyPath: 'id' });
          }
        };
        req.onsuccess = e => {
          idb = e.target.result;
          resolve(idb);
        };
        req.onerror = () => resolve(null);
      } catch {
        resolve(null);
      }
    });
  }

  // Однократный перенос офлайн-треков из имени БД ранних версий плеера.
  async function migrateLegacyIndexedDB() {
    if (!idb || !indexedDB.databases) return;
    try {
      const databases = await indexedDB.databases();
      if (!databases.some(db => db.name === 'BahonIQ_Music_DB')) return;
      const legacy = await new Promise(resolve => {
        const req = indexedDB.open('BahonIQ_Music_DB');
        req.onsuccess = () => resolve(req.result);
        req.onerror = () => resolve(null);
      });
      if (!legacy || !legacy.objectStoreNames.contains('tracks_blobs')) return;
      const rows = await new Promise(resolve => {
        const tx = legacy.transaction('tracks_blobs', 'readonly');
        const req = tx.objectStore('tracks_blobs').getAll();
        req.onsuccess = () => resolve(req.result || []);
        req.onerror = () => resolve([]);
      });
      for (const row of rows) {
        const blob = row?.blob;
        if (!blob || blob.size < 20000) continue;
        await new Promise(resolve => {
          const tx = idb.transaction('tracks_blobs', 'readwrite');
          tx.objectStore('tracks_blobs').put({
            ...row, id: Number(row.id), blob, size: blob.size, complete: true
          });
          tx.oncomplete = resolve;
          tx.onerror = resolve;
          tx.onabort = resolve;
        });
      }
      legacy.close();
    } catch (err) {
      console.warn('Legacy offline storage migration skipped:', err);
    }
  }

  // --- OPFS (Origin Private File System) Хранилище ---
  let opfsRoot = null;
  async function initOPFS() {
    try {
      if (navigator.storage && navigator.storage.getDirectory) {
        opfsRoot = await navigator.storage.getDirectory();
      }
    } catch {
      opfsRoot = null;
    }
    if (diagStorageEngine) {
      diagStorageEngine.textContent = opfsRoot ? 'OPFS + IndexedDB' : (idb ? 'IndexedDB' : 'Онлайн');
    }
  }

  // --- Сохранение аудиофайла локально (IndexedDB + OPFS) ---
  async function saveAudioLocally(trackId, blob, trackMeta = null) {
    const tid = Number(trackId);
    const expectedSize = Number(trackMeta?.file_size || 0);
    if (!blob || blob.size < 20000) {
      console.warn(`saveAudioLocally: rejected invalid blob size (${blob?.size || 0} bytes) for track ${tid}`);
      return false;
    }

    // 1. Сначала мгновенная запись в IndexedDB (без задержки антивируса ОС на закрытии файла)
    let savedInIdb = false;
    if (idb) {
      try {
        await new Promise((resolve, reject) => {
          const txB = idb.transaction('tracks_blobs', 'readwrite');
          txB.objectStore('tracks_blobs').put({
            id: tid,
            blob: blob,
            size: blob.size,
            complete: true,
            expectedSize: blob.size,
            date: Date.now()
          });
          txB.oncomplete = () => resolve();
          txB.onerror = () => reject(txB.error);
          txB.onabort = () => reject(txB.error);
        });
        savedInIdb = true;

        if (trackMeta) {
          const txM = idb.transaction('tracks_meta', 'readwrite');
          txM.objectStore('tracks_meta').put(trackMeta);
        }
      } catch (err) {
        console.warn('IndexedDB write error:', err);
      }
    }

    // 2. Однопроходная запись в OPFS (если доступна)
    let savedInOpfs = false;
    if (opfsRoot) {
      try {
        const fileHandle = await opfsRoot.getFileHandle(`track_${tid}.bin`, { create: true });
        if (typeof fileHandle.createWritable === 'function') {
          const writable = await fileHandle.createWritable();
          await writable.write(blob);
          await writable.close();
          const savedFile = await fileHandle.getFile();
          if (savedFile && savedFile.size === blob.size) {
            savedInOpfs = true;
          } else {
            await opfsRoot.removeEntry(`track_${tid}.bin`).catch(() => {});
          }
        }
      } catch (err) {
        await opfsRoot.removeEntry(`track_${tid}.bin`).catch(() => {});
        console.warn('OPFS write fallback:', err);
      }
    }

    if (savedInIdb || savedInOpfs) {
      offlineTrackIds.add(tid);
      persistOfflineTrackIds();
      if (memoryBlobUrls.has(tid)) {
        URL.revokeObjectURL(memoryBlobUrls.get(tid));
      }
      memoryBlobUrls.set(tid, URL.createObjectURL(blob));
      return true;
    }
    return false;
  }

  // --- Получение аудиофайла из локального хранилища ---
  async function getLocalAudioBlob(trackId, expectedSize = 0) {
    const tid = Number(trackId);

    // 1. Проверяем OPFS
    if (opfsRoot) {
      try {
        const handle = await opfsRoot.getFileHandle(`track_${tid}.bin`);
        const file = await handle.getFile();
        if (file && file.size >= 20000) {
          return file;
        }
        if (file && file.size < 20000) await opfsRoot.removeEntry(`track_${tid}.bin`).catch(() => {});
      } catch {}
    }

    // 2. Проверяем IndexedDB
    if (idb) {
      return new Promise(resolve => {
        try {
          const tx = idb.transaction('tracks_blobs', 'readonly');
          const req = tx.objectStore('tracks_blobs').get(tid);
          req.onsuccess = () => {
            const row = req.result;
            const b = row?.blob;
            const size = Number(b?.size || row?.size || 0);
            if (b && size >= 20000 && row.complete !== false) {
              resolve(b);
            } else {
              resolve(null);
            }
          };
          req.onerror = () => resolve(null);
        } catch {
          resolve(null);
        }
      });
    }

    return null;
  }

  // --- Удаление трека из локальной памяти ---
  async function deleteLocalAudio(trackId) {
    const tid = Number(trackId);
    if (opfsRoot) {
      try {
        await opfsRoot.removeEntry(`track_${tid}.bin`);
      } catch {}
    }
    if (idb) {
      try {
        const tx = idb.transaction('tracks_blobs', 'readwrite');
        tx.objectStore('tracks_blobs').delete(tid);
      } catch {}
    }
    if (memoryBlobUrls.has(tid)) {
      URL.revokeObjectURL(memoryBlobUrls.get(tid));
      memoryBlobUrls.delete(tid);
    }
    offlineTrackIds.delete(tid);
    persistOfflineTrackIds();
    updateTrackItemBadge(tid);
    syncDownloadAllButton();
    if (currentIndex >= 0 && Number(playlist[currentIndex]?.id) === tid) {
      updateOfflinePill('stream');
      if (btnDownloadActive) btnDownloadActive.classList.remove('active');
    }
  }

  // --- Сканирование офлайн-треков при старте приложения ---
  async function scanOfflineTracks() {
    offlineTrackIds.clear();
    loadCachedPlaylistFromStorage();

    // 1. Точная инспекция записей IndexedDB и подготовка быстрых Blob URL в памяти
    if (idb) {
      await new Promise(resolve => {
        try {
          const tx = idb.transaction('tracks_blobs', 'readonly');
          const req = tx.objectStore('tracks_blobs').getAll();
          req.onsuccess = () => {
            (req.result || []).forEach(row => {
              const b = row?.blob;
              const size = Number(b?.size || row?.size || 0);
              if (b && size >= 20000 && row.complete !== false) {
                const tid = Number(row.id);
                offlineTrackIds.add(tid);
                if (!memoryBlobUrls.has(tid)) {
                  memoryBlobUrls.set(tid, URL.createObjectURL(b));
                }
              }
            });
            resolve();
          };
          req.onerror = () => resolve();
        } catch {
          resolve();
        }
      });
    }

    // 2. Проверка файлов в OPFS
    if (opfsRoot && playlist.length > 0) {
      for (let i = 0; i < playlist.length; i += 16) {
        const batch = playlist.slice(i, i + 16);
        await Promise.all(batch.map(async t => {
          try {
            const tid = Number(t.id);
            const handle = await opfsRoot.getFileHandle(`track_${tid}.bin`);
            const file = await handle.getFile();
            if (file && file.size >= 20000) {
              offlineTrackIds.add(tid);
              if (!memoryBlobUrls.has(tid)) {
                memoryBlobUrls.set(tid, URL.createObjectURL(file));
              }
            }
          } catch {}
        }));
      }
    }

    // 3. Восстановление метаданных из IDB, если сети нет
    if (idb && playlist.length === 0) {
      await new Promise(resolve => {
        try {
          const tx = idb.transaction('tracks_meta', 'readonly');
          const req = tx.objectStore('tracks_meta').getAll();
          req.onsuccess = () => {
            if (playlist.length === 0 && req.result && req.result.length > 0) {
              playlist = req.result;
              filteredPlaylist = [...playlist];
              persistCachedPlaylist();
            }
            resolve();
          };
          req.onerror = () => resolve();
        } catch {
          resolve();
        }
      });
    }

    persistOfflineTrackIds();
    syncDownloadAllButton();
    renderCatalog();
  }

  // --- Форматирование секунд в mm:ss или hh:mm:ss ---
  function formatTime(seconds) {
    if (!seconds || isNaN(seconds) || seconds < 0) return '0:00';
    const h = Math.floor(seconds / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = Math.floor(seconds % 60);
    if (h > 0) {
      return `${h}:${m < 10 ? '0' : ''}${m}:${s < 10 ? '0' : ''}${s}`;
    }
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  }

  // --- Индикатор статуса источника звука (Офлайн / Стриминг / Загрузка) ---
  function updateOfflinePill(state, progress = 0) {
    if (inlineStatusEl) {
      inlineStatusEl.className = 'car-inline-status';
      if (state === 'offline') {
        inlineStatusEl.classList.add('offline');
        inlineStatusEl.textContent = 'сохранено офлайн';
      } else if (state === 'downloading') {
        inlineStatusEl.classList.add('downloading');
        inlineStatusEl.textContent = progress > 0 ? `сохранение ${progress}%` : 'сохранение...';
      } else {
        inlineStatusEl.textContent = 'онлайн';
      }
    }
    if (!offlineStatus || !offlineText) return;
    offlineStatus.className = 'car-offline-pill hidden';
  }

  // --- Фоновое скачивание трека в постоянную память (после старта воспроизведения, как в Telegram) ---
  async function downloadTrackInBackground(track, isManual = false) {
    if (!track) return false;
    const tid = Number(track.id);

    if (offlineTrackIds.has(tid) && memoryBlobUrls.has(tid)) return true;
    if (downloadPromises.has(tid)) return downloadPromises.get(tid);

    const controller = new AbortController();
    downloadAbortControllers.set(tid, controller);

    const task = (async () => {
      downloadingTrackIds.add(tid);
      updateTrackItemBadge(tid);
      if (currentIndex >= 0 && Number(playlist[currentIndex]?.id) === tid) {
        updateOfflinePill('downloading');
        if (btnDownloadActive) btnDownloadActive.classList.add('loading');
      }

      try {
        for (let attempt = 1; attempt <= 3; attempt++) {
          if (controller.signal.aborted) throw new DOMException('Aborted', 'AbortError');
          try {
            const resp = await fetch(`/api/music/tracks/${tid}/download`, { signal: controller.signal });
            if (!resp.ok) throw new Error(`HTTP ${resp.status}`);

            const responseSize = Number(resp.headers.get('Content-Length') || track.file_size || 0);
            let blob = null;

            if (resp.body && typeof resp.body.getReader === 'function' && responseSize > 0) {
              const reader = resp.body.getReader();
              const chunks = [];
              let received = 0;
              let lastPct = 0;
              try {
                while (true) {
                  const { done, value } = await reader.read();
                  if (done) break;
                  if (value) {
                    chunks.push(value);
                    received += value.byteLength;
                    const pct = Math.min(99, Math.floor((received / responseSize) * 100));
                    if (pct >= lastPct + 5 && currentIndex >= 0 && Number(playlist[currentIndex]?.id) === tid) {
                      lastPct = pct;
                      updateOfflinePill('downloading', pct);
                    }
                  }
                }
              } catch (readErr) {
                // Сохраняем уже полученные чанки и ниже дозагружаем только хвост.
                console.warn(`Initial download interrupted at ${received}/${responseSize}:`, readErr);
              }

              // На мобильной сети/Render длинный ответ иногда завершается на 95–99%.
              // Не скачиваем файл заново: добираем только отсутствующий хвост Range-запросом.
              for (let repair = 0; responseSize > 0 && received < responseSize && repair < 3; repair++) {
                const repairResp = await fetch(
                  `/api/music/tracks/${tid}/stream?resume=${Date.now()}`,
                  {
                    signal: controller.signal,
                    headers: { Range: `bytes=${received}-${responseSize - 1}` }
                  }
                );
                if (repairResp.status !== 206) {
                  throw new Error(`Range repair failed: HTTP ${repairResp.status}`);
                }
                const repairReader = repairResp.body?.getReader();
                if (!repairReader) throw new Error('Range repair body is unavailable');
                const beforeRepair = received;
                try {
                  while (received < responseSize) {
                    const { done, value } = await repairReader.read();
                    if (done) break;
                    if (!value || value.byteLength === 0) continue;
                    const remaining = responseSize - received;
                    const piece = value.byteLength > remaining ? value.slice(0, remaining) : value;
                    chunks.push(piece);
                    received += piece.byteLength;
                    const pct = Math.min(100, Math.floor((received / responseSize) * 100));
                    if (currentIndex >= 0 && Number(playlist[currentIndex]?.id) === tid) {
                      updateOfflinePill('downloading', pct);
                    }
                  }
                } catch (repairErr) {
                  console.warn(`Range repair ${repair + 1} interrupted at ${received}/${responseSize}:`, repairErr);
                }
                if (received <= beforeRepair) break;
              }
              blob = new Blob(chunks, { type: resp.headers.get('Content-Type') || track.mime_type || 'audio/mpeg' });
            } else {
              blob = await resp.blob();
            }

            if (!blob || blob.size < 20000 || (responseSize > 0 && Math.abs(blob.size - responseSize) > 4096)) {
              throw new Error(`Downloaded blob size mismatch (${blob?.size || 0} vs ${responseSize})`);
            }

            if (currentIndex >= 0 && Number(playlist[currentIndex]?.id) === tid) {
              updateOfflinePill('downloading', 100);
            }

            const saved = await saveAudioLocally(tid, blob, { ...track, file_size: blob.size });
            if (!saved) throw new Error('Failed to save blob locally');

            offlineTrackIds.add(tid);
            memoryBlobUrls.set(tid, URL.createObjectURL(blob));
            downloadingTrackIds.delete(tid);
            downloadPromises.delete(tid);
            persistOfflineTrackIds();
            updateTrackItemBadge(tid);
            updateTabCounters();
            syncDownloadAllButton();

            if (currentIndex >= 0 && Number(playlist[currentIndex]?.id) === tid) {
              updateOfflinePill('offline');
              if (btnDownloadActive) {
                btnDownloadActive.classList.remove('loading');
                btnDownloadActive.classList.add('active');
              }
              // После сохранения текущего трека тихо предзагружаем следующий трек в очереди
              setTimeout(() => {
                if (!audio.paused) prefetchNextTrackInQueue();
              }, 1500);
            }
            return true;
          } catch (attemptErr) {
            if (controller.signal.aborted || (attemptErr && attemptErr.name === 'AbortError')) {
              throw attemptErr;
            }
            if (attempt < 3) {
              await new Promise(r => setTimeout(r, 1500));
            } else {
              throw attemptErr;
            }
          }
        }
        return false;
      } catch (err) {
        if (err && err.name !== 'AbortError') {
          console.warn(`Download error for track ${tid}:`, err);
        }
        if (currentIndex >= 0 && Number(playlist[currentIndex]?.id) === tid) {
          updateOfflinePill(offlineTrackIds.has(tid) ? 'offline' : 'stream');
          if (btnDownloadActive) btnDownloadActive.classList.remove('loading');
        }
        return false;
      } finally {
        downloadAbortControllers.delete(tid);
        downloadingTrackIds.delete(tid);
        downloadPromises.delete(tid);
        updateTrackItemBadge(tid);
        syncDownloadAllButton();
        if (btnDownloadActive && (currentIndex < 0 || Number(playlist[currentIndex]?.id) === tid)) {
          btnDownloadActive.classList.remove('loading');
          btnDownloadActive.classList.toggle('active', offlineTrackIds.has(tid));
        }
      }
    })();

    downloadPromises.set(tid, task);
    return await task;
  }

  // --- Запуск воспроизведения трека (СИНХРОННО В СТЕКЕ КЛИКА) ---
  function playTrack(index, recordHistory = true) {
    if (index < 0 || index >= playlist.length) return;
    if (radioMode) {
      radioMode = false;
      currentRadioIndex = -1;
      if (btnRadio) btnRadio.classList.remove('active');
      if (inlineStatusEl) inlineStatusEl.classList.remove('live-air');
      renderRadioList();
    }
    setRadioUiMode(false);
    const requestId = ++playRequestId;

    if (recordHistory && currentIndex >= 0 && currentIndex !== index) {
      playbackHistory.push(playlist[currentIndex]?.id);
      if (playbackHistory.length > 50) playbackHistory.shift();
    }

    currentIndex = index;
    const track = playlist[currentIndex];
    const tid = Number(track.id);
    recordRecentTrack(tid);
    localStorage.setItem(LAST_POS_STORAGE_KEY, '0');

    // Отменяем незавершённые фоновые загрузки других треков, чтобы не мешать текущему потоку
    for (const [otherTid, ctrl] of downloadAbortControllers.entries()) {
      if (otherTid !== tid) {
        try { ctrl.abort(); } catch {}
        downloadAbortControllers.delete(otherTid);
      }
    }

    // 1. СИНХРОННО пробуждаем Web Audio контекст в прямом стеке клика пользователя!
    resumeAudioContext();

    // 2. Метаданные трека
    trackTitle.textContent = track.title || 'Без названия';
    trackArtist.textContent = track.artist || 'Музыка ДИТ';
    if (metaDurationEl) metaDurationEl.textContent = formatTime(track.duration);
    timeTotal.textContent = formatTime(track.duration);
    applyTrackAmbientAndCover(track);
    buildWaveformShapeForTrack(track);
    if (diagCurrentTrack) diagCurrentTrack.textContent = `${track.artist} — ${track.title}`;
    localStorage.setItem('bahoniq_last_track_id', tid);

    const isFav = favorites.has(tid);
    btnFav.classList.toggle('active', isFav);
    btnFav.classList.toggle('fav-active', isFav);
    if (btnFavDrive) {
      btnFavDrive.classList.toggle('active', isFav);
      btnFavDrive.classList.toggle('fav-active', isFav);
    }
    const isOffline = offlineTrackIds.has(tid);
    if (btnDownloadActive) btnDownloadActive.classList.toggle('active', isOffline);
    updateUpNextStrip();

    // 3. Выбор источника (синхронно):
    // Если трек уже сохранён в памяти устройства — воспроизводим локальный Blob URL (0 мс, без сети).
    // Если трек ещё не скачан — начинаем онлайн-стриминг (после начала воспроизведения он сам скачается в фоне).
    let targetSrc = '';
    if (isOffline && memoryBlobUrls.has(tid)) {
      targetSrc = memoryBlobUrls.get(tid);
      updateOfflinePill('offline');
    } else {
      targetSrc = `/api/music/tracks/${tid}/stream`;
      updateOfflinePill(isOffline ? 'offline' : 'stream');
    }

    const absoluteTargetSrc = targetSrc.startsWith('blob:')
      ? targetSrc
      : new URL(targetSrc, window.location.origin).href;
    if (audio.src !== absoluteTargetSrc) {
      audio.src = targetSrc;
    }

    // 4. СИНХРОННЫЙ вызов audio.play() без блокирующих await — Autoplay Policy всегда одобрен!
    const playPromise = audio.play();
    if (playPromise !== undefined) {
      playPromise.then(() => {
        updatePlayButton(true);
      }).catch(err => {
        console.warn('Audio play initiated:', err);
        updatePlayButton(!audio.paused);
      });
    }

    updateMediaSession(track);
    highlightCurrentTrackInList();

    // 5. Если трек помечен как офлайн, но его Blob URL ещё не был создан в памяти — подтягиваем его
    if (isOffline && !memoryBlobUrls.has(tid)) {
      getLocalAudioBlob(tid, Number(track.file_size || 0)).then(blob => {
        if (blob && requestId === playRequestId) {
          const url = URL.createObjectURL(blob);
          memoryBlobUrls.set(tid, url);
          if (audio.currentTime < 1.5 && audio.src !== url) {
            const savedTime = audio.currentTime;
            const wasPlaying = !audio.paused;
            audio.src = url;
            audio.currentTime = savedTime;
            updateOfflinePill('offline');
            if (wasPlaying) audio.play().catch(() => {});
          }
        }
      });
    }
  }

  function updatePlayButton(playing) {
    document.body.classList.toggle('playing', Boolean(playing));
    if (playing) {
      iconPlay.classList.add('hidden');
      iconPause.classList.remove('hidden');
      if (diagAudioStatus) diagAudioStatus.textContent = 'Воспроизведение';
    } else {
      iconPlay.classList.remove('hidden');
      iconPause.classList.add('hidden');
      if (diagAudioStatus) diagAudioStatus.textContent = 'Пауза';
    }
  }

  function getActiveQueueIndices() {
    if (playlist.length === 0) return [];
    let indices = [];
    if (playbackContextTab === 'downloaded') {
      playlist.forEach((t, idx) => {
        if (offlineTrackIds.has(Number(t.id))) indices.push(idx);
      });
    } else if (playbackContextTab === 'favorites') {
      playlist.forEach((t, idx) => {
        if (favorites.has(Number(t.id))) indices.push(idx);
      });
    } else if (playbackContextTab === 'recent') {
      recentTrackIds.forEach(tid => {
        const idx = playlist.findIndex(t => Number(t.id) === Number(tid));
        if (idx >= 0) indices.push(idx);
      });
    }
    if (indices.length === 0) {
      indices = playlist.map((_, i) => i);
    }
    return indices;
  }

  function pickNextShuffleIndex(queueIndices) {
    if (queueIndices.length <= 1) return queueIndices[0] ?? 0;
    const validSet = new Set(queueIndices);
    shuffleBag = shuffleBag.filter(i => validSet.has(i) && i !== currentIndex);
    if (shuffleBag.length === 0) {
      shuffleBag = queueIndices.filter(i => i !== currentIndex);
      // Перемешивание Фишера — Йейтса без повторов
      for (let i = shuffleBag.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [shuffleBag[i], shuffleBag[j]] = [shuffleBag[j], shuffleBag[i]];
      }
    }
    return shuffleBag.pop();
  }

  function prefetchNextTrackInQueue() {
    if (playlist.length <= 1 || downloadPromises.size > 0) return;
    const queue = getActiveQueueIndices();
    if (queue.length === 0) return;
    let nextIdx = -1;
    if (isShuffle) {
      if (shuffleBag.length === 0 && queue.length > 1) {
        shuffleBag = queue.filter(i => i !== currentIndex);
        for (let i = shuffleBag.length - 1; i > 0; i--) {
          const j = Math.floor(Math.random() * (i + 1));
          [shuffleBag[i], shuffleBag[j]] = [shuffleBag[j], shuffleBag[i]];
        }
      }
      const candidate = shuffleBag.length > 0 ? shuffleBag[shuffleBag.length - 1] : -1;
      if (candidate >= 0 && playlist[candidate]) nextIdx = candidate;
    } else {
      const pos = queue.indexOf(currentIndex);
      nextIdx = pos >= 0 ? queue[(pos + 1) % queue.length] : (currentIndex + 1) % playlist.length;
    }
    if (nextIdx >= 0 && playlist[nextIdx]) {
      const nextTrack = playlist[nextIdx];
      const ntid = Number(nextTrack.id);
      if (!offlineTrackIds.has(ntid) && !downloadPromises.has(ntid)) {
        downloadTrackInBackground(nextTrack, false);
      }
    }
  }

  function playNextTrack() {
    if (radioMode) {
      playNextRadioStation();
      return;
    }
    if (playlist.length === 0) return;
    const queue = getActiveQueueIndices();
    if (isShuffle) {
      const nextIdx = pickNextShuffleIndex(queue);
      playTrack(nextIdx, true);
    } else {
      const pos = queue.indexOf(currentIndex);
      const nextIdx = pos >= 0 ? queue[(pos + 1) % queue.length] : (currentIndex + 1) % playlist.length;
      playTrack(nextIdx, true);
    }
  }

  function playPrevTrack() {
    if (radioMode) {
      playPrevRadioStation();
      return;
    }
    if (playlist.length === 0) return;
    if (audio.currentTime > 3) {
      audio.currentTime = 0;
      return;
    }
    if (playbackHistory.length > 0) {
      const prevId = playbackHistory.pop();
      const prevIdx = playlist.findIndex(t => Number(t.id) === Number(prevId));
      if (prevIdx >= 0) {
        playTrack(prevIdx, false);
        return;
      }
    }
    const queue = getActiveQueueIndices();
    const pos = queue.indexOf(currentIndex);
    const prevIdx = pos >= 0 ? queue[(pos - 1 + queue.length) % queue.length] : (currentIndex - 1 + playlist.length) % playlist.length;
    playTrack(prevIdx, false);
  }

  // --- События HTML5 Audio элемента ---
  let lastSavedSec = -1;
  audio.addEventListener('timeupdate', () => {
    if (!radioMode && !isNaN(audio.duration) && isFinite(audio.duration) && audio.duration > 0) {
      const ratio = audio.currentTime / audio.duration;
      const pct = ratio * 100;
      seekBar.value = pct;
      renderWaveformBars(ratio);
      timeCurrent.textContent = formatTime(audio.currentTime);
      timeTotal.textContent = formatTime(audio.duration);
      if (metaDurationEl) metaDurationEl.textContent = formatTime(audio.duration);

      const curSec = Math.floor(audio.currentTime);
      if (curSec !== lastSavedSec && curSec % 3 === 0) {
        lastSavedSec = curSec;
        try {
          localStorage.setItem(LAST_POS_STORAGE_KEY, String(curSec));
        } catch {}
      }

      if ('mediaSession' in navigator && navigator.mediaSession.setPositionState) {
        try {
          navigator.mediaSession.setPositionState({
            duration: audio.duration,
            playbackRate: audio.playbackRate,
            position: audio.currentTime
          });
        } catch {}
      }
    }
  });

  audio.addEventListener('waiting', () => {
    if (diagAudioStatus) diagAudioStatus.textContent = 'Буферизация...';
    btnPlay.classList.add('loading');
  });

  audio.addEventListener('playing', () => {
    if (diagAudioStatus) diagAudioStatus.textContent = 'Воспроизведение';
    btnPlay.classList.remove('loading');
    updatePlayButton(true);
    if (currentIndex >= 0 && playlist[currentIndex]) {
      streamRetryByTrack.delete(Number(playlist[currentIndex].id));
    }
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing';
    if (radioMode) {
      clearTimeout(radioPlayTimeout);
      const station = getAllRadioStations()[currentRadioIndex];
      if (station) startRadioMetadataPolling(station);
      renderRadioList();
    }

    // Автоматическое сохранение в память устройства после фактического старта воспроизведения (как в Telegram)
    if (!radioMode && currentIndex >= 0 && playlist[currentIndex]) {
      const currentTrack = playlist[currentIndex];
      const tid = Number(currentTrack.id);
      if (!offlineTrackIds.has(tid) && !downloadPromises.has(tid)) {
        const activeReqId = playRequestId;
        setTimeout(() => {
          if (
            playRequestId === activeReqId &&
            !audio.paused &&
            currentIndex >= 0 &&
            Number(playlist[currentIndex]?.id) === tid &&
            !offlineTrackIds.has(tid) &&
            !downloadPromises.has(tid)
          ) {
            downloadTrackInBackground(currentTrack);
          }
        }, 1200);
      }
    }
  });

  audio.addEventListener('pause', () => {
    if (diagAudioStatus) diagAudioStatus.textContent = 'Пауза';
    btnPlay.classList.remove('loading');
    updatePlayButton(false);
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'paused';
    if (radioMode) {
      stopRadioMetadataPolling();
      renderRadioList();
    }
  });

  audio.addEventListener('error', (e) => {
    console.warn('Audio stream error event:', e);
    btnPlay.classList.remove('loading');
    if (radioMode) {
      stopRadioMetadataPolling();
      updatePlayButton(false);
      if (diagAudioStatus) diagAudioStatus.textContent = 'Станция недоступна';
      showToast('Радиостанция временно недоступна');
      renderRadioList();
      return;
    }
    const track = currentIndex >= 0 ? playlist[currentIndex] : null;
    const tid = Number(track?.id || 0);
    const retries = streamRetryByTrack.get(tid) || 0;
    const isOnlineSource = tid > 0 && !String(audio.currentSrc || audio.src || '').startsWith('blob:');
    if (isOnlineSource && retries < 2) {
      streamRetryByTrack.set(tid, retries + 1);
      if (diagAudioStatus) diagAudioStatus.textContent = 'Переподключение...';
      recordDiagnosticCommand(`ПОВТОР ПОТОКА ${retries + 1}/2`);
      const expectedRequest = playRequestId;
      setTimeout(() => {
        if (expectedRequest !== playRequestId || Number(playlist[currentIndex]?.id) !== tid) return;
        audio.src = `/api/music/tracks/${tid}/stream?retry=${Date.now()}`;
        audio.load();
        audio.play().catch(err => console.warn('Audio retry failed:', err));
      }, 700 * (retries + 1));
      return;
    }
    updatePlayButton(false);
    if (diagAudioStatus) diagAudioStatus.textContent = 'Ошибка потока';
    recordDiagnosticCommand('ОШИБКА ПОТОКА');
  });

  audio.addEventListener('ended', () => {
    try { localStorage.setItem(LAST_POS_STORAGE_KEY, '0'); } catch {}
    if (repeatMode === 'one') {
      audio.currentTime = 0;
      audio.play().catch(() => {});
    } else {
      const queue = getActiveQueueIndices();
      const pos = queue.indexOf(currentIndex);
      const isLastInQueue = pos >= 0 ? pos === queue.length - 1 : currentIndex >= playlist.length - 1;
      if (repeatMode === 'all' || isShuffle || !isLastInQueue) {
        playNextTrack();
      } else {
        updatePlayButton(false);
      }
    }
  });

  seekBar.addEventListener('input', () => {
    if (!isNaN(audio.duration) && audio.duration > 0) {
      audio.currentTime = (seekBar.value / 100) * audio.duration;
      try { localStorage.setItem(LAST_POS_STORAGE_KEY, String(Math.floor(audio.currentTime))); } catch {}
    }
  });

  btnPlay.addEventListener('click', () => {
    resumeAudioContext();
    if (currentIndex === -1 && playlist.length > 0) {
      playTrack(0);
      return;
    }
    // Если после запуска машины трек был только выбран в UI, но audio.src ещё пустой
    if (!audio.src || audio.src === window.location.href) {
      const resumeSec = Number(localStorage.getItem(LAST_POS_STORAGE_KEY) || '0');
      playTrack(currentIndex >= 0 ? currentIndex : 0, false);
      if (resumeSec > 2) {
        const restoreOnce = () => {
          if (audio.duration && resumeSec < audio.duration - 2) {
            audio.currentTime = resumeSec;
          }
          audio.removeEventListener('loadedmetadata', restoreOnce);
        };
        audio.addEventListener('loadedmetadata', restoreOnce);
      }
      return;
    }
    if (audio.paused) {
      audio.play().then(() => updatePlayButton(true)).catch(err => {
        console.warn('Play button resume failed:', err);
        updatePlayButton(false);
      });
    } else {
      audio.pause();
      updatePlayButton(false);
    }
  });

  btnPrev.addEventListener('click', playPrevTrack);
  btnNext.addEventListener('click', playNextTrack);

  function syncRepeatButtonUI() {
    if (!btnRepeat) return;
    if (repeatMode === 'all') {
      btnRepeat.classList.add('active');
      btnRepeat.classList.remove('repeat-one');
      if (repeatOneBadge) repeatOneBadge.classList.add('hidden');
      btnRepeat.title = 'Повтор: Все треки';
    } else if (repeatMode === 'one') {
      btnRepeat.classList.add('active', 'repeat-one');
      if (repeatOneBadge) repeatOneBadge.classList.remove('hidden');
      btnRepeat.title = 'Повтор: Один трек (1)';
    } else {
      btnRepeat.classList.remove('active', 'repeat-one');
      if (repeatOneBadge) repeatOneBadge.classList.add('hidden');
      btnRepeat.title = 'Повтор: Выключен';
    }
  }

  // Восстановление режимов Shuffle и Repeat
  if (btnShuffle) {
    btnShuffle.classList.toggle('active', isShuffle);
  }
  syncRepeatButtonUI();

  btnShuffle.addEventListener('click', () => {
    isShuffle = !isShuffle;
    shuffleBag = [];
    btnShuffle.classList.toggle('active', isShuffle);
    localStorage.setItem('bahoniq_shuffle', isShuffle ? 'true' : 'false');
    updateUpNextStrip();
    showCarToast(isShuffle ? '🔀 Случайный порядок: ВКЛ (без повторов)' : '➡️ По порядку: ВКЛ');
  });

  btnRepeat.addEventListener('click', () => {
    if (repeatMode === 'none') {
      repeatMode = 'all';
      showCarToast('🔁 Повтор: Все треки');
    } else if (repeatMode === 'all') {
      repeatMode = 'one';
      showCarToast('🔂 Повтор: Одна песня (1)');
    } else {
      repeatMode = 'none';
      showCarToast('➡️ Повтор: Выключен');
    }
    syncRepeatButtonUI();
    localStorage.setItem('bahoniq_repeat', repeatMode);
  });

  function toggleCurrentTrackFavorite() {
    if (radioMode) {
      const station = getAllRadioStations()[currentRadioIndex];
      if (!station) return;
      const stationId = String(station.id);
      const nowFav = !favoriteRadioIds.has(stationId);
      if (nowFav) favoriteRadioIds.add(stationId); else favoriteRadioIds.delete(stationId);
      saveRadioFavorites();
      btnFav.classList.toggle('active', nowFav);
      btnFav.classList.toggle('fav-active', nowFav);
      if (btnFavDrive) {
        btnFavDrive.classList.toggle('active', nowFav);
        btnFavDrive.classList.toggle('fav-active', nowFav);
      }
      renderRadioList();
      showCarToast(nowFav ? '❤️ Радиостанция добавлена в Избранное' : 'Радиостанция убрана из Избранного');
      return;
    }
    if (currentIndex < 0 || !playlist[currentIndex]) return;
    const track = playlist[currentIndex];
    const tid = Number(track.id);
    const nowFav = !favorites.has(tid);
    if (nowFav) {
      favorites.add(tid);
      showCarToast('❤️ Добавлено в Избранное');
    } else {
      favorites.delete(tid);
      showCarToast('Убрано из Избранного');
    }
    btnFav.classList.toggle('active', nowFav);
    btnFav.classList.toggle('fav-active', nowFav);
    if (btnFavDrive) {
      btnFavDrive.classList.toggle('active', nowFav);
      btnFavDrive.classList.toggle('fav-active', nowFav);
    }
    persistFavorites();
    if (activeTab === 'favorites') renderCatalog();
  }

  btnFav.addEventListener('click', toggleCurrentTrackFavorite);
  if (btnFavDrive) btnFavDrive.addEventListener('click', toggleCurrentTrackFavorite);

  if (btnDownloadActive) {
    btnDownloadActive.addEventListener('click', async () => {
      if (currentIndex < 0) return;
      const track = playlist[currentIndex];
      const tid = Number(track.id);
      if (offlineTrackIds.has(tid)) {
        if (confirm(`Удалить «${track.title}» из локальной памяти устройства?`)) {
          await deleteLocalAudio(tid);
        }
      } else {
        downloadTrackInBackground(track, true);
      }
    });
  }

  // --- Media Session API & Мультируль ---
  function recordDiagnosticCommand(cmdName) {
    if (diagLastCmd) diagLastCmd.textContent = cmdName;
    const now = new Date();
    if (diagCmdTime) {
      diagCmdTime.textContent = now.toTimeString().split(' ')[0] + '.' + String(now.getMilliseconds()).padStart(3, '0');
    }
  }

  function updateMediaSession(track) {
    if (!('mediaSession' in navigator)) return;
    const tid = Number(track.id);
    navigator.mediaSession.metadata = new MediaMetadata({
      title: track.title || 'Музыка',
      artist: track.artist || 'Музыка ДИТ',
      album: track.album || 'BahonIQ Music',
      artwork: [
        { src: `/api/music/tracks/${tid}/cover?v=${encodeURIComponent(track.cover_version || 0)}`, sizes: '512x512', type: 'image/png' }
      ]
    });
    navigator.mediaSession.playbackState = 'playing';
  }

  function setupMediaSession() {
    if (!('mediaSession' in navigator)) return;

    const actionHandlers = [
      ['play', () => {
        recordDiagnosticCommand('PLAY');
        resumeAudioContext();
        audio.play().catch(err => console.warn('MediaSession play failed:', err));
      }],
      ['pause', () => { recordDiagnosticCommand('PAUSE'); audio.pause(); updatePlayButton(false); }],
      ['stop', () => { recordDiagnosticCommand('STOP'); audio.pause(); audio.currentTime = 0; updatePlayButton(false); }],
      ['previoustrack', () => { recordDiagnosticCommand('PREVIOUS TRACK'); playPrevTrack(); }],
      ['nexttrack', () => { recordDiagnosticCommand('NEXT TRACK'); playNextTrack(); }],
      ['seekbackward', () => { recordDiagnosticCommand('SEEK BACKWARD (-10s)'); audio.currentTime = Math.max(0, audio.currentTime - 10); }],
      ['seekforward', () => { recordDiagnosticCommand('SEEK FORWARD (+10s)'); audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 10); }],
      ['seekto', details => {
        recordDiagnosticCommand(`SEEK TO ${formatTime(details.seekTime)}`);
        if (details.seekTime !== undefined && !isNaN(details.seekTime)) {
          const position = Math.max(0, Math.min(audio.duration || details.seekTime, details.seekTime));
          if (details.fastSeek && typeof audio.fastSeek === 'function') audio.fastSeek(position);
          else audio.currentTime = position;
        }
      }]
    ];

    for (const [action, handler] of actionHandlers) {
      try {
        navigator.mediaSession.setActionHandler(action, handler);
      } catch (err) {
        console.warn(`MediaSession action "${action}" not supported:`, err);
      }
    }

    // Аппаратные медиа-кнопки (CAN-шина / Bluetooth HID / Клавиатурные события)
    window.addEventListener('keydown', e => {
      if (e.target && (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA')) {
        return;
      }
      const key = e.key || e.code;
      if (key === 'MediaTrackNext' || key === 'TrackNext' || e.keyCode === 176) {
        e.preventDefault();
        recordDiagnosticCommand('МУЛЬТИРУЛЬ: СЛЕДУЮЩИЙ ТРЕК');
        playNextTrack();
      } else if (key === 'MediaTrackPrevious' || key === 'TrackPrevious' || e.keyCode === 177) {
        e.preventDefault();
        recordDiagnosticCommand('МУЛЬТИРУЛЬ: ПРЕДЫДУЩИЙ ТРЕК');
        playPrevTrack();
      } else if (key === 'MediaPlayPause' || key === 'PlayPause' || e.keyCode === 179) {
        e.preventDefault();
        recordDiagnosticCommand('МУЛЬТИРУЛЬ: ПЛЕЙ/ПАУЗА');
        btnPlay.click();
      } else if (key === 'MediaPlay' || e.keyCode === 126) {
        e.preventDefault();
        recordDiagnosticCommand('МУЛЬТИРУЛЬ: ПЛЕЙ');
        if (audio.paused) btnPlay.click();
      } else if (key === 'MediaPause' || e.keyCode === 127) {
        e.preventDefault();
        recordDiagnosticCommand('МУЛЬТИРУЛЬ: ПАУЗА');
        if (!audio.paused) btnPlay.click();
      } else if (key === 'MediaStop' || e.keyCode === 178) {
        e.preventDefault();
        recordDiagnosticCommand('МУЛЬТИРУЛЬ: СТОП');
        audio.pause();
        updatePlayButton(false);
      }
    });
  }

  let fetchRetryCount = 0;

  // --- Загрузка каталога с сервера ---
  async function fetchCatalog() {
    try {
      const res = await fetch('/api/music/tracks?limit=200');
      if (res.status === 401) {
        authModal.classList.remove('hidden');
        return;
      }
      const data = await res.json();
      if (data && data.tracks && data.tracks.length > 0) {
        playlist = data.tracks;
        filteredPlaylist = [...playlist];
        persistCachedPlaylist();

        await scanOfflineTracks();

        const lastTrackId = Number(localStorage.getItem('bahoniq_last_track_id'));
        let initIdx = 0;
        if (lastTrackId) {
          const found = playlist.findIndex(t => Number(t.id) === lastTrackId);
          if (found >= 0) initIdx = found;
        }

        if (currentIndex === -1 && playlist.length > 0) {
          currentIndex = initIdx;
          const t = playlist[initIdx];
          const tid = Number(t.id);
          trackTitle.textContent = t.title || 'Без названия';
          trackArtist.textContent = t.artist || 'Музыка ДИТ';
          if (metaDurationEl) metaDurationEl.textContent = formatTime(t.duration);
          applyTrackAmbientAndCover(t);
          buildWaveformShapeForTrack(t);
          const isFav = favorites.has(tid);
          btnFav.classList.toggle('active', isFav);
          btnFav.classList.toggle('fav-active', isFav);
          if (btnFavDrive) {
            btnFavDrive.classList.toggle('active', isFav);
            btnFavDrive.classList.toggle('fav-active', isFav);
          }
          const isOff = offlineTrackIds.has(tid);
          if (btnDownloadActive) btnDownloadActive.classList.toggle('active', isOff);
          updateOfflinePill(isOff ? 'offline' : 'stream');
          const savedPos = Number(localStorage.getItem(LAST_POS_STORAGE_KEY) || '0');
          if (t.duration > 0) {
            timeTotal.textContent = formatTime(t.duration);
            if (savedPos > 0 && savedPos < t.duration) {
              timeCurrent.textContent = formatTime(savedPos);
              const ratio = savedPos / t.duration;
              seekBar.value = ratio * 100;
              renderWaveformBars(ratio);
            }
          }
          updateUpNextStrip();
        }

        // Кэшируем метаданные в IndexedDB для работы офлайн
        if (idb) {
          try {
            const tx = idb.transaction('tracks_meta', 'readwrite');
            const store = tx.objectStore('tracks_meta');
            playlist.forEach(t => store.put(t));
          } catch {}
        }

        renderCatalog();
      } else if (fetchRetryCount < 6) {
        fetchRetryCount++;
        setTimeout(fetchCatalog, 3000);
      }
    } catch (err) {
      console.warn('Network offline or catalog fetch failed, relying on local cache:', err);
      if (currentIndex === -1 && playlist.length > 0) {
        const lastTrackId = Number(localStorage.getItem('bahoniq_last_track_id'));
        let initIdx = 0;
        if (lastTrackId) {
          const found = playlist.findIndex(t => Number(t.id) === lastTrackId);
          if (found >= 0) initIdx = found;
        }
        currentIndex = initIdx;
        const t = playlist[initIdx];
        const tid = Number(t.id);
        trackTitle.textContent = t.title || 'Без названия';
        trackArtist.textContent = t.artist || 'Музыка ДИТ';
        if (metaDurationEl) metaDurationEl.textContent = formatTime(t.duration);
        applyTrackAmbientAndCover(t);
        buildWaveformShapeForTrack(t);
        const isFav = favorites.has(tid);
        btnFav.classList.toggle('active', isFav);
        btnFav.classList.toggle('fav-active', isFav);
        if (btnFavDrive) {
          btnFavDrive.classList.toggle('active', isFav);
          btnFavDrive.classList.toggle('fav-active', isFav);
        }
        const isOff = offlineTrackIds.has(tid);
        if (btnDownloadActive) btnDownloadActive.classList.toggle('active', isOff);
        updateOfflinePill(isOff ? 'offline' : 'stream');
        updateUpNextStrip();
        renderCatalog();
      }
    }
  }

  // --- Авторизация устройства ---
  authForm.addEventListener('submit', async e => {
    e.preventDefault();
    const pwd = authPassword.value;
    const body = new FormData();
    body.append('password', pwd);

    const res = await fetch('/api/auth/login', { method: 'POST', body });
    if (res.ok) {
      authModal.classList.add('hidden');
      fetchCatalog();
    } else {
      alert('Неверный пароль Work Center');
    }
  });

  // --- Кнопка «Скачать все» скрыта (треки сохраняются автоматически при прослушивании, как в Telegram) ---
  function syncDownloadAllButton() {
    if (!btnDownloadAll) return;
    btnDownloadAll.style.display = 'none';
  }

  // --- Рендеринг списка музыки в каталоге ---
  function renderCatalog() {
    syncDownloadAllButton();
    updateTabCounters();
    const q = (searchInput.value || '').toLowerCase().trim();
    const matchFn = t => !q || (t.title || '').toLowerCase().includes(q) || (t.artist || '').toLowerCase().includes(q);

    if (activeTab === 'recent') {
      filteredPlaylist = recentTrackIds
        .map(id => playlist.find(t => Number(t.id) === Number(id)))
        .filter(t => t && matchFn(t));
    } else {
      filteredPlaylist = playlist.filter(t => {
        if (!matchFn(t)) return false;
        if (activeTab === 'downloaded') return offlineTrackIds.has(Number(t.id));
        if (activeTab === 'favorites') return favorites.has(Number(t.id));
        return true;
      });
    }

    tracksListEl.innerHTML = '';
    if (filteredPlaylist.length === 0) {
      if (activeTab === 'downloaded') {
        tracksListEl.innerHTML = `
          <div style="text-align: center; padding: 36px 16px; color: var(--text-muted);">
            <div style="font-size: 20px; color: #fff; margin-bottom: 8px;">💾 В памяти устройства пока нет сохранённых треков</div>
            <p style="font-size: 14px; line-height: 1.5; margin-bottom: 16px; color: #cbd5e1;">
              ${playlist.length > 0 ? `Все <strong>${playlist.length} треков</strong> доступны во вкладке <strong>«Все треки»</strong>.<br>Просто включите любую песню — она сразу заиграет онлайн и автоматически сохранится в память (как в Telegram).` : 'Подключитесь к интернету для загрузки списка треков.'}
            </p>
            <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
              <button id="carBtnGoAllTab" class="car-btn-open-list" style="margin: 0;" type="button">📂 Открыть «Все треки»</button>
            </div>
          </div>
        `;
        const goAll = document.getElementById('carBtnGoAllTab');
        if (goAll) goAll.onclick = () => {
          document.querySelectorAll('.car-tab[data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === 'all'));
          activeTab = 'all';
          renderCatalog();
        };
      } else if (activeTab === 'recent') {
        tracksListEl.innerHTML = `
          <div style="text-align: center; padding: 36px 16px; color: var(--text-muted);">
            <div style="font-size: 18px; color: #fff; margin-bottom: 8px;">🕒 История прослушивания пуста</div>
            <p style="font-size: 14px; margin-bottom: 16px;">Здесь автоматически появятся песни, которые вы недавно включали.</p>
            <button id="carBtnRecentGoAll" class="car-btn-open-list" style="margin: 0 auto;" type="button">📂 Открыть «Все треки»</button>
          </div>
        `;
        const goAllRec = document.getElementById('carBtnRecentGoAll');
        if (goAllRec) goAllRec.onclick = () => {
          document.querySelectorAll('.car-tab[data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === 'all'));
          activeTab = 'all';
          renderCatalog();
        };
      } else if (activeTab === 'favorites') {
        tracksListEl.innerHTML = `
          <div style="text-align: center; padding: 36px 16px; color: var(--text-muted);">
            <div style="font-size: 18px; color: #fff; margin-bottom: 8px;">❤️ Нет избранных треков</div>
            <p style="font-size: 14px; margin-bottom: 16px;">Нажмите на сердечко во время прослушивания любого трека.</p>
            <button id="carBtnFavGoAll" class="car-btn-open-list" style="margin: 0 auto;" type="button">📂 Открыть «Все треки»</button>
          </div>
        `;
        const goAllFav = document.getElementById('carBtnFavGoAll');
        if (goAllFav) goAllFav.onclick = () => {
          document.querySelectorAll('.car-tab[data-tab]').forEach(b => b.classList.toggle('active', b.dataset.tab === 'all'));
          activeTab = 'all';
          renderCatalog();
        };
      } else if (playlist.length === 0) {
        tracksListEl.innerHTML = `
          <div style="text-align: center; padding: 36px 16px; color: var(--text-muted);">
            <div style="font-size: 18px; color: #fff; margin-bottom: 8px;">Синхронизация с Telegram...</div>
            <p style="font-size: 14px; margin-bottom: 16px;">Сервер считывает аудиофайлы из канала «Музыка ДИТ». Это занимает несколько секунд.</p>
            <button id="carBtnRetrySync" class="car-btn-open-list" style="margin: 0 auto;" type="button">🔄 Обновить список</button>
          </div>
        `;
        const retryBtn = document.getElementById('carBtnRetrySync');
        if (retryBtn) retryBtn.onclick = () => fetchCatalog();
      } else {
        tracksListEl.innerHTML = `
          <div style="text-align: center; padding: 36px 16px; color: var(--text-muted);">
            <div style="font-size: 18px; color: #fff; margin-bottom: 8px;">🔍 Ничего не найдено</div>
            <p style="font-size: 14px;">Попробуйте ввести другое название или очистить строку поиска.</p>
          </div>
        `;
      }
      return;
    }

    filteredPlaylist.forEach(track => {
      const tid = Number(track.id);
      const isCur = currentIndex >= 0 && Number(playlist[currentIndex]?.id) === tid;
      const isOff = offlineTrackIds.has(tid);
      const isDown = downloadingTrackIds.has(tid);

      const item = document.createElement('div');
      item.className = `car-track-item ${isCur ? 'current' : ''}`;
      item.id = `track-item-${tid}`;

      let badgeHtml = '';
      if (isOff) badgeHtml = `<span class="car-track-badge">✓ Офлайн</span>`;
      else if (isDown) badgeHtml = `<span class="car-track-badge" style="color:var(--accent-gold);background:rgba(250,204,21,0.15);">⏳ Загрузка</span>`;

      item.innerHTML = `
        <div class="car-track-thumb">
          <img src="/api/music/tracks/${tid}/cover?v=${encodeURIComponent(track.cover_version || 0)}" alt="Обложка">
        </div>
        <div class="car-track-info">
          <div class="car-track-name">${escapeHtml(track.title)}</div>
          <div class="car-track-artist">${escapeHtml(track.artist)} · ${formatTime(track.duration)}</div>
        </div>
        ${badgeHtml}
      `;

      item.onclick = () => {
        const targetIdx = playlist.findIndex(t => Number(t.id) === tid);
        if (targetIdx >= 0) {
          playbackContextTab = activeTab;
          shuffleBag = [];
          playTrack(targetIdx);
          catalogDrawer.classList.remove('open');
        }
      };

      tracksListEl.appendChild(item);
    });
  }

  function updateTrackItemBadge(trackId) {
    const tid = Number(trackId);
    if (activeTab === 'downloaded') {
      renderCatalog();
      return;
    }
    const el = document.getElementById(`track-item-${tid}`);
    if (!el) return;
    const isOff = offlineTrackIds.has(tid);
    const isDown = downloadingTrackIds.has(tid);
    let badge = el.querySelector('.car-track-badge');
    if (isOff) {
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'car-track-badge';
        el.appendChild(badge);
      }
      badge.textContent = '✓ Офлайн';
      badge.style.color = '';
      badge.style.background = '';
    } else if (isDown) {
      if (!badge) {
        badge = document.createElement('span');
        badge.className = 'car-track-badge';
        el.appendChild(badge);
      }
      badge.textContent = '⏳ Загрузка';
      badge.style.color = 'var(--accent-gold)';
      badge.style.background = 'rgba(250,204,21,0.15)';
    } else if (badge) {
      badge.remove();
    }
  }

  function highlightCurrentTrackInList() {
    const items = tracksListEl.querySelectorAll('.car-track-item');
    items.forEach(el => el.classList.remove('current'));
    if (currentIndex >= 0 && playlist[currentIndex]) {
      const curEl = document.getElementById(`track-item-${playlist[currentIndex].id}`);
      if (curEl) curEl.classList.add('current');
    }
  }

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({
      '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
    }[c]));
  }

  // --- Переключение вкладок каталога ---
  document.querySelectorAll('.car-tab[data-tab]').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('.car-tab[data-tab]').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeTab = btn.dataset.tab;
      renderCatalog();
    };
  });

  searchInput.addEventListener('input', () => renderCatalog());

  // --- Кнопка пакетного скачивания скрыта (автосохранение работает как в Telegram) ---
  if (btnDownloadAll) {
    btnDownloadAll.style.display = 'none';
  }

  // --- Звуковой процессор (Web Audio API) и сочный бас ---
  let audioCtx = null;
  let audioSourceNode = null;
  let preampNode = null;
  let bassFilter = null;
  let trebleFilter = null;
  let limiterNode = null;
  let isAudioChainInit = false;

  let currentBassGain = parseFloat(localStorage.getItem('bahoniq_bass_gain') || '4.5');
  let currentTrebleGain = parseFloat(localStorage.getItem('bahoniq_treble_gain') || '1.5');
  let currentPreset = localStorage.getItem('bahoniq_sound_preset') || 'juicy';

  const PRESETS = {
    juicy: { bass: 4.5, treble: 1.5 },
    car: { bass: 6.0, treble: 2.5 },
    vocal: { bass: 1.5, treble: 3.5 },
    flat: { bass: 0.0, treble: 0.0 }
  };

  function initAudioDSP() {
    if (isAudioChainInit) return;
    try {
      const AudioCtxClass = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtxClass) {
        console.warn('Web Audio API not supported');
        return;
      }
      if (!audioCtx) audioCtx = new AudioCtxClass();
      if (!audioSourceNode) audioSourceNode = audioCtx.createMediaElementSource(audio);

      preampNode = audioCtx.createGain();

      // LowShelf фильтр на 75 Гц: глубокий сочный бархатный панч
      bassFilter = audioCtx.createBiquadFilter();
      bassFilter.type = 'lowshelf';
      bassFilter.frequency.value = 75;
      bassFilter.gain.value = currentBassGain;

      // HighShelf фильтр на 9000 Гц: воздушность и чистота тарелок/вокала
      trebleFilter = audioCtx.createBiquadFilter();
      trebleFilter.type = 'highshelf';
      trebleFilter.frequency.value = 9000;
      trebleFilter.gain.value = currentTrebleGain;

      // Anti-clipping лимитер для защиты автомобильных динамиков
      limiterNode = audioCtx.createDynamicsCompressor();
      limiterNode.threshold.value = -3;
      limiterNode.knee.value = 2;
      limiterNode.ratio.value = 12;
      limiterNode.attack.value = 0.001;
      limiterNode.release.value = 0.15;

      audioSourceNode.connect(preampNode);
      preampNode.connect(bassFilter);
      bassFilter.connect(trebleFilter);
      trebleFilter.connect(limiterNode);
      limiterNode.connect(audioCtx.destination);

      isAudioChainInit = true;
      updateDSPHeadroom();
    } catch (e) {
      console.warn('Audio DSP init error:', e);
    }
  }

  function updateDSPHeadroom() {
    if (!preampNode || !audioCtx) return;
    const boost = Math.max(0, currentBassGain, currentTrebleGain);
    const attenuationDb = boost > 0 ? -(boost * 0.45) : 0;
    const gain = Math.pow(10, Math.max(-12, attenuationDb) / 20);
    preampNode.gain.setTargetAtTime(gain, audioCtx.currentTime, 0.02);
  }

  function resumeAudioContext() {
    initAudioDSP();
    if (audioCtx && audioCtx.state === 'suspended') {
      audioCtx.resume().catch(() => {});
    }
  }

  function applyPreset(presetKey, save = true) {
    const p = PRESETS[presetKey];
    if (!p) return;
    currentPreset = presetKey;
    presetBtns.forEach(btn => btn.classList.toggle('active', btn.dataset.preset === presetKey));
    setBassGain(p.bass, false);
    setTrebleGain(p.treble, false);
    if (save) {
      localStorage.setItem('bahoniq_sound_preset', presetKey);
    }
  }

  function setBassGain(val, isCustom = true) {
    currentBassGain = Number(val);
    if (bassFilter && audioCtx) {
      bassFilter.gain.setTargetAtTime(currentBassGain, audioCtx.currentTime, 0.02);
    }
    updateDSPHeadroom();
    if (bassValEl) {
      bassValEl.textContent = `${currentBassGain > 0 ? '+' : ''}${currentBassGain.toFixed(1)} dB`;
    }
    if (bassSlider) {
      bassSlider.value = currentBassGain;
      const pct = Math.max(0, Math.min(100, (currentBassGain / 10) * 100));
      bassSlider.style.setProperty('--slider-pct', `${pct.toFixed(1)}%`);
    }
    localStorage.setItem('bahoniq_bass_gain', currentBassGain);
    if (isCustom) {
      currentPreset = 'custom';
      presetBtns.forEach(b => b.classList.remove('active'));
      localStorage.setItem('bahoniq_sound_preset', 'custom');
    }
  }

  function setTrebleGain(val, isCustom = true) {
    currentTrebleGain = Number(val);
    if (trebleFilter && audioCtx) {
      trebleFilter.gain.setTargetAtTime(currentTrebleGain, audioCtx.currentTime, 0.02);
    }
    updateDSPHeadroom();
    if (trebleValEl) {
      trebleValEl.textContent = `${currentTrebleGain > 0 ? '+' : ''}${currentTrebleGain.toFixed(1)} dB`;
    }
    if (trebleSlider) {
      trebleSlider.value = currentTrebleGain;
      const pct = Math.max(0, Math.min(100, ((currentTrebleGain - (-4)) / 12) * 100));
      trebleSlider.style.setProperty('--slider-pct', `${pct.toFixed(1)}%`);
    }
    localStorage.setItem('bahoniq_treble_gain', currentTrebleGain);
    if (isCustom) {
      currentPreset = 'custom';
      presetBtns.forEach(b => b.classList.remove('active'));
      localStorage.setItem('bahoniq_sound_preset', 'custom');
    }
  }

  function setupSoundControls() {
    if (bassSlider) {
      bassSlider.value = currentBassGain;
      bassSlider.addEventListener('input', (e) => {
        resumeAudioContext();
        setBassGain(e.target.value, true);
      });
    }
    if (trebleSlider) {
      trebleSlider.value = currentTrebleGain;
      trebleSlider.addEventListener('input', (e) => {
        resumeAudioContext();
        setTrebleGain(e.target.value, true);
      });
    }
    if (bassValEl) {
      bassValEl.textContent = `${currentBassGain > 0 ? '+' : ''}${currentBassGain.toFixed(1)} dB`;
    }
    if (trebleValEl) {
      trebleValEl.textContent = `${currentTrebleGain > 0 ? '+' : ''}${currentTrebleGain.toFixed(1)} dB`;
    }

    presetBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        resumeAudioContext();
        applyPreset(btn.dataset.preset, true);
      });
    });

    if (currentPreset && PRESETS[currentPreset]) {
      presetBtns.forEach(b => b.classList.toggle('active', b.dataset.preset === currentPreset));
    }

    if (btnSound && soundModal) {
      btnSound.onclick = () => {
        resumeAudioContext();
        soundModal.classList.remove('hidden');
      };
    }
    if (btnCloseSound && soundModal) {
      btnCloseSound.onclick = () => soundModal.classList.add('hidden');
    }
  }

  // --- Открытие/закрытие панелей и СВАЙП (перелистывание пальцем) ---
  if (btnPlaylist && catalogDrawer) btnPlaylist.onclick = () => catalogDrawer.classList.add('open');
  if (btnCloseCatalog && catalogDrawer) btnCloseCatalog.onclick = () => catalogDrawer.classList.remove('open');

  const coverBox = $('carCoverBox');
  const stageEl = document.querySelector('.car-stage');

  // Подключаем живой свайп (перелистывание пальцем или мышью влево/вправо) по обложке и сцене плеера
  function attachSwipeNavigation() {
    const swipeTarget = stageEl || coverBox;
    if (!swipeTarget) return;

    let startX = 0;
    let startY = 0;
    let currentX = 0;
    let tracking = false;
    let didSwipe = false;

    const isInteractiveControl = (el) => {
      if (!el || !el.closest) return false;
      return Boolean(el.closest('button, a, input, #carWaveformBars, .waveform-bars'));
    };

    const onStart = (x, y, target) => {
      if (isInteractiveControl(target)) return;
      startX = x;
      startY = y;
      currentX = x;
      tracking = true;
      didSwipe = false;
      if (coverBox) coverBox.style.transition = 'transform 0.05s linear';
    };

    const onMove = (x, y) => {
      if (!tracking) return;
      currentX = x;
      const dx = x - startX;
      const dy = y - startY;
      if (Math.abs(dx) > 12 && Math.abs(dx) > Math.abs(dy)) {
        didSwipe = true;
        if (coverBox) {
          const clampDx = Math.max(-75, Math.min(75, dx * 0.45));
          coverBox.style.transform = `translateX(${clampDx}px) rotate(${clampDx * 0.04}deg)`;
        }
      }
    };

    const onEnd = (x, y) => {
      if (!tracking) return;
      tracking = false;
      const dx = x - startX;
      const dy = y - startY;

      if (coverBox) {
        coverBox.style.transition = 'transform 0.25s cubic-bezier(0.22, 1, 0.36, 1)';
        coverBox.style.transform = '';
      }

      if (Math.abs(dx) > 45 && Math.abs(dx) > Math.abs(dy) * 1.2) {
        didSwipe = true;
        if (dx < 0) {
          playNextTrack();
        } else {
          playPrevTrack();
        }
      }
    };

    // Touch-события (телефон и экран магнитолы)
    swipeTarget.addEventListener('touchstart', e => {
      if (e.touches && e.touches.length === 1) {
        onStart(e.touches[0].clientX, e.touches[0].clientY, e.target);
      }
    }, { passive: true });

    swipeTarget.addEventListener('touchmove', e => {
      if (e.touches && e.touches.length === 1) {
        onMove(e.touches[0].clientX, e.touches[0].clientY);
      }
    }, { passive: true });

    swipeTarget.addEventListener('touchend', e => {
      if (e.changedTouches && e.changedTouches.length > 0) {
        onEnd(e.changedTouches[0].clientX, e.changedTouches[0].clientY);
      }
    }, { passive: true });

    if (coverBox) {
      coverBox.addEventListener('dragstart', e => e.preventDefault());
    }
    if (coverImg) {
      coverImg.addEventListener('dragstart', e => e.preventDefault());
    }

    // Pointer/Mouse-события (для планшетов, ГУ на Android с Pointer Events и ПК)
    swipeTarget.addEventListener('pointerdown', e => {
      if (e.pointerType === 'touch') return; // уже обработано touchstart
      onStart(e.clientX, e.clientY, e.target);
    });
    window.addEventListener('pointermove', e => {
      if (e.pointerType === 'touch' || !tracking) return;
      onMove(e.clientX, e.clientY);
    });
    window.addEventListener('pointerup', e => {
      if (e.pointerType === 'touch' || !tracking) return;
      onEnd(e.clientX, e.clientY);
    });

    if (coverBox && catalogDrawer) {
      coverBox.onclick = (e) => {
        if (didSwipe) {
          didSwipe = false;
          e.stopPropagation();
          return;
        }
        catalogDrawer.classList.add('open');
      };
    }
  }
  attachSwipeNavigation();

  window.addEventListener('pagehide', () => {
    // Освобождение Blob URL при выгрузке страницы
    memoryBlobUrls.forEach(url => URL.revokeObjectURL(url));
    memoryBlobUrls.clear();
  });

  const metaBox = $('carMetaBox');
  if (metaBox && catalogDrawer) metaBox.onclick = () => catalogDrawer.classList.add('open');
  const btnOpenList = $('carBtnOpenList');
  if (btnOpenList && catalogDrawer) {
    btnOpenList.onclick = (e) => {
      e.stopPropagation();
      catalogDrawer.classList.add('open');
    };
  }

  if (btnDiag && diagModal) btnDiag.onclick = () => diagModal.classList.remove('hidden');
  if (btnCloseDiag && diagModal) btnCloseDiag.onclick = () => diagModal.classList.add('hidden');

  // Закрытие модальных окон при клике вне контента
  [diagModal, soundModal, authModal].forEach(modal => {
    if (!modal) return;
    modal.addEventListener('click', e => {
      if (e.target === modal) modal.classList.add('hidden');
    });
  });

  // Закрытие окон и шторки по клавише Escape
  window.addEventListener('keydown', e => {
    if (e.key === 'Escape') {
      if (soundModal && !soundModal.classList.contains('hidden')) soundModal.classList.add('hidden');
      if (diagModal && !diagModal.classList.contains('hidden')) diagModal.classList.add('hidden');
      if (catalogDrawer && catalogDrawer.classList.contains('open')) catalogDrawer.classList.remove('open');
      if (radioDrawer && radioDrawer.classList.contains('open')) radioDrawer.classList.remove('open');
    }
  });

  // ============================================================
  // ОНЛАЙН-РАДИО: ЗАГРУЗКА, СПИСОК, ВОСПРОИЗВЕДЕНИЕ
  // ============================================================
  function loadCustomRadioStations() {
    try {
      const raw = localStorage.getItem(CUSTOM_RADIO_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      customRadioStations = Array.isArray(arr) ? arr : [];
    } catch {
      customRadioStations = [];
    }
  }

  function loadRadioFavorites() {
    favoriteRadioIds.clear();
    try {
      const values = JSON.parse(localStorage.getItem(RADIO_FAVORITES_KEY) || '[]');
      if (Array.isArray(values)) values.forEach(id => favoriteRadioIds.add(String(id)));
    } catch {}
  }

  function saveRadioFavorites() {
    try { localStorage.setItem(RADIO_FAVORITES_KEY, JSON.stringify([...favoriteRadioIds])); } catch {}
  }

  function saveCustomRadioStations() {
    try {
      localStorage.setItem(CUSTOM_RADIO_KEY, JSON.stringify(customRadioStations));
    } catch {}
  }

  function getAllRadioStations() {
    return [...radioStations, ...customRadioStations];
  }

  function getFilteredRadioStations() {
    const all = getAllRadioStations();
    let list = all;
    if (radioFilter === 'KZ') list = list.filter(s => s.country === 'KZ' && !s.custom);
    else if (radioFilter === 'RU') list = list.filter(s => s.country === 'RU' && !s.custom);
    else if (radioFilter === 'favorites') list = list.filter(s => favoriteRadioIds.has(String(s.id)));
    else if (radioFilter === 'custom') list = list.filter(s => s.custom);
    if (radioFilter === 'KZ' && radioSubgroup !== 'all') list = list.filter(s => s.subgroup === radioSubgroup);
    const query = String(radioSearch?.value || '').trim().toLocaleLowerCase('ru');
    if (query) {
      list = list.filter(station => [station.name, station.freq, station.genre, station.country, station.description, ...(station.aliases || [])]
        .filter(Boolean).join(' ').toLocaleLowerCase('ru').includes(query));
    }
    return list;
  }

  function updateRadioCounts() {
    const all = getAllRadioStations();
    const counts = {
      all: all.length,
      KZ: radioStations.filter(s => s.country === 'KZ').length,
      RU: radioStations.filter(s => s.country === 'RU').length,
      favorites: all.filter(s => favoriteRadioIds.has(String(s.id))).length,
      custom: customRadioStations.length,
    };
    radioTabsEl?.querySelectorAll('[data-radio-count]').forEach(el => {
      el.textContent = String(counts[el.dataset.radioCount] || 0);
    });
    if (radioSubgroupsEl) radioSubgroupsEl.classList.toggle('hidden', radioFilter !== 'KZ');
  }

  async function fetchRadioStations() {
    loadCustomRadioStations();
    loadRadioFavorites();
    try {
      const res = await fetch('/api/music/radio/stations');
      if (!res.ok) throw new Error('HTTP ' + res.status);
      const data = await res.json();
      radioStations = Array.isArray(data.stations) ? data.stations : [];
    } catch (err) {
      console.warn('Не удалось загрузить радиостанции:', err);
    }
    renderRadioList();
  }

  function renderRadioList() {
    if (!radioListEl) return;
    const all = getAllRadioStations();
    const list = getFilteredRadioStations();
    updateRadioCounts();
    if (list.length === 0) {
      const message = radioFilter === 'favorites' ? 'Здесь появятся ваши любимые станции' : 'Станции не найдены';
      radioListEl.innerHTML = `<div class="car-radio-empty">${message}</div>`;
      return;
    }
    radioListEl.innerHTML = '';
    list.forEach(station => {
      const globalIdx = all.findIndex(s => s.id === station.id);
      const isPlayingThis = radioMode && globalIdx === currentRadioIndex;
      const isFavorite = favoriteRadioIds.has(String(station.id));
      const playable = station.available !== false && !!station.stream_url;
      const initials = String(station.name || 'FM').split(/\s+/).map(v => v[0]).join('').slice(0, 2).toUpperCase();
      const item = document.createElement('article');
      item.className = 'car-radio-item' + (isPlayingThis ? ' active' : '');
      item.dataset.stationId = station.id;
      item.innerHTML = `
        <div class="car-radio-monogram" aria-hidden="true">${escapeHtml(initials)}</div>
        <div class="car-radio-copy">
          <div class="car-radio-name">
            ${isPlayingThis ? '<span class="car-radio-live-wave"><i></i><i></i><i></i></span>' : ''}${escapeHtml(station.name)}
          </div>
          <div class="car-radio-meta">
            ${escapeHtml(station.freq || 'Online')} · ${escapeHtml(station.genre || 'Радио')}
          </div>
          ${!playable ? `<div class="car-radio-unavailable">${escapeHtml(station.unavailableReason || 'Поток временно недоступен')}</div>` : ''}
        </div>
        <div class="car-radio-actions">
          <span class="car-radio-badge ${isPlayingThis ? 'live' : ''}">${isPlayingThis ? 'LIVE' : (station.country || 'FM')}</span>
          <button class="car-radio-fav-btn ${isFavorite ? 'active' : ''}" type="button" title="${isFavorite ? 'Убрать из избранного' : 'В избранное'}" aria-label="Избранное">${isFavorite ? '♥' : '♡'}</button>
          <button class="car-radio-play-btn" type="button" ${playable ? '' : 'disabled'} title="${playable ? (isPlayingThis && !audio.paused ? 'Пауза' : 'Слушать') : 'Поток недоступен'}">${isPlayingThis && !audio.paused ? 'Ⅱ' : '▶'}</button>
          ${station.custom ? '<button class="car-radio-edit-btn" type="button" title="Редактировать">✎</button><button class="car-radio-del-btn" type="button" title="Удалить">✕</button>' : ''}
        </div>
      `;
      item.addEventListener('click', e => {
        const favBtn = e.target.closest('.car-radio-fav-btn');
        if (favBtn) {
          e.stopPropagation();
          if (isFavorite) favoriteRadioIds.delete(String(station.id)); else favoriteRadioIds.add(String(station.id));
          saveRadioFavorites();
          renderRadioList();
          return;
        }
        if (e.target.closest('.car-radio-edit-btn')) {
          e.stopPropagation();
          openRadioModal(station);
          return;
        }
        if (e.target.closest('.car-radio-del-btn')) {
          e.stopPropagation();
          if (!window.confirm(`Удалить станцию «${station.name}»?`)) return;
          customRadioStations = customRadioStations.filter(s => s.id !== station.id);
          favoriteRadioIds.delete(String(station.id));
          saveCustomRadioStations();
          saveRadioFavorites();
          if (isPlayingThis) exitRadioMode();
          else renderRadioList();
          return;
        }
        if (!playable) return;
        if (isPlayingThis) {
          if (audio.paused) audio.play().catch(() => {}); else audio.pause();
          renderRadioList();
          return;
        }
        playRadioStation(globalIdx);
      });
      radioListEl.appendChild(item);
    });
  }

  function stopRadioMetadataPolling() {
    if (radioMetadataTimer) clearInterval(radioMetadataTimer);
    radioMetadataTimer = null;
  }

  async function refreshRadioMetadata(station) {
    if (!radioMode || !station || station.custom) return;
    try {
      const res = await fetch(`/api/music/radio/metadata/${encodeURIComponent(station.id)}`, { cache: 'no-store' });
      if (!res.ok) return;
      const meta = await res.json();
      if (!radioMode || getAllRadioStations()[currentRadioIndex]?.id !== station.id) return;
      const label = [meta.artist, meta.title].filter(Boolean).join(' — ');
      trackArtist.textContent = label || `${station.freq || 'FM'} · ${station.genre || 'Радио'}`;
      if (label && 'mediaSession' in navigator && navigator.mediaSession.metadata) {
        navigator.mediaSession.metadata = new MediaMetadata({ title: meta.title || station.name, artist: meta.artist || station.name, album: station.name });
      }
    } catch {}
  }

  function startRadioMetadataPolling(station) {
    stopRadioMetadataPolling();
    refreshRadioMetadata(station);
    radioMetadataTimer = setInterval(() => refreshRadioMetadata(station), 15000);
  }

  function setRadioUiMode(enabled) {
    progressWrap?.classList.toggle('radio-live-mode', enabled);
    controlsSub?.classList.toggle('radio-live-mode', enabled);
    waveformBarsEl?.classList.toggle('radio-live-mode', enabled);
    if (waveformBarsEl) waveformBarsEl.title = enabled ? 'Живой сигнал радиостанции' : 'Нажмите или проведите для перемотки';
    if (btnRepeat) btnRepeat.hidden = enabled;
    if (btnDownloadActive) btnDownloadActive.hidden = enabled;
    if (!enabled) renderWaveformBars(currentProgressRatio);
  }

  function playRadioStation(index) {
    const all = getAllRadioStations();
    if (index < 0 || index >= all.length) return;
    const station = all[index];
    if (station.available === false || !station.stream_url) {
      showToast('Поток этой станции пока недоступен');
      return;
    }
    radioMode = true;
    setRadioUiMode(true);
    currentRadioIndex = index;
    try { localStorage.setItem(LAST_RADIO_KEY, String(station.id)); } catch {}
    playRequestId++;

    resumeAudioContext();

    if (btnRadio) btnRadio.classList.add('active');
    trackTitle.textContent = station.name;
    trackArtist.textContent = `${station.freq || 'FM'} · ${station.genre || 'Радио'}`;
    if (metaDurationEl) metaDurationEl.textContent = 'LIVE';
    if (inlineStatusEl) {
      inlineStatusEl.textContent = '● прямой эфир';
      inlineStatusEl.classList.add('live-air');
    }
    timeCurrent.textContent = 'LIVE';
    timeTotal.textContent = '● ЭФИР';
    seekBar.value = 0;

    applyTrackAmbientAndCover({ title: station.name, artist: station.genre || 'Radio', id: station.id });
    renderWaveformBars(0);
    const stationFavorite = favoriteRadioIds.has(String(station.id));
    btnFav?.classList.toggle('active', stationFavorite);
    btnFav?.classList.toggle('fav-active', stationFavorite);
    if (diagCurrentTrack) diagCurrentTrack.textContent = `📻 ${station.name}`;

    let nextStation = station;
    for (let step = 1; step <= all.length; step++) {
      const candidate = all[(index + step) % all.length];
      if (candidate.available !== false && candidate.stream_url) { nextStation = candidate; break; }
    }
    if (upNextStrip && upNextTitleEl) {
      upNextStrip.classList.remove('hidden');
      upNextTitleEl.textContent = `📻 ${nextStation.name}`;
      if (upNextMetaEl) upNextMetaEl.textContent = `(${nextStation.freq || 'FM'})`;
    }

    clearTimeout(radioPlayTimeout);
    audio.pause();
    audio.src = station.stream_url;
    audio.load();
    audio.play().catch(err => {
      console.warn('Radio play failed:', err);
      showToast('Станция временно недоступна');
      btnPlay.classList.remove('loading');
    });
    btnPlay.classList.add('loading');
    radioPlayTimeout = setTimeout(() => {
      if (radioMode && audio.readyState < 2) {
        btnPlay.classList.remove('loading');
        showToast('Слишком долгое подключение к станции');
      }
    }, 12000);
    startRadioMetadataPolling(station);

    if ('mediaSession' in navigator) {
      try {
        navigator.mediaSession.metadata = new MediaMetadata({
          title: station.name,
          artist: `${station.freq || 'FM'} · BahonIQ Радио`,
          album: 'Прямой эфир',
        });
      } catch {}
    }

    renderRadioList();
    if (radioDrawer) radioDrawer.classList.remove('open');
  }

  function playNextRadioStation() {
    const all = getAllRadioStations();
    if (all.length === 0) return;
    if (isShuffle) {
      const playable = all.map((station, idx) => ({ station, idx })).filter(v => v.idx !== currentRadioIndex && v.station.available !== false && v.station.stream_url);
      if (playable.length) return playRadioStation(playable[Math.floor(Math.random() * playable.length)].idx);
    }
    for (let step = 1; step <= all.length; step++) {
      const next = (currentRadioIndex + step) % all.length;
      if (all[next].available !== false && all[next].stream_url) return playRadioStation(next);
    }
  }

  function playPrevRadioStation() {
    const all = getAllRadioStations();
    if (all.length === 0) return;
    for (let step = 1; step <= all.length; step++) {
      const prev = (currentRadioIndex - step + all.length) % all.length;
      if (all[prev].available !== false && all[prev].stream_url) return playRadioStation(prev);
    }
  }

  function exitRadioMode() {
    stopRadioMetadataPolling();
    clearTimeout(radioPlayTimeout);
    radioMode = false;
    setRadioUiMode(false);
    currentRadioIndex = -1;
    if (btnRadio) btnRadio.classList.remove('active');
    if (inlineStatusEl) inlineStatusEl.classList.remove('live-air');
    if (radioDrawer) radioDrawer.classList.remove('open');
    renderRadioList();
    if (playlist.length > 0) {
      playTrack(currentIndex >= 0 ? currentIndex : 0, false);
    } else {
      audio.pause();
      audio.removeAttribute('src');
      updatePlayButton(false);
    }
  }

  if (btnRadio && radioDrawer) {
    btnRadio.addEventListener('click', async () => {
      if (catalogDrawer) catalogDrawer.classList.remove('open');
      radioDrawer.classList.toggle('open');
      if (radioStations.length === 0) {
        await fetchRadioStations();
      } else {
        renderRadioList();
      }
    });
  }

  if (btnCloseRadio && radioDrawer) {
    btnCloseRadio.addEventListener('click', () => radioDrawer.classList.remove('open'));
  }

  if (btnExitRadio) {
    btnExitRadio.addEventListener('click', () => exitRadioMode());
  }

  if (radioTabsEl) {
    radioTabsEl.addEventListener('click', e => {
      const btn = e.target.closest('.car-tab');
      if (!btn) return;
      radioFilter = btn.dataset.radioFilter || 'all';
      if (radioFilter !== 'KZ') radioSubgroup = 'all';
      radioTabsEl.querySelectorAll('.car-tab').forEach(b => b.classList.toggle('active', b === btn));
      renderRadioList();
    });
  }

  radioSubgroupsEl?.addEventListener('click', e => {
    const btn = e.target.closest('[data-radio-subgroup]');
    if (!btn) return;
    radioSubgroup = btn.dataset.radioSubgroup || 'all';
    radioSubgroupsEl.querySelectorAll('button').forEach(b => b.classList.toggle('active', b === btn));
    renderRadioList();
  });

  radioSearch?.addEventListener('input', () => {
    radioSearchClear?.classList.toggle('hidden', !radioSearch.value);
    renderRadioList();
  });
  radioSearchClear?.addEventListener('click', () => {
    radioSearch.value = '';
    radioSearchClear.classList.add('hidden');
    radioSearch.focus();
    renderRadioList();
  });

  function openRadioModal(station = null) {
    customRadioEditId.value = station?.id || '';
    customRadioName.value = station?.name || '';
    customRadioUrl.value = station?.raw_url || '';
    customRadioFreq.value = station?.freq === 'Своя' ? '' : (station?.freq || '');
    customRadioGenre.value = station?.genre === 'Интернет-радио' ? '' : (station?.genre || '');
    customRadioCountry.value = station?.country === 'custom' ? '' : (station?.country || '');
    radioFormError.textContent = '';
    radioModal?.classList.remove('hidden');
    setTimeout(() => customRadioName?.focus(), 0);
  }
  function closeRadioModal() { radioModal?.classList.add('hidden'); }
  btnAddRadio?.addEventListener('click', () => openRadioModal());
  btnCloseRadioModal?.addEventListener('click', closeRadioModal);
  radioModal?.addEventListener('click', e => { if (e.target === radioModal) closeRadioModal(); });

  if (customRadioForm) {
    customRadioForm.addEventListener('submit', e => {
      e.preventDefault();
      const name = String(customRadioName?.value || '').trim();
      const rawUrl = String(customRadioUrl?.value || '').trim();
      if (!name || !rawUrl) return;
      let parsed;
      try { parsed = new URL(rawUrl); } catch { radioFormError.textContent = 'Введите корректный URL потока'; return; }
      if (!['http:', 'https:'].includes(parsed.protocol)) { radioFormError.textContent = 'Поддерживаются только HTTP и HTTPS'; return; }
      const lowerUrl = (parsed.pathname + parsed.search + (parsed.port ? ':' + parsed.port : '')).toLowerCase();
      const isDirectStream = /\.(mp3|aac|aacp|ogg|opus|flac|m3u8|pls)(\?|$)/.test(parsed.pathname.toLowerCase())
        || /:(8000|8008|8030|8080|8443|9000|9036)/.test(rawUrl)
        || /(\/stream|\/live|\/icecast|\/icecast\.audio|\/radio|\/listen|\/bc\/live)/.test(lowerUrl);
      if (!isDirectStream) {
        radioFormError.textContent = 'Нужен прямой аудиопоток (.mp3, .aac, .m3u8 или Icecast), а не адрес сайта';
        return;
      }
      const editId = String(customRadioEditId?.value || '');
      const duplicate = getAllRadioStations().find(s => s.id !== editId && (String(s.name).toLocaleLowerCase('ru') === name.toLocaleLowerCase('ru') || s.raw_url === rawUrl));
      if (duplicate) { radioFormError.textContent = 'Такая станция или URL уже существуют'; return; }
      const station = {
        id: editId || ('custom_' + Date.now()),
        name,
        freq: String(customRadioFreq?.value || '').trim() || 'Online',
        genre: String(customRadioGenre?.value || '').trim() || 'Интернет-радио',
        country: String(customRadioCountry?.value || '').trim() || 'Моя',
        custom: true,
        available: true,
        raw_url: rawUrl,
        stream_url: `/api/music/radio/proxy?url=${encodeURIComponent(rawUrl)}`,
      };
      if (editId) customRadioStations = customRadioStations.map(s => s.id === editId ? station : s);
      else customRadioStations.push(station);
      saveCustomRadioStations();
      customRadioForm.reset();
      closeRadioModal();
      radioFilter = 'custom';
      if (radioTabsEl) {
        radioTabsEl.querySelectorAll('.car-tab').forEach(b => b.classList.toggle('active', b.dataset.radioFilter === 'custom'));
      }
      renderRadioList();
      showToast(`Станция «${name}» сохранена`);
    });
  }

  // --- Старт приложения ---
  async function init() {
    // Скрываем кнопку скачивания APK, если плеер уже открыт внутри установленного приложения или WebView
    const btnApk = $('carBtnApk');
    const isStandaloneApp = window.matchMedia('(display-mode: standalone)').matches ||
      window.navigator.standalone === true ||
      /; wv\)/.test(navigator.userAgent || '');
    if (btnApk && isStandaloneApp) {
      btnApk.style.display = 'none';
    }

    if ('serviceWorker' in navigator) {
      navigator.serviceWorker.register('/music/sw.js', { scope: '/music/' })
        .then(reg => reg.update().catch(() => {}))
        .catch(() => {});
    }
    loadOfflineTrackIdsFromStorage();
    loadFavoritesFromStorage();
    loadRecentTracksFromStorage();
    loadCachedPlaylistFromStorage();
    if (playlist.length > 0) {
      renderCatalog();
    }
    await initIndexedDB();
    // Подтягиваем избранное из IndexedDB, если оно там было сохранено
    if (idb && idb.objectStoreNames.contains('favorites')) {
      await new Promise(resolve => {
        try {
          const tx = idb.transaction('favorites', 'readonly');
          const req = tx.objectStore('favorites').getAll();
          req.onsuccess = () => {
            (req.result || []).forEach(r => {
              if (r && r.id) favorites.add(Number(r.id));
            });
            resolve();
          };
          req.onerror = () => resolve();
        } catch {
          resolve();
        }
      });
    }
    await migrateLegacyIndexedDB();
    await initOPFS();
    setupMediaSession();
    setupSoundControls();
    await scanOfflineTracks();
    await fetchCatalog();
  }

  init();
})();
