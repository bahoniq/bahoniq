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

  const btnSound = $('carBtnSound');
  const btnCloseSound = $('carBtnCloseSound');
  const soundModal = $('carSoundModal');
  const bassSlider = $('carBassSlider');
  const trebleSlider = $('carTrebleSlider');
  const bassValEl = $('carBassVal');
  const trebleValEl = $('carTrebleVal');
  const presetBtns = document.querySelectorAll('.car-sound-preset');

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
  let isShuffle = localStorage.getItem('bahoniq_shuffle') === 'true';
  let repeatMode = localStorage.getItem('bahoniq_repeat') || 'none'; // 'none' | 'all' | 'one'
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

  async function saveAudioLocally(trackId, blob, trackMeta = null) {
    let saved = false;
    // 1. Попытка в OPFS (Origin Private File System)
    if (opfsRoot) {
      try {
        const fileHandle = await opfsRoot.getFileHandle(`track_${trackId}.bin`, { create: true });
        const writable = await fileHandle.createWritable();
        await writable.write(blob);
        await writable.close();
        offlineTrackIds.add(trackId);
        saved = true;
      } catch (err) {
        console.warn('OPFS write failed, falling back to IndexedDB:', err);
      }
    }

    // 2. Всегда сохраняем в IndexedDB (метаданные и/или бинарник)
    if (idb) {
      try {
        if (!saved) {
          const txB = idb.transaction('tracks_blobs', 'readwrite');
          txB.objectStore('tracks_blobs').put({ id: trackId, blob: blob, size: blob.size, date: Date.now() });
        }
        if (trackMeta) {
          const txM = idb.transaction('tracks_meta', 'readwrite');
          txM.objectStore('tracks_meta').put(trackMeta);
        }
        offlineTrackIds.add(trackId);
        saved = true;
      } catch (err) {
        console.warn('IDB write error:', err);
      }
    }
    return saved;
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
    // 1. Сканируем OPFS
    if (opfsRoot && typeof opfsRoot.entries === 'function') {
      try {
        for await (const [name, handle] of opfsRoot.entries()) {
          const m = name.match(/^track_(\d+)\.bin$/);
          if (m) {
            offlineTrackIds.add(Number(m[1]));
          }
        }
      } catch (err) {
        console.warn('OPFS scan error:', err);
      }
    }

    // 2. Сканируем IndexedDB
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

    // 3. Восстанавливаем список треков из локального кэша IndexedDB если сети нет
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

    renderCatalog();
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
        await saveAudioLocally(track.id, completeBlob, track);
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

  // История воспроизведения (для точного возврата назад даже в режиме Shuffle)
  const playbackHistory = [];

  // --- Воспроизведение трека ---
  async function playTrack(index, recordHistory = true) {
    if (index < 0 || index >= playlist.length) return;

    if (recordHistory && currentIndex >= 0 && currentIndex !== index) {
      playbackHistory.push(currentIndex);
      if (playbackHistory.length > 50) playbackHistory.shift();
    }

    currentIndex = index;
    const track = playlist[currentIndex];

    resumeAudioContext();

    trackTitle.textContent = track.title || 'Без названия';
    trackArtist.textContent = track.artist || 'Музыка ДИТ';
    coverImg.onerror = () => {
      coverImg.onerror = null;
      coverImg.src = '/music/assets/logo.png';
    };
    coverImg.src = `/api/music/tracks/${track.id}/cover`;
    diagCurrentTrack.textContent = `${track.artist} — ${track.title}`;
    localStorage.setItem('bahoniq_last_track_id', track.id);

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
      let nextIdx = currentIndex;
      if (playlist.length > 1) {
        let attempts = 0;
        while (nextIdx === currentIndex && attempts < 20) {
          nextIdx = Math.floor(Math.random() * playlist.length);
          attempts++;
        }
      }
      playTrack(nextIdx, true);
    } else {
      const nextIdx = (currentIndex + 1) % playlist.length;
      playTrack(nextIdx, true);
    }
  }

  function playPrevTrack() {
    if (playlist.length === 0) return;
    if (audio.currentTime > 3) {
      audio.currentTime = 0;
      return;
    }
    // Если есть история (особенно в Shuffle) — возвращаем реально прошлый игравший трек!
    if (playbackHistory.length > 0) {
      const prevIdx = playbackHistory.pop();
      playTrack(prevIdx, false);
    } else {
      const prevIdx = (currentIndex - 1 + playlist.length) % playlist.length;
      playTrack(prevIdx, false);
    }
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
    } else if (repeatMode === 'all' || isShuffle || currentIndex < playlist.length - 1) {
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
    resumeAudioContext();
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

  // Восстановление сохранённого состояния кнопок Shuffle и Repeat
  if (btnShuffle) {
    btnShuffle.classList.toggle('active', isShuffle);
  }
  if (btnRepeat) {
    if (repeatMode === 'all') {
      btnRepeat.classList.add('active');
      btnRepeat.title = 'Повтор: Все треки';
    } else if (repeatMode === 'one') {
      btnRepeat.classList.add('active');
      btnRepeat.title = 'Повтор: Один трек';
    } else {
      btnRepeat.classList.remove('active');
      btnRepeat.title = 'Повтор: Выключен';
    }
  }

  btnShuffle.addEventListener('click', () => {
    isShuffle = !isShuffle;
    btnShuffle.classList.toggle('active', isShuffle);
    localStorage.setItem('bahoniq_shuffle', isShuffle ? 'true' : 'false');
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
    localStorage.setItem('bahoniq_repeat', repeatMode);
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

    // Аппаратные медиа-кнопки магнитолы (CAN-шина / Bluetooth HID / Клавиатурные события)
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

        const lastTrackId = Number(localStorage.getItem('bahoniq_last_track_id'));
        let initIdx = 0;
        if (lastTrackId) {
          const found = playlist.findIndex(t => t.id === lastTrackId);
          if (found >= 0) initIdx = found;
        }

        if (currentIndex === -1 && playlist.length > 0) {
          currentIndex = initIdx;
          const t = playlist[initIdx];
          trackTitle.textContent = t.title || 'Без названия';
          trackArtist.textContent = t.artist || 'Музыка ДИТ';
          coverImg.src = `/api/music/tracks/${t.id}/cover`;
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
      if (playlist.length === 0) {
        tracksListEl.innerHTML = `
          <div style="text-align: center; padding: 36px 16px; color: var(--text-muted);">
            <div style="font-size: 18px; color: #fff; margin-bottom: 8px;">Канал @bahoniqmusic синхронизируется...</div>
            <p style="font-size: 14px; margin-bottom: 16px;">При первом запуске сервер считывает аудиофайлы из Telegram. Это занимает 5–10 секунд.</p>
            <button id="carBtnRetrySync" class="car-btn-open-list" style="margin: 0 auto;" type="button">🔄 Обновить список</button>
          </div>
        `;
        const retryBtn = document.getElementById('carBtnRetrySync');
        if (retryBtn) retryBtn.onclick = () => fetchCatalog();
      } else if (activeTab === 'downloaded') {
        tracksListEl.innerHTML = `
          <div style="text-align: center; padding: 36px 16px; color: var(--text-muted);">
            <div style="font-size: 20px; color: #fff; margin-bottom: 8px;">💾 В памяти устройства пока нет треков</div>
            <p style="font-size: 14px; line-height: 1.5; margin-bottom: 16px; color: #cbd5e1;">
              Все <strong>${playlist.length} треков</strong> находятся на соседней вкладке <strong>«Все треки»</strong>.<br>
              Чтобы слушать их без интернета, скачайте их в память:
            </p>
            <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
              <button id="carBtnGoAllTab" class="car-btn-open-list" style="margin: 0;" type="button">📂 Открыть «Все треки»</button>
              <button id="carBtnTriggerDownloadAll" class="car-btn-open-list" style="margin: 0; background: rgba(0, 229, 255, 0.15); color: var(--accent-cyan); border-color: rgba(0,229,255,0.4);" type="button">📥 Скачать все (${playlist.length})</button>
            </div>
          </div>
        `;
        const goAll = document.getElementById('carBtnGoAllTab');
        if (goAll) goAll.onclick = () => {
          document.querySelectorAll('.car-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === 'all'));
          activeTab = 'all';
          renderCatalog();
        };
        const trigDl = document.getElementById('carBtnTriggerDownloadAll');
        if (trigDl && btnDownloadAll) {
          trigDl.onclick = () => btnDownloadAll.click();
        }
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
          document.querySelectorAll('.car-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === 'all'));
          activeTab = 'all';
          renderCatalog();
        };
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

  const btnDownloadAll = $('carBtnDownloadAll');
  let isDownloadingAll = false;

  if (btnDownloadAll) {
    btnDownloadAll.onclick = async () => {
      if (isDownloadingAll) return;
      const unDownloaded = playlist.filter(t => !offlineTrackIds.has(t.id));
      if (unDownloaded.length === 0) {
        alert('Все треки уже сохранены в памяти устройства!');
        return;
      }
      isDownloadingAll = true;
      btnDownloadAll.disabled = true;

      let count = 0;
      for (const track of unDownloaded) {
        count++;
        btnDownloadAll.textContent = `📥 ${count}/${unDownloaded.length}...`;
        await downloadTrackInBackground(track);
      }

      btnDownloadAll.textContent = '✓ Все сохранены';
      btnDownloadAll.disabled = false;
      isDownloadingAll = false;
      renderCatalog();
    };
  }

  // --- Звуковой процессор (Web Audio API) и сочный бас ---
  let audioCtx = null;
  let audioSourceNode = null;
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
      audioCtx = new AudioCtxClass();

      audioSourceNode = audioCtx.createMediaElementSource(audio);

      // LowShelf фильтр на 75 Гц: даёт мягкий, глубокий и сочный бархатный панч
      bassFilter = audioCtx.createBiquadFilter();
      bassFilter.type = 'lowshelf';
      bassFilter.frequency.value = 75;
      bassFilter.gain.value = currentBassGain;

      // HighShelf фильтр на 9000 Гц: добавляет воздушность и чистоту вокалу/тарелкам
      trebleFilter = audioCtx.createBiquadFilter();
      trebleFilter.type = 'highshelf';
      trebleFilter.frequency.value = 9000;
      trebleFilter.gain.value = currentTrebleGain;

      // Студийный динамический компрессор-лимитер (Anti-clipping protection):
      // Защищает динамики и дверные карты авто от треска, клиппинга и искажений при любой громкости
      limiterNode = audioCtx.createDynamicsCompressor();
      limiterNode.threshold.value = -1.5;
      limiterNode.knee.value = 6;
      limiterNode.ratio.value = 8;
      limiterNode.attack.value = 0.003;
      limiterNode.release.value = 0.15;

      audioSourceNode.connect(bassFilter);
      bassFilter.connect(trebleFilter);
      trebleFilter.connect(limiterNode);
      limiterNode.connect(audioCtx.destination);

      isAudioChainInit = true;
    } catch (e) {
      console.warn('Audio DSP init error:', e);
    }
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
    presetBtns.forEach(b => b.classList.toggle('active', b.dataset.preset === presetKey));
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
    if (bassValEl) {
      bassValEl.textContent = `${currentBassGain > 0 ? '+' : ''}${currentBassGain.toFixed(1)} dB`;
    }
    if (bassSlider) {
      bassSlider.value = currentBassGain;
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
    if (trebleValEl) {
      trebleValEl.textContent = `${currentTrebleGain > 0 ? '+' : ''}${currentTrebleGain.toFixed(1)} dB`;
    }
    if (trebleSlider) {
      trebleSlider.value = currentTrebleGain;
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
    setupSoundControls();
    await scanOfflineTracks();
    await fetchCatalog();
  }

  init();
})();
