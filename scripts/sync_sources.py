"""GitHub metadata + new discovery candidates. Never changes catalog.json.
Python 3.10+, stdlib. GITHUB_TOKEN belongs on the server, never in the app.
No upstream code, APK, ROM or build artifact is executed.
"""
import argparse
import base64
import hashlib
import html
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_RE = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')


def utcnow():
    return datetime.now(timezone.utc).isoformat(timespec='seconds').replace('+00:00', 'Z')


def read_json(path, default):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def atomic_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + '.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temp.replace(path)


class ApiError(RuntimeError):
    pass


class RateLimited(ApiError):
    pass


class SafeRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        target = urllib.parse.urlsplit(newurl)
        if target.scheme != 'https' or target.hostname != 'api.github.com' or target.username or target.password:
            raise ApiError('Refusing redirect outside api.github.com')
        return super().redirect_request(request, fp, code, msg, headers, newurl)


class GitHub:
    def __init__(self, cache_path, token=None, pause=0.25):
        self.cache_path = cache_path
        self.cache = read_json(cache_path, {})
        self.token = token
        self.pause = pause
        self.opener = urllib.request.build_opener(SafeRedirect())

    def get(self, path, allow_404=False):
        if not path.startswith('/repos/') or '..' in path or '\n' in path or '\r' in path:
            raise ApiError('Unexpected API path')
        url = 'https://api.github.com' + path
        cached = self.cache.get(url, {})
        headers = {'Accept':'application/vnd.github+json','User-Agent':'HandheldAtlas/0.1','X-GitHub-Api-Version':'2022-11-28'}
        if self.token:
            headers['Authorization'] = 'Bearer ' + self.token
        if cached.get('etag'):
            headers['If-None-Match'] = cached['etag']
        try:
            time.sleep(self.pause)
            with self.opener.open(urllib.request.Request(url, headers=headers), timeout=25) as response:
                body = response.read(6_000_001)
                if len(body) > 6_000_000:
                    raise ApiError('API response exceeds size limit')
                data = json.loads(body)
                self.cache[url] = {'etag':response.headers.get('ETag'), 'data':data}
                return data
        except urllib.error.HTTPError as error:
            if error.code == 304 and 'data' in cached:
                return cached['data']
            if error.code == 404 and allow_404:
                return None
            if error.code in (403, 429):
                retry = error.headers.get('Retry-After') or error.headers.get('X-RateLimit-Reset') or 'later'
                raise RateLimited(f'HTTP {error.code}: stop; retry/reset: {retry}') from error
            raise ApiError(f'GitHub HTTP {error.code}') from error
        except (urllib.error.URLError, TimeoutError, ValueError, OSError) as error:
            raise ApiError(type(error).__name__ + ': network or JSON response failed') from error

    def save_cache(self):
        atomic_json(self.cache_path, self.cache)


def canonical_project_url(value):
    try:
        u = urllib.parse.urlsplit(html.unescape(value).strip().rstrip('.,;'))
        if u.scheme != 'https' or u.hostname != 'github.com' or u.username or u.password or u.port:
            return None
        parts = u.path.strip('/').split('/')
        if len(parts) < 2:
            return None
        repo = '/'.join(parts[:2]).removesuffix('.git')
        if not REPO_RE.fullmatch(repo):
            return None
        if parts[0].lower() in {'sponsors','topics','settings','features','orgs','marketplace','collections'}:
            return None
        if parts[1] == '.github' or (len(parts)>2 and parts[2] in {'issues','pull','pulls','actions','stargazers','forks','releases','commit','commits','discussions'}):
            return None
        suffix = '/'.join(parts[2:])
        if suffix and not suffix.startswith(('blob/', 'tree/')):
            return None
        fragment = '#' + urllib.parse.quote(urllib.parse.unquote(u.fragment), safe='-_') if u.fragment else ''
        return ('https://github.com/' + repo + ('/' + suffix if suffix else '') + fragment, repo)
    except (ValueError, TypeError):
        return None


def extract_links(text):
    matches = []
    for label, url in re.findall(r'\[([^\]\n]{1,180})\]\((https://github\.com/[^\s)]+)\)', text):
        matches.append((url, re.sub(r'<[^>]+>', '', label).strip()[:120]))
    for url in re.findall(r'https://github\.com/[A-Za-z0-9_./%#?=&:+-]+', text):
        matches.append((url, ''))
    result = {}
    for value, label in matches:
        parsed = canonical_project_url(value)
        if parsed:
            url, repo = parsed
            if url not in result or label:
                result[url] = {'url':url, 'repo':repo, 'label':label or repo}
    return sorted(result.values(), key=lambda item:item['url'].lower())


