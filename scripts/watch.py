#!/usr/bin/env python3
"""Daily watcher – no AI, no API key required (GITHUB_TOKEN raises the rate limit).

1. New releases / archive status for every project in data/projects.json that has a GitHub repo
   -> updates projects.json and writes a changelog entry (shown in the app's "Neu" tab).
2. New candidates from GitHub search, forks of watched repos, Modrinth and RSS feeds (data/watch.json)
   -> appended to data/inbox.json for the maintenance agent to sort into games.

Every source is optional: network errors are logged and skipped, never fatal.
    python3 scripts/watch.py [--no-discovery]
"""
import json
import os
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from atlas import DATA, read, write  # noqa: E402

UA = 'handheld-atlas-watcher (+https://github.com/markusklier/handheld-atlas)'
TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')
log = lambda *a: print(*a, file=sys.stderr)


def http_json(url, token=None):
    headers = {'User-Agent': UA, 'Accept': 'application/vnd.github+json'}
    if token and 'api.github.com' in url:
        headers['Authorization'] = f'Bearer {token}'
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=25) as r:
        return json.loads(r.read().decode())


def http_text(url):
    with urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=25) as r:
        return r.read().decode('utf-8', 'replace')


def norm(u):
    return (u or '').rstrip('/').lower().replace('http://', 'https://').replace('://www.', '://')


