/* Local assets only. Never cache external downloads or execute remote code. */
const CACHE = 'atlas-9093c57261084c';
const ROOT = new URL('./', self.location).href;
const PATHS = ['./','index.html','manifest.webmanifest','assets/icon.svg','assets/icon-192.png','assets/icon-512.png','data/catalog.json','data/updates.json','data/candidates.json','data/research_queue.json','data/quality_report.json'];
self.addEventListener('install', event => event.waitUntil(caches.open(CACHE).then(c => c.addAll(PATHS)).then(() => self.skipWaiting())));
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('atlas-') && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  if (event.request.method !== 'GET') return;
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || !url.href.startsWith(ROOT)) return;
  const known = PATHS.some(path => new URL(path, ROOT).pathname === url.pathname);
  if (!known && event.request.mode !== 'navigate') return;
  event.respondWith((async () => {
    const cache = await caches.open(CACHE);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 5000);
    try {
      const response = await fetch(event.request, {signal:controller.signal});
      if (!response.ok) throw new Error('HTTP ' + response.status);
      if (known) await cache.put(url.pathname, response.clone());
      return response;
    } catch (_) {
      return (await cache.match(url.pathname)) || (event.request.mode === 'navigate' ? await cache.match('index.html') : null) || new Response('Offline', {status:503});
    } finally { clearTimeout(timeout); }
  })());
});