def add_candidates(state, links, source_id, source_url, known_repos, now):
    by_url = {item['url'].lower():item for item in state['candidates']}
    added = 0
    for link in links:
        url, repo = link['url'], link['repo']
        if repo.lower() in known_repos and url.rstrip('/').lower() == ('https://github.com/' + repo).lower():
            continue
        key = url.lower()
        if key in by_url:
            item = by_url[key]
            if source_id not in item['sourceIds']:
                item['sourceIds'].append(source_id)
            if source_url not in item['provenance']:
                item['provenance'].append(source_url)
            item['lastSeenAt'] = now
        elif len(by_url) < 10000:
            item = {'id':hashlib.sha256(key.encode()).hexdigest()[:20], 'url':url, 'repo':repo,
                    'label':link['label'], 'sourceIds':[source_id], 'provenance':[source_url],
                    'discoveredAt':now, 'lastSeenAt':now, 'status':'pending', 'reviewed':False,
                    'gameId':None, 'note':'Discovery candidate, not an installation recommendation.'}
            state['candidates'].append(item)
            by_url[key] = item
            added += 1
    return added


def metadata_events(previous, current, now):
    if not previous:
        return []
    events = []
    repo = current['repo']
    release, old_release = current.get('latestRelease'), previous.get('latestRelease')
    if release and (not old_release or release['id'] != old_release['id'] or release['tag'] != old_release['tag']):
        events.append({'type':'release', 'title':repo + ' / ' + release['tag'], 'repo':repo,
                       'url':release['url'], 'detectedAt':now, 'publishedAt':release['publishedAt'],
                       'reviewed':False, 'summary':'Neuer Projekt-Release. Funktionen und Geraetekompatibilitaet sind nicht bestaetigt.'})
    if current['archived'] and not previous.get('archived'):
        events.append({'type':'archived','title':repo,'repo':repo,'url':current['url'],
                       'detectedAt':now,'reviewed':False,'summary':'Repository archiviert. Keine automatische Deinstallation oder Migration.'})
    if current.get('branchHead') and previous.get('branchHead') and current['branchHead'] != previous['branchHead']:
        events.append({'type':'repository_changed','title':repo+' / '+current['branch'], 'repo':repo,
                       'url':current['url']+'/tree/'+urllib.parse.quote(current['branch'],safe=''),
                       'detectedAt':now,'reviewed':False,'summary':'Beobachteter Branch geaendert; redaktionelle Pruefung steht aus.'})
    for event in events:
        identity = '|'.join([event['type'],repo,event.get('publishedAt') or now,event.get('title','')])
        event['id'] = hashlib.sha256(identity.encode()).hexdigest()[:20]
    return events


