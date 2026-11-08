"""Reproducible static PWA build. Python 3.10+, standard library only."""
import base64
import hashlib
import json
import shutil
import struct
import zlib
from pathlib import Path
from validate import validate

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / 'dist'


def json_embed(path):
    return json.dumps(json.loads(path.read_text(encoding='utf-8')), ensure_ascii=False,
                      separators=(',', ':')).replace('<', '\\u003c')


def icon_png(size):
    """Rasterize an original two-screen geometric mark; no font dependency."""
    rows = []
    for y in range(size):
        row = bytearray([0])
        for x in range(size):
            u, v = x / size, y / size
            pixel = (178, 244, 203, 255)
            if (.20 < u < .80 and .19 < v < .47) or (.20 < u < .80 and .53 < v < .81):
                pixel = (22, 48, 34, 255)
            if (.26 < u < .74 and .25 < v < .41) or (.30 < u < .70 and .59 < v < .75):
                pixel = (178, 244, 203, 255)
            row.extend(pixel)
        rows.append(bytes(row))
    def chunk(name, payload):
        return struct.pack('!I', len(payload)) + name + payload + struct.pack('!I', zlib.crc32(name + payload) & 0xffffffff)
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('!IIBBBBB', size, size, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(b''.join(rows))) + chunk(b'IEND', b'')


def build():
    catalog = json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8'))
    validate(catalog)
    DIST.mkdir(exist_ok=True)
    (DIST / 'assets').mkdir(exist_ok=True)
    (DIST / 'data').mkdir(exist_ok=True)
    html = (ROOT / 'src/template.html').read_text(encoding='utf-8')
    parts = {'STYLE':(ROOT/'src/style.css').read_text(encoding='utf-8'),
             'CORE':(ROOT/'src/core.js').read_text(encoding='utf-8'),
             'APP':(ROOT/'src/app.js').read_text(encoding='utf-8'),
             'CATALOG':json_embed(ROOT/'data/catalog.json'),
             'UPDATES':json_embed(ROOT/'data/updates.json'),
             'CANDIDATES':json_embed(ROOT/'data/candidates.json'),
             'RESEARCH':json_embed(ROOT/'data/research_queue.json'),
             'QUALITY':json_embed(ROOT/'data/quality_report.json')}
    for key, content in parts.items():
        html = html.replace('/*__' + key + '__*/', content)
    hashes = ' '.join("'sha256-" + base64.b64encode(hashlib.sha256(parts[k].encode()).digest()).decode() + "'" for k in ('CORE','APP'))
    csp = "default-src 'none'; script-src " + hashes + "; style-src 'unsafe-inline'; img-src 'self' data: https://raw.githubusercontent.com; manifest-src 'self'; connect-src 'self'; worker-src 'self'; base-uri 'none'; form-action 'none'"
    html = html.replace('<meta charset="utf-8">', '<meta charset="utf-8">\n<meta http-equiv="Content-Security-Policy" content="' + csp + '">')
    (DIST/'index.html').write_text(html, encoding='utf-8')
    portable = html.replace('<link rel="manifest" href="manifest.webmanifest">','').replace('<link rel="icon" href="assets/icon.svg" type="image/svg+xml">','')
    (ROOT/'Handheld-Atlas.html').write_text(portable, encoding='utf-8')
    for name in ['catalog.json','updates.json','candidates.json','research_queue.json','quality_report.json']:
        shutil.copy2(ROOT/'data'/name, DIST/'data'/name)
    svg = '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 192 192"><rect width="192" height="192" rx="36" fill="#b2f4cb"/><g fill="none" stroke="#163022" stroke-width="11"><rect x="44" y="40" width="104" height="45" rx="5"/><rect x="44" y="107" width="104" height="45" rx="5"/></g></svg>'
    (DIST/'assets/icon.svg').write_text(svg)
    for size in (192,512):
        (DIST/f'assets/icon-{size}.png').write_bytes(icon_png(size))
    manifest = {'id':'./','name':'Handheld Atlas','short_name':'Atlas','lang':'de',
        'description':'Spielwege, Ports und Mods fuer Android- und offene Handhelds entdecken.',
        'start_url':'./','scope':'./','display':'standalone','background_color':'#101316','theme_color':'#101316',
        'icons':[{'src':f'assets/icon-{n}.png','sizes':f'{n}x{n}','type':'image/png','purpose':'any maskable'} for n in (192,512)]}
    (DIST/'manifest.webmanifest').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    version = hashlib.sha256(html.encode()).hexdigest()[:14]
    sw = '''/* Local assets only. Never cache external downloads or execute remote code. */
const CACHE = 'atlas-VERSION';
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
'''.replace('VERSION',version)
    (DIST/'sw.js').write_text(sw,encoding='utf-8')
    (DIST/'.nojekyll').touch()
    print('Built', DIST, 'and Handheld-Atlas.html; cache',version)

if __name__ == '__main__':
    build()
