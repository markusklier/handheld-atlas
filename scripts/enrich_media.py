"""Enrich *live* game-project candidates with original project gallery links.

Fetches only official GitHub and Modrinth APIs; never downloads images, installs
code, or approves licences. Candidates retain original source links and status.
Runs with a small explicit request budget on GitHub Actions.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import urllib.error
import urllib.parse
from datetime import datetime, timezone

from deep_research import (
    ROOT, QUEUE, REPO, image_candidates, load_json, now, request_gh_readme,
    request_json, safe_project_image, write_json,
)

USER_AGENT = 'HandheldAtlasMedia/0.4.1 (metadata only; original images not copied)'
IMAGE_FILE = re.compile(r'\.(?:png|jpe?g|webp)$', re.I)
SHOTS_DIR = re.compile(r'(^|/)(?:screenshots?|gallery|previews?|demos?|docs/images)(/|$)', re.I)
SHOTS_FILE = re.compile(r'(^|/)(?:screenshots?|gameplay|preview|dual[-_]?screen)[-_ .]', re.I)
BAD_IMAGE = re.compile(r'(?:^|[.\-_/ ])(?:icon|logo|badge|button|avatar|sprite|favicon|tile|font)(?:[.\-_/ ]|$)', re.I)
SLUG = re.compile(r'^[A-Za-z0-9_-]{2,90}$')
HANDHELD_RE = re.compile(r'\b(?:dual[ -]?screens?|second[ -]?screens?|secondary[ -]?displays?|two[ -]?screens?|multi[ -]?screens?|second[ -]?monitors?|ayn[ -]?thor|android[ -]?handhelds?|droidbridge|pojavlauncher|zalithlauncher)\b', re.I)


def from_modrinth_gallery(gallery, project_url, max_images=6):
    """Accepts search-result URL strings or detailed project-gallery objects."""
    found = []
    if not isinstance(gallery, list):
        return found
    for item in gallery[:25]:
        raw = item if isinstance(item, str) else item.get('url') if isinstance(item, dict) else None
        url = safe_project_image(raw)
        if not url or url in {x['url'] for x in found}:
            continue
        name = (item.get('title') or item.get('description') or 'Projektgalerie') if isinstance(item, dict) else 'Projektgalerie'
        found.append({'url': url, 'caption': str(name).strip()[:140], 'sourceUrl': project_url,
                      'reviewStatus': 'needs-context-and-rights-review'})
        if len(found) >= max_images:
            break
    return found


def from_github_tree(files, repo, branch, limit=6):
    """Prefer screenshot/gallery paths; exclude icons and app UI assets."""
    if not REPO.fullmatch(repo) or not re.fullmatch(r'[A-Za-z0-9._/-]{1,130}', branch) or '..' in branch:
        return []
    if not isinstance(files, list):
        return []
    paths = []
    for entry in files[:5000]:
        if not isinstance(entry, dict) or entry.get('type') != 'blob':
            continue
        path = entry.get('path', '')
        if not isinstance(path, str) or not IMAGE_FILE.search(path):
            continue
        if path.startswith('/') or '\\' in path or '..' in path.split('/') or BAD_IMAGE.search(path):
            continue
        if not (SHOTS_DIR.search(path) or SHOTS_FILE.search(path)):
            continue
        rank = 0 if SHOTS_DIR.search(path) else 1
        paths.append((rank, path))
    out = []
    for _, path in sorted(set(paths)):
        safe_path = urllib.parse.quote(path, safe='/')
        prefix = f'https://raw.githubusercontent.com/{repo}/{branch}/'
        url = safe_project_image(prefix + safe_path)
        if not url:
            continue
        out.append({'url': url, 'caption': path.split('/')[-1].rsplit('.', 1)[0][:140].replace('_', ' '),
                    'sourceUrl': f'https://github.com/{repo}/blob/{branch}/' + safe_path,
                    'reviewStatus': 'needs-context-and-rights-review'})
        if len(out) >= limit:
            break
    return out


def eligible(candidate, stamp, game_id=None, force=False):
    if candidate.get('discoveryMode') != 'live' or candidate.get('provider') not in ('github', 'modrinth'):
        return False
    if game_id and candidate.get('gameId') != game_id:
        return False
    if candidate.get('status') == 'rejected':
        return False
    if candidate.get('provider') == 'modrinth':
        # The word 'companion' by itself often means a pet, not a handheld app.
        if not HANDHELD_RE.search((candidate.get('project') or '') + ' ' + (candidate.get('label') or '')):
            return False
    if force:
        return True
    last = candidate.get('mediaScan', {}).get('checkedAt', '')
    if last and str(last)[:10] >= stamp[:10] and len(candidate.get('mediaCandidates', [])) >= 1:
        return False
    if last:
        try:
            age = datetime.fromisoformat(stamp.replace('Z', '+00:00')) - datetime.fromisoformat(last.replace('Z', '+00:00'))
            if age.total_seconds() < 7 * 86400:
                return False
        except (ValueError, TypeError, OverflowError):
            pass
    return True


def enrich_candidate(candidate, get_json, get_readme):
    provider = candidate['provider']
    url = candidate.get('url', '')
    existing = list(candidate.get('mediaCandidates', []))
    found = []
    if provider == 'modrinth':
        slug = url.removeprefix('https://modrinth.com/mod/')
        if not SLUG.fullmatch(slug):
            return []
        info = get_json('https://api.modrinth.com/v2/project/' + slug)
        found = from_modrinth_gallery(info.get('gallery', []), url)
    elif provider == 'github':
        repo = url.removeprefix('https://github.com/')
        if not REPO.fullmatch(repo):
            return []
        meta = get_json('https://api.github.com/repos/' + repo)
        branch = meta.get('default_branch', 'main')
        if not isinstance(branch, str) or not re.fullmatch(r'[A-Za-z0-9._/-]{1,130}', branch) or '..' in branch:
            return []
        try:
            readme = get_readme(repo) or ''
            found.extend(image_candidates(readme, repo, f'https://github.com/{repo}/blob/{branch}/README.md', limit=6))
            found = [m for m in found if not BAD_IMAGE.search(urllib.parse.urlsplit(m['url']).path)]
            for m in found:
                m['url'] = m['url'].replace(f'https://raw.githubusercontent.com/{repo}/HEAD/',
                                             f'https://raw.githubusercontent.com/{repo}/{branch}/')
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, UnicodeError):
            pass
        if len(found) < 6:
            try:
                tree = get_json('https://api.github.com/repos/' + repo + '/git/trees/' + urllib.parse.quote(branch, safe='') + '?recursive=1')
                found.extend(from_github_tree(tree.get('tree', []), repo, branch, limit=6))
            except (urllib.error.HTTPError, urllib.error.URLError, ValueError, KeyError):
                pass
    merged = {m['url']: m for m in existing if isinstance(m, dict) and m.get('url')}
    for m in found:
        if m['url'] not in merged:
            merged[m['url']] = m
    return list(merged.values())[:10]


def enrich_queue(queue, get_json, get_readme, limit=6, game_id=None, force=False, stamp=None):
    stamp = stamp or now()
    items = [x for x in queue.get('candidates', []) if isinstance(x, dict)]
    selected = [x for x in items if eligible(x, stamp, game_id, force)]
    selected.sort(key=lambda x: (-int(x.get('score', 0)), bool(x.get('mediaCandidates')), x.get('project', '').lower()))
    checked = added = failures = 0
    for candidate in selected[:limit]:
        try:
            before = len(candidate.get('mediaCandidates', []))
            media = enrich_candidate(candidate, get_json, get_readme)
            candidate['mediaCandidates'] = media
            candidate['mediaScan'] = {'checkedAt': stamp, 'result': 'source-gallery' if media else 'no-gallery-found'}
            checked += 1
            added += max(0, len(media) - before)
        except (urllib.error.HTTPError, urllib.error.URLError, ValueError, TypeError, KeyError) as error:
            failures += 1
            candidate['mediaScan'] = {'checkedAt': stamp, 'result': 'fetch-error', 'errorType': type(error).__name__}
    return queue, {'checked': checked, 'newImages': added, 'errors': failures, 'eligible': len(selected)}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--game', help='Optional known game ID')
    p.add_argument('--limit', type=int, default=5, help='Maximum candidates to check this run (1..12)')
    p.add_argument('--force', action='store_true', help='Ignore seven-day refetch delay')
    p.add_argument('--dry-run', action='store_true', help='Never write queue')
    args = p.parse_args()
    if not 1 <= args.limit <= 12:
        p.error('limit must be 1..12')
    token = os.getenv('GITHUB_TOKEN')
    def fetch_json(url):
        headers = {'User-Agent': USER_AGENT}
        if url.startswith('https://api.github.com/'):
            headers['X-GitHub-Api-Version'] = '2022-11-28'
            if token:
                headers['Authorization'] = 'Bearer ' + token
        return request_json(url, headers, 1_500_000)
    queue = load_json(QUEUE, {'schemaVersion':1,'candidates':[],'runs':[]})
    result, stats = enrich_queue(queue, fetch_json, lambda repo: request_gh_readme(repo, token),
                                 limit=args.limit, game_id=args.game, force=args.force)
    if not args.dry_run:
        write_json(QUEUE, result)
    print(json.dumps({'game': args.game or 'rotating', **stats, 'written': not args.dry_run}, ensure_ascii=False))


if __name__ == '__main__':
    main()
