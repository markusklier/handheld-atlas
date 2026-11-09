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
import os
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
        if not src.startswith('https://'):   # http images break validation (and mixed content in the app)
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


def release_images(repo, fetch_json=None):
    """Images embedded in the newest release notes (often the freshest screenshots of a port)."""
    token = os.environ.get('GITHUB_TOKEN')
    fetch_json = fetch_json or (lambda url: json.loads(urllib.request.urlopen(urllib.request.Request(url, headers={
        'User-Agent': UA, 'Accept': 'application/vnd.github+json', **({'Authorization': f'Bearer {token}'} if token else {})}),
        timeout=25).read().decode()))
    out = []
    try:
        for rel in fetch_json(f'https://api.github.com/repos/{repo}/releases?per_page=3') or []:
            out += readme_images(rel.get('body') or '', f'https://raw.githubusercontent.com/{repo}/HEAD/RELEASE.md', repo)
    except Exception as e:  # noqa: BLE001 – releases are a bonus
        log(f'! Releases {repo}: {e}')
    return out


def fill_route_shots(fetch=get, fetch_json=None, only=None):
    """New README/release-note images for game-specific projects; also tops up routes that already have pictures.
    Images rejected by ai_vision.py (media_state.json → rejectedImages) never come back."""
    projects = {p['id']: p for p in read(DATA / 'projects.json')['projects']}
    rejected = set(load_state().get('rejectedImages', []))
    cache, added = {}, 0
    for f in sorted((DATA / 'games').glob('*.json')):
        if only is not None and f.stem not in only:
            continue
        g = read(f)
        changed = False
        for r in g.get('routes', []):
            have = {s['url'] for s in r.get('screenshots', [])}
            if len(have) >= MAX_ROUTE_SHOTS:
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
                    imgs = readme_images(text, url, repo) if text else []
                    cache[key] = imgs + [i for i in release_images(repo, fetch_json) if i['url'] not in {x['url'] for x in imgs}]
                new = [i for i in cache[key] if i['url'] not in have and i['url'] not in rejected]
                if not new:
                    continue
                source = f"https://github.com/{repo}" + (f"/tree/{p['branch']}" if p.get('branch') else '')
                room = MAX_ROUTE_SHOTS - len(have)
                r.setdefault('screenshots', []).extend(
                    {'url': i['url'], 'caption': caption_from(i['alt'], i['url']), 'source': source,
                     'credit': p['name'], 'check': 'readme'} for i in new[:room])
                changed = True
                added += 1
                break
        if changed:
            write(f, g)
    print(f'media.py: {added} Spielwege mit neuen README-/Release-Bildern ergänzt')
    return added


# ---------------- 2. Steam (PC games) ----------------
def steam_lookup(title, fetch=get):
    want = norm(title)
    for cc in ('de', 'us'):             # some games are not sold in Germany (or only under another store region)
        res = fetch('https://store.steampowered.com/api/storesearch/?' + urllib.parse.urlencode(
            {'term': title, 'cc': cc, 'l': 'english'}), as_json=True)
        for item in res.get('items', []):
            if norm(item.get('name')) == want:
                return item['id']
    return None


