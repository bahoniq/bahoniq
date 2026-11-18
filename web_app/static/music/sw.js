/* BahonIQ РњСѓР·С‹РєР° РІ Р°РІС‚Рѕ - РР·РѕР»РёСЂРѕРІР°РЅРЅС‹Р№ Service Worker (Scope: /music/) */
const CACHE_NAME = 'bahoniq-music-shell-v25';
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

  // Р”Р»СЏ API-Р·Р°РїСЂРѕСЃРѕРІ Рё СЃС‚СЂРёРјРёРЅРіР° РѕС‚РґР°С‘Рј РЅР°РїСЂСЏРјСѓСЋ РІ СЃРµС‚СЊ (Р°СѓРґРёРѕ РєСЌС€РёСЂСѓРµС‚СЃСЏ РєР»РёРµРЅС‚РѕРј С‡РµСЂРµР· OPFS/IndexedDB)
  if (url.pathname.startsWith('/api/')) {
    return;
  }

  // Р”Р»СЏ СЃРєСЂРёРїС‚РѕРІ Рё СЃС‚РёР»РµР№: Network First СЃ РєСЌС€-fallback (РґР»СЏ РјРіРЅРѕРІРµРЅРЅРѕРіРѕ РѕР±РЅРѕРІР»РµРЅРёСЏ Р±РµР· СЂСѓС‡РЅРѕР№ С‡РёСЃС‚РєРё РєСЌС€Р°)
  if (url.pathname.endsWith('.js') || url.pathname.endsWith('.css')) {
    event.respondWith(
      fetch(event.request)
        .then(response => {
          if (response && response.status === 200) {
            const respClone = response.clone();
            caches.open(CACHE_NAME).then(cache => cache.put(event.request, respClone));
          }
          return response;
        })
        .catch(() => caches.match(event.request))
    );
    return;
  }

  // Р”Р»СЏ РЅР°РІРёРіР°С†РёРё РІРЅСѓС‚СЂРё /music/ РІРѕР·РІСЂР°С‰Р°РµРј РєСЌС€РёСЂРѕРІР°РЅРЅСѓСЋ РѕР±РѕР»РѕС‡РєСѓ РїР»РµРµСЂР°
  if (event.request.mode === 'navigate' && url.pathname.startsWith('/music/')) {
    event.respondWith(
      fetch(event.request).catch(() => caches.match('/music/'))
    );
    return;
  }

  // Р”Р»СЏ РѕСЃС‚Р°Р»СЊРЅС‹С… СЃС‚Р°С‚РёС‡РµСЃРєРёС… СЂРµСЃСѓСЂСЃРѕРІ РїР»РµРµСЂР° - Cache First СЃ fallback РІ СЃРµС‚СЊ
  if (url.pathname.startsWith('/music/')) {
    event.respondWith(
      caches.match(event.request).then(cached => {
        return cached || fetch(event.request);
      })
    );
  }
});
