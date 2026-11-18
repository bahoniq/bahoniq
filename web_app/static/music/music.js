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
    document.querySelectorAll('.car-tab').forEach(btn => {
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
    if (!offlineStatus || !offlineText) return;
    offlineStatus.className = 'car-offline-pill';
    if (state === 'offline') {
      offlineStatus.classList.add('offline');
      offlineText.textContent = 'Офлайн (в памяти)';
    } else if (state === 'stream') {
      offlineStatus.classList.add('stream');
      offlineText.textContent = 'Онлайн стриминг';
    } else if (state === 'downloading') {
      offlineStatus.classList.add('downloading');
      offlineText.textContent = progress > 0 ? `Сохранение ${progress}%` : 'Сохранение в память...';
    }
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
              blob = new Blob(chunks, { type: resp.headers.get('Content-Type') || track.mime_type || 'audio/mpeg' });
            } else {
              blob = await resp.blob();
            }

            if (!blob || blob.size < 20000 || (responseSize > 0 && Math.abs(blob.size - responseSize) > 4096)) {
              throw new Error(`Downloaded blob size mismatch (${blob?.size || 0} vs ${responseSize})`);
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
    coverImg.onerror = () => {
      coverImg.onerror = null;
      coverImg.src = '/music/assets/logo.png';
    };
    coverImg.src = `/api/music/tracks/${tid}/cover`;
    if (diagCurrentTrack) diagCurrentTrack.textContent = `${track.artist} — ${track.title}`;
    localStorage.setItem('bahoniq_last_track_id', tid);

    const isFav = favorites.has(tid);
    btnFav.classList.toggle('active', isFav);
    btnFav.classList.toggle('fav-active', isFav);
    const isOffline = offlineTrackIds.has(tid);
    if (btnDownloadActive) btnDownloadActive.classList.toggle('active', isOffline);

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

    if (audio.src !== targetSrc) {
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
    if (!isNaN(audio.duration) && audio.duration > 0) {
      const pct = (audio.currentTime / audio.duration) * 100;
      seekBar.value = pct;
      timeCurrent.textContent = formatTime(audio.currentTime);
      timeTotal.textContent = formatTime(audio.duration);

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
    if ('mediaSession' in navigator) navigator.mediaSession.playbackState = 'playing';

    // Автоматическое сохранение в память устройства после фактического старта воспроизведения (как в Telegram)
    if (currentIndex >= 0 && playlist[currentIndex]) {
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
  });

  audio.addEventListener('error', (e) => {
    console.warn('Audio stream error event:', e);
    btnPlay.classList.remove('loading');
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

  btnFav.addEventListener('click', () => {
    if (currentIndex < 0 || !playlist[currentIndex]) return;
    const track = playlist[currentIndex];
    const tid = Number(track.id);
    if (favorites.has(tid)) {
      favorites.delete(tid);
      btnFav.classList.remove('active', 'fav-active');
      showCarToast('Убрано из Избранного');
    } else {
      favorites.add(tid);
      btnFav.classList.add('active', 'fav-active');
      showCarToast('❤️ Добавлено в Избранное');
    }
    persistFavorites();
    if (activeTab === 'favorites') renderCatalog();
  });

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
        { src: `/api/music/tracks/${tid}/cover`, sizes: '512x512', type: 'image/png' }
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
          coverImg.src = `/api/music/tracks/${tid}/cover`;
          const isFav = favorites.has(tid);
          btnFav.classList.toggle('active', isFav);
          btnFav.classList.toggle('fav-active', isFav);
          const isOff = offlineTrackIds.has(tid);
          if (btnDownloadActive) btnDownloadActive.classList.toggle('active', isOff);
          updateOfflinePill(isOff ? 'offline' : 'stream');
          const savedPos = Number(localStorage.getItem(LAST_POS_STORAGE_KEY) || '0');
          if (t.duration > 0) {
            timeTotal.textContent = formatTime(t.duration);
            if (savedPos > 0 && savedPos < t.duration) {
              timeCurrent.textContent = formatTime(savedPos);
              seekBar.value = (savedPos / t.duration) * 100;
            }
          }
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
          document.querySelectorAll('.car-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === 'all'));
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
          document.querySelectorAll('.car-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === 'all'));
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
          document.querySelectorAll('.car-tab').forEach(b => b.classList.toggle('active', b.dataset.tab === 'all'));
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
          <img src="/api/music/tracks/${tid}/cover" alt="Обложка">
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
  document.querySelectorAll('.car-tab').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('.car-tab').forEach(b => b.classList.remove('active'));
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
  if (btnPlaylist && catalogDrawer) btnPlaylist.onclick = () => catalogDrawer.classList.add('open');
  if (btnCloseCatalog && catalogDrawer) btnCloseCatalog.onclick = () => catalogDrawer.classList.remove('open');

  const coverBox = $('carCoverBox');
  if (coverBox && catalogDrawer) {
    let touchStartX = 0;
    let touchStartY = 0;
    coverBox.addEventListener('touchstart', e => {
      if (e.touches && e.touches.length === 1) {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
      }
    }, { passive: true });
    coverBox.addEventListener('touchend', e => {
      if (!e.changedTouches || e.changedTouches.length === 0) return;
      const dx = e.changedTouches[0].clientX - touchStartX;
      const dy = e.changedTouches[0].clientY - touchStartY;
      if (Math.abs(dx) > 55 && Math.abs(dx) > Math.abs(dy) * 1.4) {
        if (dx < 0) playNextTrack();
        else playPrevTrack();
      }
    }, { passive: true });
    coverBox.onclick = () => catalogDrawer.classList.add('open');
  }

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
    }
  });

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