def fill_steam(fetch=get, pause=0.7, only=None):
    added = 0
    state = load_state()
    for f in sorted((DATA / 'games').glob('*.json')):
        if only is not None and f.stem not in only:
            continue
        g = read(f)
        wanted = not g.get('cover') or (only is not None and not g.get('screenshots'))   # on request: screenshots too
        if 'PC' not in g.get('platforms', []) or not wanted or (only is None and recently_tried(state, 'steam', g['id'])):
            continue
        mark_tried(state, 'steam', g['id'])
        write(DATA / 'media_state.json', state)
        if pause:
            time.sleep(pause)
        try:
            appid = steam_lookup(re.sub(r'\s*\(\d{4}\)$', '', g['title']), fetch)
            if not appid:
                continue
            details = fetch(f'https://store.steampowered.com/api/appdetails?appids={appid}&l=german', as_json=True)
        except Exception as e:  # noqa: BLE001
            log(f'! Steam {g["title"]}: {e}')
            continue
        data = (details.get(str(appid)) or {}).get('data') or {}
        if not data:
            continue
        ty = re.search(r'\((\d{4})\)$', g['title'])
        sy = re.search(r'(19|20)\d\d', (data.get('release_date') or {}).get('date') or '')
        if ty and sy and abs(int(sy.group(0)) - int(ty.group(1))) > 1:
            continue                     # "DOOM (1993)" must not get the Steam page of DOOM (2016)
        store = f'https://store.steampowered.com/app/{appid}/'
        cover = f'https://shared.fastly.steamstatic.com/store_item_assets/steam/apps/{appid}/library_600x900_2x.jpg'
        try:
            urllib.request.urlopen(urllib.request.Request(cover, method='HEAD', headers={'User-Agent': UA}), timeout=15)
        except Exception:  # noqa: BLE001 – older games have no library art; header image is landscape but better than nothing
            cover = data.get('header_image')
        if cover and not g.get('cover'):
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
    m = re.match(r'^(.*) \((\d{4})\)$', title)          # "DOOM (1993)" -> "DOOM (1993 video game)"
    base, year = (m.group(1), m.group(2)) if m else (title, None)
    names = [base] + ([' '.join(w.capitalize() if w.isupper() and len(w) > 2 else w for w in base.split())]
                      if any(w.isupper() and len(w) > 2 for w in base.split()) else [])   # "DOOM" → also "Doom"
    names = list(dict.fromkeys(names))
    titles = '|'.join([f'{n} ({year} video game)' for n in names] + [f'{n} (video game)' for n in names] + names) if year \
        else '|'.join([f'{n} (video game)' for n in names] + names)
    q = urllib.parse.urlencode({'action': 'query', 'titles': titles, 'prop': 'pageimages|description',
                                'piprop': 'thumbnail', 'pithumbsize': 600, 'pilicense': 'any', 'redirects': 1, 'format': 'json',
                                'formatversion': 2, 'maxlag': 5})
    res = fetch('https://en.wikipedia.org/w/api.php?' + q, as_json=True)
    pages = sorted(res.get('query', {}).get('pages', []), key=lambda p: ('video game)' not in p.get('title', ''), year not in p.get('title', '') if year else 0))
    for page in pages:
        desc = (page.get('description') or '').lower()
        if year and year not in desc and year not in page.get('title', ''):
            continue                                  # another game of the same name
        thumb = (page.get('thumbnail') or {}).get('source')
        if thumb and 'game' in desc and 'series' not in desc and not page.get('missing') \
                and not re.search(r'\.svg', thumb, re.I) and same_edition(base, page['title']):
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


def article_cover(article, fetch=get):
    """Cover of a known Wikipedia article: its lead image, else a file named like box art in the article."""
    m = re.match(r'https://([a-z]+)\.wikipedia\.org/wiki/([^#?]+)', article or '')
    if not m:
        return None, None
    lang, title = m.group(1), urllib.parse.unquote(m.group(2)).replace('_', ' ')
    q = urllib.parse.urlencode({'action': 'query', 'titles': title, 'prop': 'pageimages|description', 'piprop': 'thumbnail|name',
                                'pithumbsize': 600, 'pilicense': 'any', 'redirects': 1, 'format': 'json', 'formatversion': 2})
    pages = fetch(f'https://{lang}.wikipedia.org/w/api.php?{q}', as_json=True).get('query', {}).get('pages', [])
    page = pages[0] if pages else {}
    if 'game' not in (page.get('description') or '').lower():
        return None, None                           # not (or no longer) a video game article
    thumb = (page.get('thumbnail') or {}).get('source')
    if thumb and not re.search(r'\.svg', thumb, re.I) and not re.search(r'logo|wordmark', thumb, re.I):
        return thumb, article
    import images                                   # lead image is a logo: look for box art among the article's files
    files = images.from_wikipedia(article, fetch)
    box = [x for x in files if re.search(r'cover|box|packshot|key.?art|front', x['url'], re.I)]
    if box:
        return box[0]['url'], article
    # digital-only games often have no box art: a picture of the game from the article is still better than nothing
    shots = [x for x in files if not re.search(r'logo|wordmark|icon|\.svg|developer|founder|portrait|photo', x['url'], re.I)]
    return (shots[0]['url'], article + '#fallback') if shots else (None, None)


