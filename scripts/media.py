#!/usr/bin/env python3
"""Fill image gaps without AI. Images are linked, never copied.

1. Screenshots per way to play: images from the README of the route's own project
   (only game-specific projects, so a generic emulator README never ends up on a game).
   Marked  check: "readme"  – the maintenance agent looks at them and confirms or removes them.
2. Covers + original screenshots for PC games from the Steam store.
3. Cover fallback for any game still without one: lead image of the English Wikipedia article
   (only if the article is described as a video game).

    python3 scripts/media.py [--routes] [--steam] [--wikipedia]   (default: all three)
"""
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from atlas import DATA, read, write  # noqa: E402

UA = 'handheld-atlas-media/1.0 (+https://github.com/markusklier/handheld-atlas)'
log = lambda *a: print(*a, file=sys.stderr)
IMG_RE = re.compile(r'!\[([^\]]*)\]\(\s*<?([^)\s>]+)>?(?:\s+"[^"]*")?\s*\)|<img[^>]*?src=["\']([^"\']+)["\'][^>]*>', re.I)
ALT_RE = re.compile(r'alt=["\']([^"\']*)["\']', re.I)
SKIP_IMG = re.compile(r'shields\.io|badge|badgen|logo|icon|favicon|banner-ad|ko-fi|buymeacoffee|paypal|patreon|discord|'
                      r'githubusercontent\.com/u/|avatars|star-history|contrib\.rocks|\.svg(\?|$)|/workflows/|codecov|'
                      r'sponsor|qr[-_ ]?code|powered[-_ ]?by|lightmode|darkmode|og\.png|opengraph|social[-_]?preview', re.I)
MAX_ROUTE_SHOTS = 6


def get(url, as_json=False):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=25) as r:
        body = r.read().decode('utf-8', 'replace')
    return json.loads(body) if as_json else body


def norm(s):
    s = re.sub(r'[™®©]', '', s or '')  # before NFKD, which would turn ™ into "TM"
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower().replace('&', 'and')
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


# ---------------- 1. route screenshots from project READMEs ----------------
def readme(repo, branch=None, fetch=get):
    refs = [branch] if branch else ['HEAD']
    for ref in refs:
        for name in ('README.md', 'readme.md', 'Readme.md', 'README.MD', 'README.markdown'):
            url = f'https://raw.githubusercontent.com/{repo}/{ref}/{name}'
            try:
                return url, fetch(url)
            except Exception:  # noqa: BLE001 – try the next spelling
                continue
    return None, None


def readme_images(text, raw_url, repo, branch='HEAD'):
    """Image URLs (absolute, raw) with alt text, badges/logos filtered out."""
    out, seen = [], set()
    base = raw_url.rsplit('/', 1)[0] + '/'
    for m in IMG_RE.finditer(text):
        alt, src = (m.group(1) or ''), (m.group(2) or m.group(3) or '')
        if m.group(3):
            a = ALT_RE.search(m.group(0))
            alt = a.group(1) if a else ''
        if not src or src.startswith('data:') or SKIP_IMG.search(src) or SKIP_IMG.search(alt):
            continue
        if src.startswith('//'):
            src = 'https:' + src
        elif not src.startswith('http'):
            src = urllib.parse.urljoin(base, src.lstrip('./') if not src.startswith('/') else src[1:])
            if src.startswith('https://raw.githubusercontent.com/') and src.count('/') < 6:
                continue
        # github.com/<repo>/blob/<ref>/x.png -> raw
        src = re.sub(r'^https://github\.com/([^/]+/[^/]+)/blob/(.+)$', r'https://raw.githubusercontent.com/\1/\2', src)
        src = re.sub(r'^https://github\.com/([^/]+/[^/]+)/raw/(.+)$', r'https://raw.githubusercontent.com/\1/\2', src)
        if not re.search(r'\.(png|jpe?g|webp|gif)(\?|$)', src, re.I) and 'user-attachments/assets' not in src \
                and 'user-images.githubusercontent.com' not in src:
            continue
        if src in seen:
            continue
        seen.add(src)
        out.append({'url': src, 'alt': alt.strip()})
    return out


def caption_from(alt, url):
    text = alt or urllib.parse.unquote(url.rsplit('/', 1)[-1].rsplit('.', 1)[0])
    text = re.sub(r'[_-]+', ' ', text).strip()
    return (text[:1].upper() + text[1:])[:80] if text else 'Screenshot'


def fill_route_shots(fetch=get):
    projects = {p['id']: p for p in read(DATA / 'projects.json')['projects']}
    cache, added = {}, 0
    for f in sorted((DATA / 'games').glob('*.json')):
        g = read(f)
        changed = False
        for r in g.get('routes', []):
            if r.get('screenshots'):
                continue
            for pid in r.get('projects', []):
                p = projects.get(pid, {})
                repo = p.get('repo')
                # only game-specific projects: a generic emulator README says nothing about this game
                if not repo or len(p.get('games', [])) > 3 or p.get('kind') in ('emulator', 'directory', 'data-source', 'runtime'):
                    continue
                key = (repo, p.get('branch'))
                if key not in cache:
                    url, text = readme(repo, p.get('branch'), fetch)
                    cache[key] = (url, readme_images(text, url, repo) if text else [])
                url, images = cache[key]
                if not images:
                    continue
                source = f"https://github.com/{repo}" + (f"/tree/{p['branch']}" if p.get('branch') else '')
                r['screenshots'] = [{'url': i['url'], 'caption': caption_from(i['alt'], i['url']), 'source': source,
                                     'credit': p['name'], 'check': 'readme'} for i in images[:MAX_ROUTE_SHOTS]]
                changed = True
                added += 1
                break
        if changed:
            write(f, g)
    print(f'media.py: {added} Spielwege mit README-Screenshots ergänzt')
    return added


