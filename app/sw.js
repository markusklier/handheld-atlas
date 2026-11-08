// Handheld Atlas service worker. __VERSION__ is replaced at build time.
// App shell: cache-first. data.json / version.json: network-first, so the app updates itself when online.
const CACHE = 'atlas-__VERSION__';
const SHELL = ['./', 'index.html', 'style.css', 'app.js', 'icon.svg', 'icon-192.png', 'manifest.webmanifest'];

self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', (e) => {
  e.waitUntil(caches.keys()
    .then((keys) => Promise.all(keys.filter((k) => k.startsWith('atlas-') && k !== CACHE).map((k) => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (e.request.method !== 'GET' || url.origin !== location.origin) return; // cover images etc. go straight to the network
  const fresh = /\/(data|version)\.json$/.test(url.pathname) || e.request.mode === 'navigate';
  if (fresh) {
    e.respondWith(fetch(e.request).then((res) => {
      const copy = res.clone();
      caches.open(CACHE).then((c) => c.put(e.request, copy));
      return res;
    }).catch(() => caches.match(e.request).then((r) => r || caches.match('index.html'))));
  } else {
    e.respondWith(caches.match(e.request).then((r) => r || fetch(e.request)));
  }
});
