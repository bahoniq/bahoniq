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
  const downloadPromises = new Map();
  let currentBlobUrl = null;
  let playRequestId = 0;
  let activeTab = 'all';

  // --- Хранение индекса скачанных треков и кэша плейлиста для мгновенного старта офлайн ---
  const OFFLINE_IDS_STORAGE_KEY = 'bahoniq_music_offline_ids';
  const CACHED_PLAYLIST_KEY = 'bahoniq_cached_playlist';

  function persistOfflineTrackIds() {
    try {
      localStorage.setItem(OFFLINE_IDS_STORAGE_KEY, JSON.stringify([...offlineTrackIds]));
    } catch {}
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
  }

  function persistCachedPlaylist() {
    try {
      if (playlist && playlist.length > 0) {
        localStorage.setItem(CACHED_PLAYLIST_KEY, JSON.stringify(playlist));
      }
    } catch {}
  }

  function loadCachedPlaylistFromStorage() {
    try {
      const raw = localStorage.getItem(CACHED_PLAYLIST_KEY);
      if (raw) {
        const arr = JSON.parse(raw);
        if (Array.isArray(arr) && arr.length > 0 && playlist.length === 0) {
          playlist = arr;
          filteredPlaylist = [...playlist];
        }
      }
    } catch {}
  }

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
    const expectedSize = Number(trackMeta?.file_size || 0);
    if (!blob || blob.size <= 0 || (expectedSize > 0 && blob.size !== expectedSize)) {
      return false;
    }
    let saved = false;
    // 1. Попытка в OPFS (Origin Private File System)
    if (opfsRoot) {
      try {
        const tempName = `track_${trackId}.part`;
        const tempHandle = await opfsRoot.getFileHandle(tempName, { create: true });
        const tempWriter = await tempHandle.createWritable();
        await tempWriter.write(blob);
        await tempWriter.close();
        const tempFile = await tempHandle.getFile();
        if (tempFile.size !== blob.size) throw new Error('OPFS temporary file size mismatch');

        const fileHandle = await opfsRoot.getFileHandle(`track_${trackId}.bin`, { create: true });
        const writable = await fileHandle.createWritable();
        await writable.write(tempFile);
        await writable.close();
        const finalFile = await fileHandle.getFile();
        if (finalFile.size !== blob.size) throw new Error('OPFS final file size mismatch');
        await opfsRoot.removeEntry(tempName).catch(() => {});
        offlineTrackIds.add(trackId);
        persistOfflineTrackIds();
        saved = true;
      } catch (err) {
        try { await opfsRoot.removeEntry(`track_${trackId}.part`); } catch {}
        try { await opfsRoot.removeEntry(`track_${trackId}.bin`); } catch {}
        console.warn('OPFS write failed, falling back to IndexedDB:', err);
      }
    }

    // 2. Всегда сохраняем в IndexedDB (метаданные и/или бинарник)
    if (idb) {
      try {
        if (!saved) {
          await new Promise((resolve, reject) => {
            const txB = idb.transaction('tracks_blobs', 'readwrite');
            txB.objectStore('tracks_blobs').put({
              id: trackId, blob, size: blob.size, expectedSize: expectedSize || blob.size,
              complete: true, date: Date.now()
            });
            txB.oncomplete = () => resolve();
            txB.onerror = () => reject(txB.error || new Error('IndexedDB audio write failed'));
            txB.onabort = () => reject(txB.error || new Error('IndexedDB audio write aborted'));
          });
        }
        if (trackMeta) {
          await new Promise((resolve, reject) => {
            const txM = idb.transaction('tracks_meta', 'readwrite');
            txM.objectStore('tracks_meta').put(trackMeta);
            txM.oncomplete = () => resolve();
            txM.onerror = () => reject(txM.error || new Error('IndexedDB metadata write failed'));
            txM.onabort = () => reject(txM.error || new Error('IndexedDB metadata write aborted'));
          });
        }
        offlineTrackIds.add(trackId);
        persistOfflineTrackIds();
        saved = true;
      } catch (err) {
        console.warn('IDB write error:', err);
      }
    }
    return saved;
  }

  async function getLocalAudioBlob(trackId, expectedSize = 0) {
    if (opfsRoot) {
      try {
        const fileHandle = await opfsRoot.getFileHandle(`track_${trackId}.bin`);
        const file = await fileHandle.getFile();
        if (file && file.size > 0 && (!expectedSize || file.size === expectedSize)) return file;
        if (file && expectedSize && file.size !== expectedSize) {
          await opfsRoot.removeEntry(`track_${trackId}.bin`).catch(() => {});
          offlineTrackIds.delete(trackId);
          persistOfflineTrackIds();
        }
      } catch {}
    }

    if (idb) {
      return new Promise(resolve => {
        try {
          const tx = idb.transaction('tracks_blobs', 'readonly');
          const req = tx.objectStore('tracks_blobs').get(trackId);
          req.onsuccess = () => {
            const row = req.result;
            const valid = row && row.complete === true && row.blob && row.blob.size > 0 &&
              (!expectedSize || row.blob.size === expectedSize);
            if (valid) {
              resolve(row.blob);
              return;
            }
            // Старые/оборванные записи не должны оставаться «офлайн».
            offlineTrackIds.delete(trackId);
            persistOfflineTrackIds();
            try {
              const cleanupTx = idb.transaction('tracks_blobs', 'readwrite');
              cleanupTx.objectStore('tracks_blobs').delete(trackId);
            } catch {}
            resolve(null);
          };
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
    persistOfflineTrackIds();
    updateTrackItemBadge(trackId);
    if (currentIndex >= 0 && playlist[currentIndex]?.id === trackId) {
      updateOfflinePill('stream');
    }
  }

  async function scanOfflineTracks() {
    // localStorage — только список кандидатов для быстрой проверки, но не
    // доказательство наличия файла. Истина — успешно прочитанный OPFS/IDB Blob.
    const registryCandidates = new Set();
    try {
      const raw = localStorage.getItem(OFFLINE_IDS_STORAGE_KEY);
      const arr = raw ? JSON.parse(raw) : [];
      if (Array.isArray(arr)) arr.forEach(id => registryCandidates.add(Number(id)));
    } catch {}
    offlineTrackIds.clear();
    loadCachedPlaylistFromStorage();

    // 1. Проверяем сами записи IndexedDB, а не только их ключи.
    if (idb) {
      await new Promise(resolve => {
        try {
          const tx = idb.transaction('tracks_blobs', 'readonly');
          const req = tx.objectStore('tracks_blobs').getAll();
          req.onsuccess = () => {
            (req.result || []).forEach(row => {
              const track = playlist.find(t => Number(t.id) === Number(row.id));
              const expectedSize = Number(track?.file_size || row.expectedSize || 0);
              const actualSize = Number(row.blob?.size || row.size || 0);
              if (row.complete === true && row.blob && actualSize > 0 &&
                  (!expectedSize || actualSize === expectedSize)) {
                offlineTrackIds.add(Number(row.id));
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

    // 2. Если треки в плейлисте известны, проверяем файлы в OPFS точечно по ID (работает на всех магнитолах и WebViews)
    if (opfsRoot && playlist.length > 0) {
      // Ограничиваем параллелизм для слабых Android-магнитол.
      for (let start = 0; start < playlist.length; start += 16) {
        const batch = playlist.slice(start, start + 16);
        await Promise.all(batch.map(async t => {
        try {
          const handle = await opfsRoot.getFileHandle(`track_${t.id}.bin`);
          const file = await handle.getFile();
          if (file && file.size > 0 && (!t.file_size || file.size === t.file_size)) {
            offlineTrackIds.add(t.id);
          } else if (file) {
            await opfsRoot.removeEntry(`track_${t.id}.bin`).catch(() => {});
            offlineTrackIds.delete(t.id);
          }
        } catch {}
        }));
      }
    }

    // 3. Проверяем кандидатов старого реестра и небольшой аварийный диапазон.
    if (opfsRoot) {
      const probeIds = [...registryCandidates];
      for (let i = 1; i <= 150; i++) {
        if (!offlineTrackIds.has(i) && !registryCandidates.has(i)) probeIds.push(i);
      }
      for (let s = 0; s < probeIds.length; s += 16) {
        const batch = probeIds.slice(s, s + 16);
        await Promise.all(batch.map(async id => {
          try {
            const handle = await opfsRoot.getFileHandle(`track_${id}.bin`);
            const file = await handle.getFile();
            const track = playlist.find(t => Number(t.id) === Number(id));
            const expectedSize = Number(track?.file_size || 0);
            if (file && file.size > 0 && (!expectedSize || file.size === expectedSize)) {
              offlineTrackIds.add(id);
            }
          } catch {}
        }));
      }
    }

    // Перезаписываем быстрый реестр только реально подтверждёнными файлами.
    persistOfflineTrackIds();

    // 4. Также сканируем OPFS итератором (если поддерживается)
    if (opfsRoot) {
      try {
        if (typeof opfsRoot.entries === 'function') {
          for await (const [name, handle] of opfsRoot.entries()) {
            const m = name.match(/^track_(\d+)\.bin$/);
            if (m) {
              const trackId = Number(m[1]);
              const track = playlist.find(t => t.id === trackId);
              const file = await handle.getFile();
              if (file.size > 0 && (!track?.file_size || file.size === track.file_size)) offlineTrackIds.add(trackId);
            }
          }
        } else if (typeof opfsRoot.values === 'function') {
          for await (const handle of opfsRoot.values()) {
            const m = (handle.name || '').match(/^track_(\d+)\.bin$/);
            if (m) {
              const trackId = Number(m[1]);
              const track = playlist.find(t => t.id === trackId);
              const file = await handle.getFile();
              if (file.size > 0 && (!track?.file_size || file.size === track.file_size)) {
                offlineTrackIds.add(trackId);
              }
            }
          }
        }
      } catch (err) {
        console.warn('OPFS iterator scan:', err);
      }
    }

    // 5. Восстанавливаем список треков из локального кэша IndexedDB если сети нет
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
    renderCatalog();
  }

  // --- Форматирование времени ---
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
    if (!track) return false;
    if (downloadPromises.has(track.id)) return downloadPromises.get(track.id);

    // Зелёный бейдж мог прийти из устаревшего localStorage. Перед отказом от
    // загрузки обязательно подтверждаем существование читаемого файла.
    if (offlineTrackIds.has(track.id)) {
      const verifiedBlob = await getLocalAudioBlob(track.id, Number(track.file_size || 0));
      if (verifiedBlob) return true;
      offlineTrackIds.delete(track.id);
      persistOfflineTrackIds();
      updateTrackItemBadge(track.id);
    }

    const task = (async () => {
      updateTrackItemBadge(track.id);
      const controller = new AbortController();
      try {
      const resp = await fetch(`/api/music/tracks/${track.id}/download`, { signal: controller.signal });
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
      const expectedSize = Number(track.file_size || contentLength || 0);
      if (completeBlob.size > 0 && (!expectedSize || completeBlob.size === expectedSize)) {
        const saved = await saveAudioLocally(track.id, completeBlob, { ...track, file_size: expectedSize || completeBlob.size });
        if (!saved) throw new Error('Local file validation failed');
        if (currentIndex >= 0 && playlist[currentIndex]?.id === track.id) {
          updateOfflinePill('offline');
        }
        return true;
      } else {
        console.warn('Size mismatch, discarded incomplete file');
        return false;
      }
    } catch (err) {
      console.warn('Background download error:', err);
      return false;
    } finally {
      controller.abort();
      updateTrackItemBadge(track.id);
    }
    })();
    downloadPromises.set(track.id, task);
    try {
      return await task;
    } finally {
      downloadPromises.delete(track.id);
    }
  }

  // История воспроизведения (для точного возврата назад даже в режиме Shuffle)
  const playbackHistory = [];

  // --- Воспроизведение трека ---
  async function playTrack(index, recordHistory = true) {
    if (index < 0 || index >= playlist.length) return;
    const requestId = ++playRequestId;

    if (recordHistory && currentIndex >= 0 && currentIndex !== index) {
      playbackHistory.push(playlist[currentIndex]?.id);
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

    // Проверяем наличие офлайн-копии
    const localBlob = await getLocalAudioBlob(track.id, Number(track.file_size || 0));
    if (requestId !== playRequestId) return;

    audio.pause();
    audio.removeAttribute('src');
    audio.load();
    if (currentBlobUrl) {
      URL.revokeObjectURL(currentBlobUrl);
      currentBlobUrl = null;
    }
    if (localBlob) {
      offlineTrackIds.add(track.id);
      persistOfflineTrackIds();
      updateTrackItemBadge(track.id);
      currentBlobUrl = URL.createObjectURL(localBlob);
      audio.src = currentBlobUrl;
      updateOfflinePill('offline');
      btnDownloadActive.classList.add('active');
    } else {
      // Убираем ложный статус, иначе downloadTrackInBackground решит, что файл
      // уже существует, и не восстановит его.
      offlineTrackIds.delete(track.id);
      persistOfflineTrackIds();
      updateTrackItemBadge(track.id);
      btnDownloadActive.classList.remove('active');
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
      const prevId = playbackHistory.pop();
      const prevIdx = playlist.findIndex(t => t.id === prevId);
      playTrack(prevIdx >= 0 ? prevIdx : (currentIndex - 1 + playlist.length) % playlist.length, false);
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

  audio.addEventListener('waiting', () => {
    diagAudioStatus.textContent = 'Буферизация...';
    btnPlay.classList.add('loading');
  });

  audio.addEventListener('playing', () => {
    diagAudioStatus.textContent = 'Воспроизведение';
    btnPlay.classList.remove('loading');
    updatePlayButton(true);
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing';
  });

  audio.addEventListener('pause', () => {
    diagAudioStatus.textContent = 'Пауза';
    btnPlay.classList.remove('loading');
    updatePlayButton(false);
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'paused';
  });

  audio.addEventListener('error', (e) => {
    console.warn('Audio playback error:', e);
    btnPlay.classList.remove('loading');
    updatePlayButton(false);
    diagAudioStatus.textContent = 'Ошибка потока';
    recordDiagnosticCommand('ОШИБКА ПОТОКА (СЕТЬ)');
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
      audio.play().catch(err => {
        console.warn('Audio play failed:', err);
        updatePlayButton(false);
      });
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
        { src: `/api/music/tracks/${track.id}/cover`, sizes: '512x512', type: 'image/png' }
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
        persistCachedPlaylist();
        await scanOfflineTracks();

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
      if (activeTab === 'downloaded') {
        tracksListEl.innerHTML = `
          <div style="text-align: center; padding: 36px 16px; color: var(--text-muted);">
            <div style="font-size: 20px; color: #fff; margin-bottom: 8px;">💾 В памяти устройства пока нет сохранённых треков</div>
            <p style="font-size: 14px; line-height: 1.5; margin-bottom: 16px; color: #cbd5e1;">
              ${playlist.length > 0 ? `Все <strong>${playlist.length} треков</strong> находятся на соседней вкладке <strong>«Все треки»</strong>.<br>Чтобы слушать их без интернета, скачайте их в память:` : 'Подключитесь к интернету для первого скачивания треков в память.'}
            </p>
            <div style="display: flex; gap: 10px; justify-content: center; flex-wrap: wrap;">
              <button id="carBtnGoAllTab" class="car-btn-open-list" style="margin: 0;" type="button">📂 Открыть «Все треки»</button>
              ${playlist.length > 0 ? `<button id="carBtnTriggerDownloadAll" class="car-btn-open-list" style="margin: 0; background: rgba(0, 229, 255, 0.15); color: var(--accent-cyan); border-color: rgba(0,229,255,0.4);" type="button">📥 Скачать все (${playlist.length})</button>` : ''}
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
      } else if (playlist.length === 0) {
        tracksListEl.innerHTML = `
          <div style="text-align: center; padding: 36px 16px; color: var(--text-muted);">
            <div style="font-size: 18px; color: #fff; margin-bottom: 8px;">Канал @bahoniqmusic синхронизируется...</div>
            <p style="font-size: 14px; margin-bottom: 16px;">При первом запуске сервер считывает аудиофайлы из Telegram. Это занимает 5–10 секунд.</p>
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
      const isCur = currentIndex >= 0 && playlist[currentIndex]?.id === track.id;
      const isOff = offlineTrackIds.has(track.id);
      const isDown = downloadPromises.has(track.id);

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
    if (activeTab === 'downloaded') {
      renderCatalog();
      return;
    }
    const el = document.getElementById(`track-item-${trackId}`);
    if (!el) return;
    const isOff = offlineTrackIds.has(trackId);
    const isDown = downloadPromises.has(trackId);
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
        try {
          await downloadTrackInBackground(track);
        } catch (err) {
          console.warn(`Error downloading track ${track.id}:`, err);
        }
      }

      btnDownloadAll.textContent = '✓ Все сохранены';
      btnDownloadAll.disabled = false;
      isDownloadingAll = false;
      await scanOfflineTracks();
      renderCatalog();
    };
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
    // Компенсируем максимальный положительный подъём EQ до компрессора.
    const boostDb = Math.max(0, currentBassGain, currentTrebleGain);
    const gain = Math.pow(10, (-boostDb / 20));
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
    updateDSPHeadroom();
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
    updateDSPHeadroom();
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

  window.addEventListener('pagehide', () => {
    if (currentBlobUrl) {
      URL.revokeObjectURL(currentBlobUrl);
      currentBlobUrl = null;
    }
  });
  const metaBox = $('carMetaBox');
  if (metaBox) metaBox.onclick = () => catalogDrawer.classList.add('open');
  const btnOpenList = $('carBtnOpenList');
  if (btnOpenList) btnOpenList.onclick = (e) => { e.stopPropagation(); catalogDrawer.classList.add('open'); };

  btnDiag.onclick = () => diagModal.classList.remove('hidden');
  btnCloseDiag.onclick = () => diagModal.classList.add('hidden');

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
    }
  });

  // --- Старт приложения ---
  async function init() {
    loadOfflineTrackIdsFromStorage();
    loadCachedPlaylistFromStorage();
    if (playlist.length > 0) {
      renderCatalog();
    }
    await initIndexedDB();
    await initOPFS();
    setupMediaSession();
    setupSoundControls();
    await scanOfflineTracks();
    await fetchCatalog();
  }

  init();
})();
