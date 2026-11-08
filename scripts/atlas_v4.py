"""Build Atlas 0.4's auto-visible, clearly untested discovery feed.

This job does NOT claim compatibility, run third-party code or install anything.
Raw provider and AI leads stay separate from reviewed catalog routes.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from datetime import datetime, timezone
from sync_sources import atomic_json

ROOT = Path(__file__).resolve().parents[1]
PROJECT_HOSTS = {'github.com', 'modrinth.com', 'www.curseforge.com', 'andreyvelsk.github.io', 'opengameports.com'}
IMAGE_HOSTS = {'raw.githubusercontent.com', 'cdn.modrinth.com', 'media.forgecdn.net', 'mediafilez.forgecdn.net'}

# Broad searches can match pets and unrelated HUD widgets; retain raw leads
# without publishing them as Android handheld or dual-screen game paths.
HANDHELD_MOD_TERMS = re.compile(
    r'\b(?:dual[ -]?screens?|second[ -]?screens?|secondary[ -]?displays?|'
    r'two[ -]?screens?|multi[ -]?screens?|second[ -]?monitors?|'
    r'ayn[ -]?thor|android[ -]?handhelds?|droidbridge|pojavlauncher|zalithlauncher)\b',
    re.I)

def handheld_mod_relevant(item):
    text = ' '.join(str(item.get(key) or '') for key in ('project', 'label'))
    return bool(HANDHELD_MOD_TERMS.search(text))


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')

def read(name, default):
    path = ROOT / 'data' / name
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def clean_url(raw, hosts):
    try:
        u = urlsplit(str(raw or '').strip())
        if u.scheme != 'https' or not u.hostname or u.hostname.lower() not in hosts or u.username or u.password or u.port or '\\' in u.path:
            return None
        return urlunsplit(('https', u.hostname.lower(), u.path, '', ''))
    except (ValueError, TypeError):
        return None

def project_url(raw):
    url = clean_url(raw, PROJECT_HOSTS)
    if not url: return None
    u = urlsplit(url)
    path = u.path.rstrip('/')
    if u.hostname == 'github.com':
        match = re.fullmatch(r'/([\w.-]+)/([\w.-]+)(?:/.*)?', path)
        if not match: return None
        path = '/' + match.group(1) + '/' + match.group(2).removesuffix('.git')
    return urlunsplit(('https', u.hostname, path, '', ''))

def media_url(raw):
    url = clean_url(raw, IMAGE_HOSTS)
    return url if url and re.search(r'\.(png|jpe?g|webp)$', urlsplit(url).path, re.I) else None

def project_id(url):
    return hashlib.sha256(url.lower().encode()).hexdigest()[:18]

def caption(value, length=220):
    return re.sub(r'[\x00-\x1f]+', ' ', str(value or '')).strip()[:length]

def make_index(catalog, research, source_candidates, ai, vision, previous=None, stamp=None):
    stamp = stamp or now()
    old = {p['id']:p for p in (previous or {}).get('projects', [])}
    projects = {}
    known_games = {g['id'] for g in catalog['games']} | {g['id'] for g in catalog.get('gameIndex', [])}
    def entry(raw_url, title, origin, game_id=None, is_curated=False):
        url = project_url(raw_url)
        if not url: return None
        pid = project_id(url)
        if pid not in projects:
            existing = old.get(pid, {})
            projects[pid] = {'id': pid, 'url': url, 'name': caption(title, 130) or url.rsplit('/', 1)[-1],
                'gameIds': [], 'routeIds': [], 'providers': [], 'evidence': [], 'media': [],
                'firstSeenAt': existing.get('firstSeenAt') or stamp, 'lastSeenAt': existing.get('lastSeenAt') or stamp,
                'curated': False, 'documentation': 'candidate', 'deviceTest': 'not-tested'}
        p = projects[pid]
        if is_curated: p['curated'] = True; p['documentation'] = 'curated'
        if game_id in known_games and game_id not in p['gameIds']:p['gameIds'].append(game_id)
        if origin not in p['providers']:p['providers'].append(origin)
        return p
    # Existing approved catalog is not a new discovery; connect project records to routes.
    for game in catalog['games']:
        for route in game['routes']:
            for sid in route.get('sources', []):
                source = next((s for s in catalog['sources'] if s['id'] == sid), None)
                if not source or not source.get('repo'):continue
                p = entry('https://github.com/' + source['repo'], source['name'], 'catalog', game['id'], True)
                if p and route['id'] not in p['routeIds']:p['routeIds'].append(route['id'])
    # Only genuinely live provider results. Historical offline fixtures never surface as news.
    for item in research.get('candidates', []):
        if item.get('discoveryMode') != 'live' or item.get('status') == 'rejected':continue
        if item.get('provider') == 'modrinth' and not handheld_mod_relevant(item):continue
        url = project_url(item.get('url'))
        if not url:continue
        evidence = [e for e in item.get('evidence', [])[:5] if clean_url(e.get('sourceUrl'), PROJECT_HOSTS)]
        if not evidence:continue  # no provenance = no published claim
        p = entry(url, item.get('project'), item.get('provider', 'api'), item.get('gameId'))
        if not p:continue
        for e in evidence:
            snippet = caption(e.get('excerpt'), 320)
            record = {'sourceUrl': clean_url(e['sourceUrl'], PROJECT_HOSTS), 'excerpt': snippet}
            if record not in p['evidence'] and snippet:p['evidence'].append(record)
        for m in item.get('mediaCandidates', [])[:6]:
            image = media_url(m.get('url'))
            origin = clean_url(m.get('sourceUrl'), PROJECT_HOSTS)
            if image and origin and not any(x['url'] == image for x in p['media']):
                vr = vision.get('results', {}).get(hashlib.sha256(image.encode()).hexdigest()[:20], {})
                p['media'].append({'url': image, 'caption': caption(m.get('caption'), 130), 'sourceUrl': origin,
                   'vision': vr.get('verdict', 'not-checked'), 'rights': 'not-cleared'})
        p['documentation'] = 'primary-source-lead' if not p['curated'] else 'curated'
        p['lastSeenAt'] = item.get('lastSeenAt') or stamp
    # Generic repository search detects names not covered by any target query.
    for item in source_candidates.get('candidates', [])[:300]:
        url = project_url(item.get('url'))
        if not url:continue
        p = entry(url, item.get('label') or item.get('repo'), 'github-search')
        if p and not p['curated']:
            p['documentation'] = 'unclassified-lead'
            p['lastSeenAt'] = item.get('discoveredAt') or stamp
    # AI web-search leads remain explicitly AI leads (never community/device tested).
    for item in ai.get('findings', [])[:150]:
        url = project_url(item.get('url'))
        source = clean_url(item.get('sourceUrl'), PROJECT_HOSTS)
        if not url or not source or item.get('gameId') not in known_games:continue
        p = entry(url, item.get('name'), 'ai-search', item.get('gameId'))
        if not p:continue
        p['lastSeenAt'] = item.get('foundAt') or stamp
        record = {'sourceUrl': source, 'excerpt': caption(item.get('excerpt'), 320)}
        if record not in p['evidence']:p['evidence'].append(record)
        if not p['curated'] and p['documentation'] in ('candidate', 'unclassified-lead'):
            p['documentation'] = 'ai-source-lead'
    for p in projects.values():
        p['gameIds'].sort();p['routeIds'].sort();p['providers'].sort()
        p['media'] = p['media'][:6]
        p['evidence'] = p['evidence'][:8]
    ordered = sorted(projects.values(), key=lambda p:(p['curated'], not bool(p['gameIds']), p['firstSeenAt'], p['name'].lower()))
    live = [p for p in ordered if not p['curated']]
    return {'schemaVersion': 1, 'generatedAt': stamp, 'warning': 'Automatische Funde sind KEINE Kompatibilitätstests. Rechte an Projektbildern sind ungeklärt.',
            'projects': ordered, 'discoveredCount': len(live), 'totalProjects': len(ordered)}

def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    result = make_index(read('catalog.json', {}), read('research_queue.json', {}),
                        read('candidates.json', {}), read('ai_findings.json', {}),
                        read('vision_reviews.json', {}), read('projects.json', {}))
    if not args.dry_run:atomic_json(ROOT/'data/projects.json', result)
    print(json.dumps({'projects': result['totalProjects'], 'newLeads': result['discoveredCount'], 'written': not args.dry_run}))

if __name__ == '__main__':main()