def sync(root, api, selected=None, discover=True, only_discovery=False):
    now = utcnow()
    catalog = read_json(root/'data/catalog.json', {})
    state = read_json(root/'data/updates.json', {'schemaVersion':1,'lastSuccessAt':None,'projects':{},'events':[]})
    candidates = read_json(root/'data/candidates.json', {'schemaVersion':1,'candidates':[]})
    state['lastAttemptAt'], state['errors'] = now, []
    state.setdefault('sourceHashes', {})
    state.setdefault('sourceSnapshots', {})
    all_sources = [s for s in catalog['sources'] if s.get('repo') and s['role'] != 'planned']
    known_repos = {s['repo'].lower() for s in all_sources}
    selected_sources = [s for s in all_sources if (not selected or s['id'] in selected) and (not only_discovery or s['role']=='discovery')]
    grouped = {}
    for s in selected_sources:
        grouped.setdefault(s['repo'], []).append(s)
    complete = not selected and not only_discovery and discover
    new_candidates = 0
    for repo, repo_sources in grouped.items():
        assert REPO_RE.fullmatch(repo), 'Unsafe repository ID'
        try:
            metadata = api.get('/repos/' + repo)
            primary = any(s['role']=='primary' for s in repo_sources)
            branch = next((s.get('watchBranch') for s in repo_sources if s.get('watchBranch')), None)
            release = api.get('/repos/' + repo + '/releases/latest', allow_404=True) if primary and not branch else None
            item = {'repo':repo,'url':'https://github.com/'+repo,'checkedAt':now,
                    'archived':bool(metadata.get('archived')), 'defaultBranch':metadata.get('default_branch'),
                    'licenseReportedByGitHub':(metadata.get('license') or {}).get('spdx_id'),
                    'licenseScopeNote':'Repository metadata only; media and catalog permissions require review.',
                    'latestRelease':None}
            if release:
                item['latestRelease']={'id':str(release['id']),'tag':str(release['tag_name']),
                    'url':'https://github.com/'+repo+'/releases/tag/'+urllib.parse.quote(str(release['tag_name']),safe=''),
                    'publishedAt':release.get('published_at')}
            if branch:
                commits = api.get('/repos/'+repo+'/commits?sha='+urllib.parse.quote(branch,safe='')+'&per_page=1')
                item.update(branch=branch, branchHead=commits[0]['sha'] if commits else None)
            state['events'].extend(metadata_events(state['projects'].get(repo),item,now))
            state['projects'][repo] = item
            if discover:
                for source in repo_sources:
                    if source['role'] != 'discovery':
                        continue
                    if source['id'] in {'dual-list','native-ports'}:
                        readme = api.get('/repos/'+repo+'/readme')
                        if readme.get('encoding') != 'base64' or not readme.get('content'):
                            raise ApiError('README unavailable or unexpected encoding')
                        content = base64.b64decode(readme['content']).decode('utf-8')
                        sha, links = readme['sha'], extract_links(content)
                    elif source['id'] == 'gaft':
                        branch_name = metadata.get('default_branch') or 'main'
                        tree = api.get('/repos/'+repo+'/git/trees/'+urllib.parse.quote(branch_name,safe='')+'?recursive=1')
                        if tree.get('truncated'):
                            raise ApiError('Tree is truncated; candidate discovery incomplete')
                        entries = sorted((t['path'],t.get('sha')) for t in tree.get('tree',[]) if t.get('type')=='blob' and t['path'].startswith('content/') and t['path'].endswith('.md'))
                        links = [{'url':'https://github.com/'+repo+'/blob/'+urllib.parse.quote(branch_name,safe='')+'/'+urllib.parse.quote(path,safe='/'),
                                  'repo':repo,'label':Path(path).stem.replace('-',' ')} for path,_ in entries]
                        sha = hashlib.sha256(json.dumps(entries).encode()).hexdigest()
                    else:
                        continue
                    new_candidates += add_candidates(candidates,links,source['id'],source['url'],known_repos,now)
                    old_sha = state['sourceHashes'].get(source['id'])
                    if old_sha and sha != old_sha:
                        state['events'].append({'id':hashlib.sha256((source['id']+sha).encode()).hexdigest()[:20],
                                 'type':'source_changed','title':source['name'],'repo':repo,'url':source['url'],
                                 'detectedAt':now,'reviewed':False,'summary':'Entdeckungsquelle geaendert. Neue Projekte vor Aufnahme in den Katalog pruefen.'})
                    state['sourceHashes'][source['id']] = sha
                    state['sourceSnapshots'][source['id']] = {'checkedAt':now,'hash':sha,'linkCount':len(links)}
            print('OK', repo)
        except (ApiError, KeyError, TypeError, ValueError) as error:
            state['errors'].append({'repo':repo,'message':str(error)[:250],'at':now})
            print('WARN',repo,str(error),file=sys.stderr)
            if isinstance(error, RateLimited):
                break
    if not state['errors'] and complete:
        state['lastSuccessAt'] = now
    if not state['errors']:
        state['lastPartialSuccessAt'] = now
    state['events'] = list({event['id']:event for event in state['events']}.values())
    state['events'].sort(key=lambda event:event.get('detectedAt',''),reverse=True)
    state['events'] = state['events'][:1000]
    candidates['candidates'].sort(key=lambda item:(item['discoveredAt'],item['url']),reverse=True)
    candidates['lastAttemptAt'] = now
    atomic_json(root/'data/updates.json',state)
    atomic_json(root/'data/candidates.json',candidates)
    api.save_cache()
    print('New candidates:',new_candidates,'; catalog.json was NOT modified.')
    return 1 if state['errors'] else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only',nargs='+',help='Source IDs; partial runs never mark the full catalog fresh')
    parser.add_argument('--no-discovery',action='store_true')
    parser.add_argument('--discovery-only',action='store_true',help='Three discovery feeds only')
    args = parser.parse_args()
    api = GitHub(ROOT/'.cache/github.json',os.getenv('GITHUB_TOKEN'))
    return sync(ROOT,api,args.only,not args.no_discovery,args.discovery_only)

if __name__ == '__main__':
    raise SystemExit(main())
