#!/usr/bin/env python3
"""Pictures from web pages – the part of the image search that does NOT need AI.

The model behind the KI-Recherche can find *pages* reliably (its web search returns them), but it rarely sees the
image URLs inside them. So the AI names pages (a YouTube video, a GitHub README, a Reddit post, a store page …) and
this module pulls the pictures out of each page deterministically:

    YouTube        video thumbnail (i.ytimg.com)
    GitHub         README/markdown file images, images in the newest release notes
    Steam          store screenshots (appdetails API)
    Google Play    store screenshots (play-lh.googleusercontent.com)
    Wikipedia      images of the article (cover and in-game screenshots), via the API
    Reddit         image of the post / gallery (post JSON)
    anything else  og:image / twitter:image and large <img> tags

Every picture keeps the page it came from as `source`; ai_vision.py checks each one before it counts as verified.
"""
import html
import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import media  # noqa: E402

UA = 'Mozilla/5.0 (compatible; HandheldAtlas/1.3; +https://github.com/markusklier/handheld-atlas)'
IMG_EXT = re.compile(r'\.(png|jpe?g|webp|gif)(\?|$)', re.I)
SKIP = re.compile(r'logo|icon|favicon|avatar|sprite|badge|banner-ad|placeholder|blank\.|spacer|emoji|/flags?/|'
                  r'wordmark|\.svg|pixel\.gif|tracking|1x1', re.I)


def get(url, as_json=False, timeout=20):
    req = urllib.request.Request(url, headers={'User-Agent': UA, 'Accept-Language': 'en,de;q=0.8'})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read(3_000_000).decode('utf-8', 'replace')
    return json.loads(body) if as_json else body


def youtube_id(url):
    m = re.search(r'(?:youtube\.com/(?:watch\?(?:.*&)?v=|shorts/|embed/|live/)|youtu\.be/)([A-Za-z0-9_-]{11})', url)
    return m.group(1) if m else None


def shot(url, source, caption=''):
    return {'url': url, 'source': source, 'caption': caption}


def from_youtube(url, fetch=get):
    vid = youtube_id(url)
    if not vid:
        return []
    # maxresdefault exists for most HD uploads; hqdefault always exists (letterboxed 4:3)
    return [shot(f'https://i.ytimg.com/vi/{vid}/maxresdefault.jpg', f'https://www.youtube.com/watch?v={vid}', 'Video-Vorschaubild')]


def from_github(url, fetch=get, fetch_json=None):
    m = re.match(r'https://github\.com/([^/#?]+/[^/#?]+)(?:/(blob|tree|releases)(?:/tag)?/([^#?]+))?', url)
    if not m:
        return []
    repo, kind, rest = m.group(1), m.group(2), m.group(3) or ''
    out = []
    if kind == 'blob' and re.search(r'\.(md|markdown)$', rest, re.I):          # a specific markdown file
        raw = f'https://raw.githubusercontent.com/{repo}/{rest}'
        try:
            out += media.readme_images(fetch(raw), raw, repo)
        except Exception:  # noqa: BLE001
            pass
    if kind != 'releases':
        branch = rest.split('/')[0] if kind == 'tree' and rest else None
        raw, text = media.readme(repo, branch, fetch)
        if text:
            out += media.readme_images(text, raw, repo)
    out += media.release_images(repo, fetch_json)
    src = f'https://github.com/{repo}'
    seen = set()
    return [shot(i['url'], url if kind else src, media.caption_from(i.get('alt', ''), i['url']))
            for i in out if not (i['url'] in seen or seen.add(i['url']))]


def from_steam(url, fetch=get):
    m = re.search(r'store\.steampowered\.com/app/(\d+)', url)
    if not m:
        return []
    data = (fetch(f'https://store.steampowered.com/api/appdetails?appids={m.group(1)}', as_json=True)
            .get(m.group(1)) or {}).get('data') or {}
    return [shot(s['path_full'], f'https://store.steampowered.com/app/{m.group(1)}/', 'Originalspiel')
            for s in data.get('screenshots', [])[:6]]


def from_play(url, fetch=get):
    if 'play.google.com/store/apps/details' not in url:
        return []
    page = fetch(url + ('&' if '?' in url else '?') + 'hl=de')
    urls = list(dict.fromkeys(re.findall(r'https://play-lh\.googleusercontent\.com/[A-Za-z0-9_-]{20,}', page)))
    # the first ones are the app icon and feature graphic; screenshots follow
    return [shot(u + '=w1280-h720', url, 'Google Play') for u in urls[2:8]]