# ---------------- 2. Steam (PC games) ----------------
def steam_lookup(title, fetch=get):
    res = fetch('https://store.steampowered.com/api/storesearch/?' + urllib.parse.urlencode(
        {'term': title, 'cc': 'de', 'l': 'german'}), as_json=True)
    want = norm(title)
    for item in res.get('items', []):
        if norm(item.get('name')) == want:
            return item['id']
    return None


def fill_steam(fetch=get, pause=0.7):
    added = 0
    state = load_state()
    for f in sorted((DATA / 'games').glob('*.json')):
        g = read(f)
        if 'PC' not in g.get('platforms', []) or g.get('cover') or recently_tried(state, 'steam', g['id']):
            continue
        mark_tried(state, 'steam', g['id'])
        write(DATA / 'media_state.json', state)
        if pause:
            time.sleep(pause)
        try:
            appid = steam_lookup(g['title'], fetch)
            if not appid:
                continue
            details = fetch(f'https://store.steampowered.com/api/appdetails?appids={appid}&l=german', as_json=True)
        except Exception as e:  # noqa: BLE001
            log(f'! Steam {g["title"]}: {e}')
            continue
        data = (details.get(str(appid)) or {}).get('data') or {}
        if not data:
            continue
        store = f'https://store.steampowered.com/app/{appid}/'
        cover = f'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/library_600x900_2x.jpg'
        try:
            urllib.request.urlopen(urllib.request.Request(cover, method='HEAD', headers={'User-Agent': UA}), timeout=15)
        except Exception:  # noqa: BLE001 – older games have no library art; header image is landscape but better than nothing
            cover = data.get('header_image')
        if cover:
            g['cover'] = {'url': cover, 'source': store}
        shots = [{'url': s['path_full'], 'caption': 'Originalspiel', 'source': store} for s in data.get('screenshots', [])[:6]]
        if shots and not g.get('screenshots'):
            g['screenshots'] = shots
        write(f, g)
        added += 1
    print(f'media.py: {added} PC-Spiele mit Steam-Cover/Screenshots ergänzt')
    return added


# ---------------- 3. Wikipedia cover fallback ----------------
def wikipedia_cover(title, fetch=get):
    """Both spellings in one request; Wikimedia rate-limits bursts (HTTP 429)."""
    q = urllib.parse.urlencode({'action': 'query', 'titles': f'{title} (video game)|{title}', 'prop': 'pageimages|description',
                                'piprop': 'thumbnail', 'pithumbsize': 600, 'pilicense': 'any', 'redirects': 1, 'format': 'json',
                                'formatversion': 2, 'maxlag': 5})
    res = fetch('https://en.wikipedia.org/w/api.php?' + q, as_json=True)
    pages = sorted(res.get('query', {}).get('pages', []), key=lambda p: '(video game)' not in p.get('title', ''))
    for page in pages:
        desc = (page.get('description') or '').lower()
        thumb = (page.get('thumbnail') or {}).get('source')
        if thumb and 'game' in desc and 'series' not in desc and not page.get('missing') \
                and not re.search(r'\.svg', thumb, re.I) and same_edition(title, page['title']):
            return thumb, 'https://en.wikipedia.org/wiki/' + urllib.parse.quote(page['title'].replace(' ', '_'))
    return None, None


EDITION_WORDS = {'remaster', 'remastered', 'remake', 'deluxe', 'royal', 'hd', 'definitive', 'edition', 'reload',
                 'portable', 'golden', 'complete', 'anniversary', 'reloaded', 'rebirth', 'leifthrasir', 'vita', 'switch',
                 '3d', 'ds', 'dx', 'redux', 'collection', 'eternal'}


def same_edition(game_title, page_title):
    """Wikipedia redirects remakes to the original ("Metroid Prime Remastered" -> "Metroid Prime"): reject those."""
    page_words = set(norm(page_title).split())
    return all(w in page_words for w in set(norm(game_title).split()) & EDITION_WORDS)


def load_state():
    path = DATA / 'media_state.json'
    return read(path) if path.exists() else {'wikipedia': {}, 'steam': {}}


def recently_tried(state, source, gid, days=30):
    from datetime import date, timedelta
    last = state.setdefault(source, {}).get(gid)
    return bool(last) and last >= (date.today() - timedelta(days=days)).isoformat()


def mark_tried(state, source, gid):
    from datetime import date
    state.setdefault(source, {})[gid] = date.today().isoformat()


def fill_wikipedia(fetch=get, pause=1.0, limit=250):
    added = tried = 0
    state = load_state()
    for f in sorted((DATA / 'games').glob('*.json')):
        g = read(f)
        if g.get('cover') or tried >= limit or recently_tried(state, 'wikipedia', g['id']):
            continue
        tried += 1
        mark_tried(state, 'wikipedia', g['id'])
        url = None
        for attempt in range(2):
            try:
                url, source = wikipedia_cover(g['title'], fetch)
                break
            except Exception as e:  # noqa: BLE001
                if '429' in str(e) and attempt == 0:
                    time.sleep(20)
                    continue
                log(f'! Wikipedia {g["title"]}: {e}')
        if pause:
            time.sleep(pause)
        if url:
            g['cover'] = {'url': url, 'source': source}
            write(f, g)
            added += 1
    write(DATA / 'media_state.json', state)
    print(f'media.py: {added} Cover aus Wikipedia ergänzt ({tried} versucht)')
    return added


if __name__ == '__main__':
    args = set(sys.argv[1:]) or {'--routes', '--steam', '--wikipedia'}
    if '--routes' in args:
        fill_route_shots()
    if '--steam' in args:
        fill_steam()
    if '--wikipedia' in args:
        fill_wikipedia()
