(() => {
  'use strict';

  // --- Элементы интерфейса ---
  const $ = id => document.getElementById(id);
  const audio = $('carAudioElement');
  const btnPlay = $('carBtnPlay');
  const iconPlay = $('carIconPlay');
  const iconPause = $('carIconPause');
  const btnPrev = $('carBtnPrev');
  const btnNext = $('carBtnNext');
  const btnShuffle = $('carBtnShuffle');
  const btnRepeat = $('carBtnRepeat');
  const btnFav = $('carBtnFav');
  const btnDownloadActive = $('carBtnDownloadActive');
  const seekBar = $('carSeekBar');
  const timeCurrent = $('carTimeCurrent');
  const timeTotal = $('carTimeTotal');
  const trackTitle = $('carTrackTitle');
  const trackArtist = $('carTrackArtist');
  const coverImg = $('carCoverImg');
  const offlineStatus = $('carOfflineStatus');
  const offlineText = $('carOfflineText');

  const btnPlaylist = $('carBtnPlaylist');
  const btnCloseCatalog = $('carBtnCloseCatalog');
  const catalogDrawer = $('carCatalogDrawer');
  const searchInput = $('carSearchInput');
  const tracksListEl = $('carTracksList');

  const btnDiag = $('carBtnDiag');
  const btnCloseDiag = $('carBtnCloseDiag');
  const diagModal = $('carDiagModal');
  const diagLastCmd = $('diagLastCmd');
  const diagCmdTime = $('diagCmdTime');
  const diagAudioStatus = $('diagAudioStatus');
  const diagCurrentTrack = $('diagCurrentTrack');

  const authModal = $('carAuthModal');
  const authForm = $('carAuthForm');
  const authPassword = $('carAuthPassword');

  // --- Состояние плеера ---
  let playlist = [];
  let filteredPlaylist = [];
  let currentIndex = -1;
  let isShuffle = false;
  let repeatMode = 'none'; // 'none' | 'all' | 'one'
  const favorites = new Set();
  const offlineTrackIds = new Set();
  const downloadingTrackIds = new Set();
  let currentBlobUrl = null;
  let activeTab = 'all';

  // --- Регистрация Service Worker ---
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/music/sw.js', { scope: '/music/' })
      .catch(err => console.log('Music SW registration error:', err));
  }

  // --- Запрос постоянного хранилища ---
  if (navigator.storage && navigator.storage.persist) {
    navigator.storage.persist().then(persistent => {
      console.log('Storage persistence:', persistent ? 'Granted' : 'Default');
    }).catch(() => {});
  }

  // --- Локальное хранилище: IndexedDB ---
  const DB_NAME = 'BahonIQ_Music_DB';
  const DB_VERSION = 1;
  let idb = null;

  function initIndexedDB() {
    return new Promise((resolve, reject) => {
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
      req.onerror = e => reject(e);
    });
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
  }

  async function saveAudioLocally(trackId, blob) {
    // 1. Попытка в OPFS
    if (opfsRoot) {
      try {
        const fileHandle = await opfsRoot.getFileHandle(`track_${trackId}.bin`, { create: true });
        const writable = await fileHandle.createWritable();
        await writable.write(blob);
        await writable.close();
        offlineTrackIds.add(trackId);
        return true;
      } catch (err) {
        console.warn('OPFS write failed, falling back to IndexedDB:', err);
      }
    }

    // 2. Fallback в IndexedDB
    if (idb) {
      return new Promise(resolve => {
        try {
          const tx = idb.transaction('tracks_blobs', 'readwrite');
          tx.objectStore('tracks_blobs').put({ id: trackId, blob: blob, size: blob.size, date: Date.now() });
          tx.oncomplete = () => {
            offlineTrackIds.add(trackId);
            resolve(true);
          };
          tx.onerror = () => resolve(false);
        } catch {
          resolve(false);
        }
      });
    }
    return false;
  }

  async function getLocalAudioBlob(trackId) {
    if (opfsRoot) {
      try {
        const fileHandle = await opfsRoot.getFileHandle(`track_${trackId}.bin`);
        const file = await fileHandle.getFile();
        if (file && file.size > 0) return file;
      } catch {}
    }

    if (idb) {
      return new Promise(resolve => {
        try {
          const tx = idb.transaction('tracks_blobs', 'readonly');
          const req = tx.objectStore('tracks_blobs').get(trackId);
          req.onsuccess = () => resolve(req.result ? req.result.blob : null);
          req.onerror = () => resolve(null);
        } catch {
          resolve(null);
        }
      });
    }
    return null;
  }

  async function deleteLocalAudio(trackId) {
    if (opfsRoot) {
      try {
        await opfsRoot.removeEntry(`track_${trackId}.bin`);
      } catch {}
    }
    if (idb) {
      try {
        const tx = idb.transaction('tracks_blobs', 'readwrite');
        tx.objectStore('tracks_blobs').delete(trackId);
      } catch {}
    }
    offlineTrackIds.delete(trackId);
    updateTrackItemBadge(trackId);
    if (currentIndex >= 0 && playlist[currentIndex]?.id === trackId) {
      updateOfflinePill('stream');
    }
  }

  async function scanOfflineTracks() {
    if (idb) {
      try {
        const tx = idb.transaction('tracks_blobs', 'readonly');
        const req = tx.objectStore('tracks_blobs').getAllKeys();
        req.onsuccess = () => {
          (req.result || []).forEach(k => offlineTrackIds.add(Number(k)));
          renderCatalog();
        };
      } catch {}
    }
    // Также считываем метаданные из IDB на случай открытия офлайн
    if (idb) {
      try {
        const tx = idb.transaction('tracks_meta', 'readonly');
        const req = tx.objectStore('tracks_meta').getAll();
        req.onsuccess = () => {
          if (playlist.length === 0 && req.result && req.result.length > 0) {
            playlist = req.result;
            filteredPlaylist = [...playlist];
            renderCatalog();
          }
        };
      } catch {}
    }
  }

  // --- Форматирование времени ---
  function formatTime(seconds) {
    if (!seconds || isNaN(seconds) || seconds < 0) return '0:00';
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? '0' : ''}${s}`;
  }

  // --- Статус индикатора офлайн ---
  function updateOfflinePill(state, progress = 0) {
    offlineStatus.className = 'car-offline-pill';
    if (state === 'offline') {
      offlineStatus.classList.add('offline');
      offlineText.textContent = 'Офлайн (в памяти)';
    } else if (state === 'stream') {
      offlineStatus.classList.add('stream');
      offlineText.textContent = 'Онлайн стриминг';
    } else if (state === 'downloading') {
      offlineStatus.classList.add('downloading');
      offlineText.textContent = `Сохранение ${progress}%`;
    }
  }

  // --- Загрузка трека в фоне при первом прослушивании ---
  async function downloadTrackInBackground(track) {
    if (!track || offlineTrackIds.has(track.id) || downloadingTrackIds.has(track.id)) {
      return;
    }
    downloadingTrackIds.add(track.id);
    updateTrackItemBadge(track.id);

    try {
      const resp = await fetch(`/api/music/tracks/${track.id}/download`);
      if (!resp.ok) throw new Error('Download failed');

      const contentLength = Number(resp.headers.get('Content-Length')) || track.file_size || 0;
      const reader = resp.body.getReader();
      const chunks = [];
      let receivedBytes = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        chunks.push(value);
        receivedBytes += value.length;

        if (contentLength > 0 && currentIndex >= 0 && playlist[currentIndex]?.id === track.id) {
          const pct = Math.min(99, Math.round((receivedBytes / contentLength) * 100));
          updateOfflinePill('downloading', pct);
        }
      }

      const completeBlob = new Blob(chunks, { type: track.mime_type || 'audio/mpeg' });

      // Валидация размера
      if (completeBlob.size > 0 && (contentLength === 0 || completeBlob.size === contentLength || Math.abs(completeBlob.size - contentLength) < 1024)) {
        await saveAudioLocally(track.id, completeBlob);
        if (currentIndex >= 0 && playlist[currentIndex]?.id === track.id) {
          updateOfflinePill('offline');
        }
      } else {
        console.warn('Size mismatch, discarded incomplete file');
      }
    } catch (err) {
      console.warn('Background download error:', err);
    } finally {
      downloadingTrackIds.delete(track.id);
      updateTrackItemBadge(track.id);
    }
  }

  // --- Воспроизведение трека ---
  async function playTrack(index) {
    if (index < 0 || index >= playlist.length) return;
    currentIndex = index;
    const track = playlist[currentIndex];

    trackTitle.textContent = track.title || 'Без названия';
    trackArtist.textContent = track.artist || 'Музыка ДИТ';
    coverImg.src = `/api/music/tracks/${track.id}/cover`;
    diagCurrentTrack.textContent = `${track.artist} — ${track.title}`;

    btnFav.classList.toggle('active', favorites.has(track.id));
    btnDownloadActive.classList.toggle('active', offlineTrackIds.has(track.id));

    // Очищаем предыдущий Blob URL
    if (currentBlobUrl) {
      URL.revokeObjectURL(currentBlobUrl);
      currentBlobUrl = null;
    }

    // Проверяем наличие офлайн-копии
    const localBlob = await getLocalAudioBlob(track.id);
    if (localBlob) {
      currentBlobUrl = URL.createObjectURL(localBlob);
      audio.src = currentBlobUrl;
      updateOfflinePill('offline');
    } else {
      // Стриминг с сервера через Range
      audio.src = `/api/music/tracks/${track.id}/stream`;
      updateOfflinePill('stream');
      // Параллельно запускаем фоновую загрузку полного файла
      downloadTrackInBackground(track);
    }

    try {
      await audio.play();
      updatePlayButton(true);
    } catch (err) {
      console.warn('Audio play interrupted:', err);
      updatePlayButton(false);
    }

    updateMediaSession(track);
    highlightCurrentTrackInList();
  }

  function updatePlayButton(playing) {
    if (playing) {
      iconPlay.classList.add('hidden');
      iconPause.classList.remove('hidden');
      diagAudioStatus.textContent = 'Воспроизведение';
    } else {
      iconPlay.classList.remove('hidden');
      iconPause.classList.add('hidden');
      diagAudioStatus.textContent = 'Пауза';
    }
  }

  function playNextTrack() {
    if (playlist.length === 0) return;
    if (isShuffle) {
      const nextIdx = Math.floor(Math.random() * playlist.length);
      playTrack(nextIdx);
    } else {
      const nextIdx = (currentIndex + 1) % playlist.length;
      playTrack(nextIdx);
    }
  }

  function playPrevTrack() {
    if (playlist.length === 0) return;
    if (audio.currentTime > 3) {
      audio.currentTime = 0;
      return;
    }
    const prevIdx = (currentIndex - 1 + playlist.length) % playlist.length;
    playTrack(prevIdx);
  }

  // --- События HTML5 Audio ---
  audio.addEventListener('timeupdate', () => {
    if (!isNaN(audio.duration) && audio.duration > 0) {
      const pct = (audio.currentTime / audio.duration) * 100;
      seekBar.value = pct;
      timeCurrent.textContent = formatTime(audio.currentTime);
      timeTotal.textContent = formatTime(audio.duration);

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

  audio.addEventListener('ended', () => {
    if (repeatMode === 'one') {
      audio.currentTime = 0;
      audio.play();
    } else if (repeatMode === 'all' || currentIndex < playlist.length - 1) {
      playNextTrack();
    } else {
      updatePlayButton(false);
    }
  });

  seekBar.addEventListener('input', () => {
    if (!isNaN(audio.duration) && audio.duration > 0) {
      audio.currentTime = (seekBar.value / 100) * audio.duration;
    }
  });

  btnPlay.addEventListener('click', () => {
    if (currentIndex === -1 && playlist.length > 0) {
      playTrack(0);
      return;
    }
    if (audio.paused) {
      audio.play();
      updatePlayButton(true);
    } else {
      audio.pause();
      updatePlayButton(false);
    }
  });

  btnPrev.addEventListener('click', playPrevTrack);
  btnNext.addEventListener('click', playNextTrack);

  btnShuffle.addEventListener('click', () => {
    isShuffle = !isShuffle;
    btnShuffle.classList.toggle('active', isShuffle);
  });

  btnRepeat.addEventListener('click', () => {
    if (repeatMode === 'none') {
      repeatMode = 'all';
      btnRepeat.classList.add('active');
      btnRepeat.title = 'Повтор: Все треки';
    } else if (repeatMode === 'all') {
      repeatMode = 'one';
      btnRepeat.classList.add('active');
      btnRepeat.title = 'Повтор: Один трек';
    } else {
      repeatMode = 'none';
      btnRepeat.classList.remove('active');
      btnRepeat.title = 'Повтор: Выключен';
    }
  });

  btnFav.addEventListener('click', () => {
    if (currentIndex < 0) return;
    const track = playlist[currentIndex];
    if (favorites.has(track.id)) {
      favorites.delete(track.id);
      btnFav.classList.remove('active');
    } else {
      favorites.add(track.id);
      btnFav.classList.add('active');
    }
  });

  btnDownloadActive.addEventListener('click', async () => {
    if (currentIndex < 0) return;
    const track = playlist[currentIndex];
    if (offlineTrackIds.has(track.id)) {
      if (confirm(`Удалить «${track.title}» из локальной памяти?`)) {
        await deleteLocalAudio(track.id);
      }
    } else {
      downloadTrackInBackground(track);
    }
  });

  // --- Media Session API & Мультируль ---
  function recordDiagnosticCommand(cmdName) {
    diagLastCmd.textContent = cmdName;
    const now = new Date();
    diagCmdTime.textContent = now.toTimeString().split(' ')[0] + '.' + String(now.getMilliseconds()).padStart(3, '0');
  }

  function updateMediaSession(track) {
    if (!('mediaSession' in navigator)) return;

    navigator.mediaSession.metadata = new MediaMetadata({
      title: track.title || 'Музыка',
      artist: track.artist || 'Музыка ДИТ',
      album: track.album || 'BahonIQ Music',
      artwork: [
        { src: `/api/music/tracks/${track.id}/cover`, sizes: '96x96', type: 'image/svg+xml' },
        { src: `/api/music/tracks/${track.id}/cover`, sizes: '128x128', type: 'image/svg+xml' },
        { src: `/api/music/tracks/${track.id}/cover`, sizes: '256x256', type: 'image/svg+xml' },
        { src: `/api/music/tracks/${track.id}/cover`, sizes: '512x512', type: 'image/svg+xml' }
      ]
    });
    navigator.mediaSession.playbackState = 'playing';
  }

  function setupMediaSession() {
    if (!('mediaSession' in navigator)) return;

    const actionHandlers = [
      ['play', () => { recordDiagnosticCommand('PLAY'); audio.play(); updatePlayButton(true); }],
      ['pause', () => { recordDiagnosticCommand('PAUSE'); audio.pause(); updatePlayButton(false); }],
      ['stop', () => { recordDiagnosticCommand('STOP'); audio.pause(); audio.currentTime = 0; updatePlayButton(false); }],
      ['previoustrack', () => { recordDiagnosticCommand('PREVIOUS TRACK'); playPrevTrack(); }],
      ['nexttrack', () => { recordDiagnosticCommand('NEXT TRACK'); playNextTrack(); }],
      ['seekbackward', () => { recordDiagnosticCommand('SEEK BACKWARD (-10s)'); audio.currentTime = Math.max(0, audio.currentTime - 10); }],
      ['seekforward', () => { recordDiagnosticCommand('SEEK FORWARD (+10s)'); audio.currentTime = Math.min(audio.duration || 0, audio.currentTime + 10); }],
      ['seekto', details => {
        recordDiagnosticCommand(`SEEK TO ${formatTime(details.seekTime)}`);
        if (details.seekTime !== undefined && !isNaN(details.seekTime)) {
          audio.currentTime = details.seekTime;
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

        if (currentIndex === -1 && playlist.length > 0) {
          trackTitle.textContent = playlist[0].title;
          trackArtist.textContent = playlist[0].artist;
        }

        // Кэшируем метаданные в IDB для работы офлайн
        if (idb) {
          try {
            const tx = idb.transaction('tracks_meta', 'readwrite');
            const store = tx.objectStore('tracks_meta');
            playlist.forEach(t => store.put(t));
          } catch {}
        }

        renderCatalog();
      } else if (fetchRetryCount < 6) {
        // Если база пуста, ждем фоновую синхронизацию с Telegram и повторяем запрос
        fetchRetryCount++;
        setTimeout(fetchCatalog, 3000);
      }
    } catch (err) {
      console.warn('Network offline or catalog fetch failed, relying on local cache:', err);
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

  // --- Рендеринг списка музыки в каталоге ---
  function renderCatalog() {
    const q = (searchInput.value || '').toLowerCase().trim();
    filteredPlaylist = playlist.filter(t => {
      const matchQ = !q || (t.title || '').toLowerCase().includes(q) || (t.artist || '').toLowerCase().includes(q);
      if (!matchQ) return false;
      if (activeTab === 'downloaded') return offlineTrackIds.has(t.id);
      if (activeTab === 'favorites') return favorites.has(t.id);
      return true;
    });

    tracksListEl.innerHTML = '';
    if (filteredPlaylist.length === 0) {
      tracksListEl.innerHTML = `
        <div style="text-align: center; padding: 36px 16px; color: var(--text-muted);">
          <div style="font-size: 18px; color: #fff; margin-bottom: 8px;">Канал @bahoniqmusic синхронизируется...</div>
          <p style="font-size: 14px; margin-bottom: 16px;">При первом запуске сервер считывает аудиофайлы из Telegram. Это занимает 5–10 секунд.</p>
          <button id="carBtnRetrySync" class="car-btn-open-list" style="margin: 0 auto;" type="button">🔄 Обновить список</button>
        </div>
      `;
      const retryBtn = document.getElementById('carBtnRetrySync');
      if (retryBtn) retryBtn.onclick = () => fetchCatalog();
      return;
    }

    filteredPlaylist.forEach(track => {
      const isCur = currentIndex >= 0 && playlist[currentIndex]?.id === track.id;
      const isOff = offlineTrackIds.has(track.id);
      const isDown = downloadingTrackIds.has(track.id);

      const item = document.createElement('div');
      item.className = `car-track-item ${isCur ? 'current' : ''}`;
      item.id = `track-item-${track.id}`;

      let badgeHtml = '';
      if (isOff) badgeHtml = `<span class="car-track-badge">✓ Офлайн</span>`;
      else if (isDown) badgeHtml = `<span class="car-track-badge" style="color:var(--accent-gold);background:rgba(250,204,21,0.15);">⏳ Загрузка</span>`;

      item.innerHTML = `
        <div class="car-track-thumb">
          <img src="/api/music/tracks/${track.id}/cover" alt="Обложка">
        </div>
        <div class="car-track-info">
          <div class="car-track-name">${escapeHtml(track.title)}</div>
          <div class="car-track-artist">${escapeHtml(track.artist)} · ${formatTime(track.duration)}</div>
        </div>
        ${badgeHtml}
      `;

      item.onclick = () => {
        const targetIdx = playlist.findIndex(t => t.id === track.id);
        if (targetIdx >= 0) {
          playTrack(targetIdx);
          catalogDrawer.classList.remove('open');
        }
      };

      tracksListEl.appendChild(item);
    });
  }

  function updateTrackItemBadge(trackId) {
    const el = document.getElementById(`track-item-${trackId}`);
    if (el) renderCatalog();
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
  document.querySelectorAll('.car-tab').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('.car-tab').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      activeTab = btn.dataset.tab;
      renderCatalog();
    };
  });

  searchInput.addEventListener('input', () => renderCatalog());

  // --- Открытие/закрытие панелей ---
  btnPlaylist.onclick = () => catalogDrawer.classList.add('open');
  btnCloseCatalog.onclick = () => catalogDrawer.classList.remove('open');

  const coverBox = $('carCoverBox');
  if (coverBox) coverBox.onclick = () => catalogDrawer.classList.add('open');
  const metaBox = $('carMetaBox');
  if (metaBox) metaBox.onclick = () => catalogDrawer.classList.add('open');
  const btnOpenList = $('carBtnOpenList');
  if (btnOpenList) btnOpenList.onclick = (e) => { e.stopPropagation(); catalogDrawer.classList.add('open'); };

  btnDiag.onclick = () => diagModal.classList.remove('hidden');
  btnCloseDiag.onclick = () => diagModal.classList.add('hidden');

  // --- Старт приложения ---
  async function init() {
    await initIndexedDB();
    await initOPFS();
    setupMediaSession();
    await scanOfflineTracks();
    await fetchCatalog();
  }

  init();
})();
