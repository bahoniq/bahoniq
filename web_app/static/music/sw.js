/* BahonIQ Музыка в авто - Изолированный Service Worker (Scope: /music/) — 100% Offline Ready */
const CACHE_NAME = 'bahoniq-music-shell-v46-radio-cors-fix';
const COVERS_CACHE_NAME = 'bahoniq-music-covers-v1';
const SHELL_ASSETS = [
  '/music/',
  '/music/manifest.webmanifest',
  '/music/assets/music.css',
  '/music/assets/music.js',
  '/music/assets/logo.png',
  '/music/assets/icons/icon-192.png',
  '/music/assets/icons/icon-512.png',
  '/music/assets/icons/maskable-icon-512.png'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(SHELL_ASSETS);
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys
          .filter(k => k.startsWith('bahoniq-music-') && k !== CACHE_NAME && k !== COVERS_CACHE_NAME)
          .map(k => caches.delete(k))
      );
    }).then(() => self.clients.claim())
  );
});

// Быстрый сетевой запрос с таймаутом (если сеть в авто слабая или отсутствует — не ждём 30 сек, сразу отдаём из памяти)
function fetchWithTimeout(request, timeoutMs = 2500) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Network timeout')), timeoutMs);
    fetch(request).then(response => {
      clearTimeout(timer);
      resolve(response);
    }).catch(err => {
      clearTimeout(timer);
      reject(err);
    });
  });
}

function isCoverApiRequest(url) {
  return (
    url.pathname.startsWith('/api/music/cover/') ||
    (url.pathname.startsWith('/api/music/tracks/') && url.pathname.endsWith('/cover'))
  );
}

self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);

  // Кэширование ТОЛЬКО реальных обложек треков (заглушки X-Cover-Placeholder: true и ошибки 404/5xx никогда не сохраняются)
  if (isCoverApiRequest(url)) {
    const ver = url.searchParams.get('v') || '0';
    const hasHashVersion = ver && ver !== '0';
    event.respondWith(
      caches.open(COVERS_CACHE_NAME).then(async cache => {
        if (hasHashVersion) {
          const cached = await cache.match(event.request);
          if (cached) return cached;
        }
        try {
          const response = await fetch(event.request);
          const isPlaceholder = response.headers.get('X-Cover-Placeholder') === 'true';
          if (response && response.status === 200 && !isPlaceholder) {
            cache.put(event.request, response.clone());
          }
          return response;
        } catch (err) {
          const fallbackCached = await cache.match(event.request);
          if (fallbackCached) return fallbackCached;
          throw err;
        }
      })
    );
    return;
  }

  // Для остальных API-запросов и стриминга отдаём напрямую (аудио и список треков кэшируются плеером в IndexedDB/OPFS)
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  // Для навигации внутри /music/ (запуск APK или открытие вкладки без интернета)
  if (event.request.mode === 'navigate' && (url.pathname === '/music' || url.pathname.startsWith('/music/'))) {
    event.respondWith(
      fetchWithTimeout(event.request, 2500)
        .then(response => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put('/music/', clone));
          }
          return response;
        })
        .catch(() => {
          return caches.match('/music/', { ignoreSearch: true })
            .then(cached => cached || caches.match(event.request, { ignoreSearch: true }));
        })
    );
    return;
  }

  // Для скриптов и стилей (/music/assets/music.js?v=..., music.css?v=...)
  if (url.pathname.endsWith('.js') || url.pathname.endsWith('.css')) {
    event.respondWith(
      fetchWithTimeout(event.request, 2500)
        .then(response => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        })
        .catch(() => {
          return caches.match(event.request)
            .then(exact => exact || caches.match(event.request, { ignoreSearch: true }));
        })
    );
    return;
  }

  // Для остальных статических ресурсов плеера (иконки, логотип, манифест) — Cache First с ignoreSearch
  if (url.pathname.startsWith('/music/')) {
    event.respondWith(
      caches.match(event.request, { ignoreSearch: true }).then(cached => {
        if (cached) return cached;
        return fetch(event.request).then(response => {
          if (response && response.status === 200) {
            const clone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, clone));
          }
          return response;
        });
      })
    );
  }
});