def from_wikipedia(url, fetch=get):
    m = re.match(r'https://([a-z]+)\.wikipedia\.org/wiki/([^#?]+)', url)
    if not m:
        return []
    lang, title = m.group(1), urllib.parse.unquote(m.group(2))
    api = f'https://{lang}.wikipedia.org/w/api.php?' + urllib.parse.urlencode({
        'action': 'query', 'titles': title, 'generator': 'images', 'gimlimit': 20, 'prop': 'imageinfo',
        'iiprop': 'url|size|mime', 'redirects': 1, 'format': 'json', 'formatversion': 2})
    pages = (fetch(api, as_json=True).get('query') or {}).get('pages') or []
    out = []
    for p in pages:
        info = (p.get('imageinfo') or [{}])[0]
        name = p.get('title', '')
        if info.get('mime') not in ('image/png', 'image/jpeg', 'image/webp') or SKIP.search(name) or info.get('width', 0) < 250:
            continue
        cap = re.sub(r'^(File|Datei):|\.\w+$', '', name).replace('_', ' ')
        # articles also show developers, places, other games: keep files named after the game or screenshots
        words = {w for w in re.findall(r'[a-z0-9]{4,}', title.lower().replace('_', ' ')) if w not in ('video', 'game')}
        flat = re.sub(r'[^a-z0-9]', '', name.lower())
        if not (any(w in flat for w in words) or re.search(r'screen|gameplay|ingame|in-game|level|cover|box', name, re.I)):
            continue
        out.append(shot(info['url'].split('?')[0], url, cap))
    return out


def from_reddit(url, fetch=get):
    if not re.search(r'reddit\.com/r/[^/]+/comments/', url):
        return []
    data = fetch(url.split('?')[0].rstrip('/') + '.json?raw_json=1', as_json=True)
    post = data[0]['data']['children'][0]['data']
    out = []
    target = post.get('url_overridden_by_dest') or ''
    if IMG_EXT.search(target):
        out.append(target)
    for item in (post.get('media_metadata') or {}).values():
        s = (item.get('s') or {}).get('u')
        if s:
            out.append(html.unescape(s))
    for img in (post.get('preview') or {}).get('images', []):
        if img.get('source', {}).get('url'):
            out.append(html.unescape(img['source']['url']))
    return [shot(u, url, (post.get('title') or '')[:80]) for u in dict.fromkeys(out)]


def from_html(url, fetch=get):
    page = fetch(url)
    head = page[:page.find('<body')] if '<body' in page else page[:20000]
    # only the article itself – sidebars and "related posts" show other games
    m = re.search(r'<article\b.*?</article>', page, re.S | re.I) or re.search(r'<main\b.*?</main>', page, re.S | re.I)
    body = m.group(0) if m else page
    found = re.findall(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::src)?["\'][^>]+content=["\']([^"\']+)', head, re.I)
    found += re.findall(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)', head, re.I)
    for m in re.finditer(r'<img\b[^>]*>', body, re.I):
        tag = m.group(0)
        src = re.search(r'\b(?:data-src|src)=["\']([^"\']+)', tag)
        w = re.search(r'\bwidth=["\']?(\d+)', tag)
        if src and (not w or int(w.group(1)) >= 400):
            found.append(src.group(1))
    out = []
    for u in found:
        u = urllib.parse.urljoin(url, html.unescape(u))
        if u.startswith('https://') and IMG_EXT.search(u) and not SKIP.search(u):
            out.append(u)
    return [shot(u, url) for u in list(dict.fromkeys(out))[:6]]


def same_image(a, b):
    """raw.githubusercontent …/HEAD/x.png = …/main/x.png; Wikimedia URLs differ only in tracking parameters."""
    def k(u):
        u = (u or '').split('?')[0] if 'wikimedia.org' in (u or '') else (u or '')
        return re.sub(r'^(https://raw\.githubusercontent\.com/[^/]+/[^/]+)/[^/]+/', r'\1/@/', u)
    return k(a) == k(b)


def images_from_page(url, fetch=get, fetch_json=None, log=print):
    """All pictures we can get out of one page, best first. Never raises."""
    try:
        if youtube_id(url):
            return from_youtube(url, fetch)
        if url.startswith('https://github.com/'):
            return from_github(url, fetch, fetch_json)
        if 'store.steampowered.com/app/' in url:
            return from_steam(url, fetch)
        if 'play.google.com/store/apps/details' in url:
            return from_play(url, fetch)
        if '.wikipedia.org/wiki/' in url:
            return from_wikipedia(url, fetch)
        if 'reddit.com/r/' in url:
            return from_reddit(url, fetch)
        if IMG_EXT.search(url):
            return [shot(url, url)]
        return from_html(url, fetch)
    except Exception as e:  # noqa: BLE001 – a page we cannot read just yields nothing
        log(f'    ! {url[:90]}: {type(e).__name__}: {str(e)[:80]}')
        return []