class Watcher:
    def __init__(self, fetch_json=http_json, fetch_text=http_text, token=None):
        self.fetch_json, self.fetch_text, self.token = fetch_json, fetch_text, token
        self.projects_doc = read(DATA / 'projects.json')
        self.inbox = read(DATA / 'inbox.json')
        self.inbox.setdefault('leads', [])
        self.inbox.setdefault('rejected', [])
        self.changelog = read(DATA / 'changelog.json')
        self.config = read(DATA / 'watch.json')
        self.known = self._known_urls()
        self.new_leads = 0
        self.new_events = 0

    def _known_urls(self):
        known = set()
        for p in self.projects_doc['projects']:
            known.add(norm(p['url']))
            if p.get('repo'):
                known.add(norm(f"https://github.com/{p['repo']}"))
        for f in (DATA / 'games').glob('*.json'):
            g = read(f)
            for r in g.get('routes', []):
                known.update(norm(l['url']) for l in r.get('links', []))
            known.update(norm(m.get('url')) for m in g.get('mods', []))
        known.update(norm(l['url']) for l in self.inbox['leads'])
        known.update(norm(u) for u in self.inbox['rejected'])
        return known

    def gh(self, path):
        return self.fetch_json('https://api.github.com' + path, self.token)

    # ---- 1. releases of known projects ----
    def check_projects(self):
        for p in self.projects_doc['projects']:
            repo = p.get('repo')
            if not repo:
                continue
            try:
                info = self.gh(f'/repos/{repo}')
                releases = self.gh(f'/repos/{repo}/releases?per_page=3')
            except Exception as e:  # noqa: BLE001 – a single broken repo must not stop the run
                log(f'! {repo}: {e}')
                continue
            if info.get('archived') and not p.get('archived'):
                p['archived'] = True
                self.event('release', f"{p['name']} wurde archiviert (nicht mehr gepflegt).", p)
            if info.get('pushed_at'):
                p['pushedAt'] = info['pushed_at'][:10]
            if info.get('description') and not p.get('description'):
                p['description'] = info['description'][:300]
            rel = next((r for r in releases if not r.get('draft')), None)
            if rel:
                tag = rel.get('tag_name')
                old = (p.get('latestRelease') or {}).get('tag')
                p['latestRelease'] = {'tag': tag, 'url': rel.get('html_url'),
                                      'date': (rel.get('published_at') or '')[:10]}
                if old != tag:
                    pre = ' (Vorabversion)' if rel.get('prerelease') else ''
                    self.event('release', f"{p['name']} {tag}{pre} veröffentlicht.", p, url=rel.get('html_url'))
            p['checkedAt'] = TODAY

    def event(self, kind, text, project=None, url=None):
        entry = {'date': TODAY, 'type': kind, 'text': text}
        if project:
            entry['project'] = project['id']
            if project.get('games'):
                entry['games'] = project['games'][:12]
        if url:
            entry['url'] = url
        self.changelog['entries'].insert(0, entry)
        self.new_events += 1

    # ---- 2. discovery ----
    def lead(self, url, title, excerpt, source):
        key = norm(url)
        if not url or key in self.known:
            return
        self.known.add(key)
        self.inbox['leads'].insert(0, {'url': url, 'title': (title or '')[:160], 'excerpt': (excerpt or '')[:400],
                                       'game': None, 'source': source, 'foundAt': TODAY})
        self.new_leads += 1

    def discover(self):
        since = (datetime.now(timezone.utc) - timedelta(days=self.config.get('searchWindowDays', 120))).strftime('%Y-%m-%d')
        for q in self.config.get('githubQueries', []):
            try:
                res = self.gh('/search/repositories?' + urllib.parse.urlencode(
                    {'q': f'{q} pushed:>={since}', 'sort': 'updated', 'per_page': 20}))
            except Exception as e:  # noqa: BLE001
                log(f'! GitHub-Suche {q!r}: {e}')
                continue
            for r in res.get('items', []):
                if r.get('fork') and not r.get('description'):
                    continue
                self.lead(r['html_url'], r['full_name'], r.get('description'), 'github-search')
        for repo in self.config.get('forkWatch', []):
            try:
                forks = self.gh(f'/repos/{repo}/forks?sort=newest&per_page=30')
            except Exception as e:  # noqa: BLE001
                log(f'! Forks {repo}: {e}')
                continue
            for f in forks:
                # only forks that actually changed something after forking
                if (f.get('pushed_at') or '') > (f.get('created_at') or '') and (f.get('pushed_at') or '')[:10] >= since:
                    self.lead(f['html_url'], f"{f['full_name']} (Fork von {repo})", f.get('description'), 'github-fork')
        for q in self.config.get('modrinthQueries', []):
            try:
                res = self.fetch_json('https://api.modrinth.com/v2/search?' + urllib.parse.urlencode(
                    {'query': q, 'index': 'updated', 'limit': 20}))
            except Exception as e:  # noqa: BLE001
                log(f'! Modrinth {q!r}: {e}')
                continue
            for h in res.get('hits', []):
                self.lead(f"https://modrinth.com/{h.get('project_type', 'mod')}/{h['slug']}", h.get('title'),
                          h.get('description'), 'modrinth')
        for feed in self.config.get('rssFeeds', []):
            try:
                root = ET.fromstring(self.fetch_text(feed))
            except Exception as e:  # noqa: BLE001
                log(f'! RSS {feed}: {e}')
                continue
            ns = {'a': 'http://www.w3.org/2005/Atom'}
            for entry in root.findall('a:entry', ns)[:25]:
                link = entry.find('a:link', ns)
                title = entry.findtext('a:title', default='', namespaces=ns)
                if link is not None:
                    self.lead(link.get('href'), title, None, 'rss')
            for item in root.iter('item'):
                self.lead(item.findtext('link'), item.findtext('title'), None, 'rss')

    def save(self):
        self.inbox['leads'] = self.inbox['leads'][: self.config.get('maxInbox', 800)]
        self.changelog['entries'] = self.changelog['entries'][:1000]
        self.inbox['watcher'] = {'lastRun': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
                                 'newLeads': self.new_leads, 'newEvents': self.new_events}
        write(DATA / 'projects.json', self.projects_doc)
        write(DATA / 'inbox.json', self.inbox)
        write(DATA / 'changelog.json', self.changelog)


def main():
    w = Watcher(token=os.environ.get('GITHUB_TOKEN'))
    w.check_projects()
    if '--no-discovery' not in sys.argv:
        w.discover()
    w.save()
    print(f'Watcher: {w.new_events} Projekt-Ereignisse, {w.new_leads} neue Funde in der Inbox')


if __name__ == '__main__':
    main()