def fill_wikipedia(fetch=get, pause=1.0, limit=250, only=None):
    added = tried = 0
    state = load_state()
    for f in sorted((DATA / 'games').glob('*.json')):
        if only is not None and f.stem not in only:
            continue
        g = read(f)
        # missing covers are retried weekly; a newly known Wikipedia article (from Wikidata) is tried at once
        key = 'wikipedia' if not g.get('wikipedia') else 'wikipedia-article'
        if g.get('cover') or tried >= limit or (only is None and recently_tried(state, key, g['id'], days=7)):
            continue
        tried += 1
        mark_tried(state, key, g['id'])
        url = None
        for attempt in range(2):
            try:
                url, source = article_cover(g['wikipedia'], fetch) if g.get('wikipedia') else (None, None)
                if not url:
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
            g['cover'] = {'url': url, 'source': source.replace('#fallback', '')}
            if source.endswith('#fallback'):
                g['cover']['fallback'] = True    # only a picture from the article – replaced as soon as real art turns up
            write(f, g)
            added += 1
    write(DATA / 'media_state.json', state)
    print(f'media.py: {added} Cover aus Wikipedia ergänzt ({tried} versucht)')
    return added


def fill_website_covers(fetch=get, only=None, limit=100):
    """Official key art: og:image of the game's official website (Wikidata P856) for games without a real cover.
    Marked check 'ai' – the image check confirms it before it counts."""
    import images
    state, added, tried = load_state(), 0, 0
    for f in sorted((DATA / 'games').glob('*.json')):
        if only is not None and f.stem not in only:
            continue
        g = read(f)
        cov = g.get('cover') or {}
        pages = [p for p in (g.get('website'), g.get('playStore')) if p]
        if not pages or (cov and not cov.get('fallback')) or tried >= limit:
            continue
        if only is None and recently_tried(state, 'website', g['id'], days=14):
            continue
        tried += 1
        url = source = None
        reached = False
        for pg in pages:                    # official website first, then the Google Play listing (feature graphic)
            page = None
            for browser in (False, True):  # some publisher sites only answer browsers; the tags are in the first KB
                try:
                    page = images.get(pg, timeout=40, limit=400_000, browser=browser)
                    break
                except Exception as e:  # noqa: BLE001
                    log(f'! Website {g["title"]}: {str(e)[:80]}')
            if page is None:
                continue
            reached = True
            head = page[:page.find('<body')] if '<body' in page else page[:60000]
            m = re.search(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]+content=["\']([^"\']+)', head, re.I) or \
                re.search(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)', head, re.I)
            cand = urllib.parse.urljoin(pg, m.group(1).replace('&amp;', '&')) if m else None
            if cand and cand.startswith('https://') and not re.search(r'logo|favicon|\.svg', cand, re.I):
                if 'play-lh.googleusercontent.com' in cand:
                    cand = re.sub(r'=[^/]*$', '', cand) + '=w1280-h640'     # feature graphic in a usable size
                url, source = cand, pg
                break
        if reached:
            mark_tried(state, 'website', g['id'])   # unreachable sites are tried again tomorrow
        if not url:
            continue
        g['cover'] = {'url': url, 'source': source, 'check': 'ai'}
        write(f, g)
        added += 1
    write(DATA / 'media_state.json', state)
    print(f'media.py: {added} Cover von offiziellen Spieleseiten ({tried} versucht)')
    return added


if __name__ == '__main__':
    args = set(sys.argv[1:]) or {'--routes', '--steam', '--wikipedia'}
    if '--routes' in args:
        fill_route_shots()
    if '--steam' in args:
        fill_steam()
    if '--wikipedia' in args:
        fill_wikipedia()
        fill_website_covers()
