/* BahonIQ Музыка в авто - Изолированный Service Worker (Scope: /music/) */
const CACHE_NAME = 'bahoniq-music-shell-v5';
const SHELL_ASSETS = [
  '/music/',
  '/music/manifest.webmanifest',
  '/music/assets/music.css',
  '/music/assets/music.js',
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
        keys.filter(k => k.startsWith('bahoniq-music-') && k !== CACHE_NAME).map(k => caches.delete(k))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);

  // Для API-запросов и стриминга отдаём напрямую в сеть (аудио кэшируется клиентом через OPFS/IndexedDB)
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  // Для навигации внутри /music/ возвращаем кэшированную оболочку плеера
  if (event.request.mode === 'navigate' && url.pathname.startsWith('/music/')) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match('/music/'))
    );
    return;
  }

  // Для статических ресурсов плеера - Cache First с fallback в сеть
  if (url.pathname.startsWith('/music/')) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        return cached || fetch(event.request);
      })
    );
  }
});
