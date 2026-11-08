#!/usr/bin/env python3
"""Handheld Atlas: validate the database and build the web app.

    python3 scripts/atlas.py validate     # check every data file, exit 1 on errors
    python3 scripts/atlas.py build        # validate, then write dist/ (app + data.json + offline HTML)
    python3 scripts/atlas.py stats        # quick overview of the database
    python3 scripts/atlas.py format       # rewrite all data files with canonical formatting

Standard library only (Python 3.10+).
"""
import hashlib
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
APP = ROOT / 'app'
DIST = ROOT / 'dist'

ID_RE = re.compile(r'^[a-z0-9][a-z0-9-]*$')
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
ROUTE_STATUS = {'active', 'experimental', 'archived'}
PROJECT_KINDS = {'emulator', 'emulator-fork', 'port', 'launcher', 'mod', 'companion', 'runtime', 'official',
                 'tool', 'directory', 'data-source', 'other'}
CHANGELOG_TYPES = {'system', 'release', 'route-added', 'route-updated', 'game-added', 'mod-added',
                   'project-added', 'screenshot-added', 'verified', 'removed'}


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def load_db():
    games = []
    for f in sorted((DATA / 'games').glob('*.json')):
        g = read(f)
        g['_file'] = f.name
        games.append(g)
    return {
        'meta': read(DATA / 'meta.json'),
        'games': games,
        'projects': read(DATA / 'projects.json')['projects'],
        'platforms': read(DATA / 'platforms.json')['platforms'],
        'changelog': read(DATA / 'changelog.json')['entries'],
        'inbox': read(DATA / 'inbox.json'),
    }


def validate(db=None):
    """Return a list of human-readable problems. Empty list == valid."""
    db = db or load_db()
    meta = db['meta']
    errors = []
    err = errors.append
    kinds, features = set(meta['kinds']), set(meta['features'])
    verif, effort, targets = set(meta['verification']), set(meta['effort']), set(meta['targets'])
    version_types = set(meta.get('versionTypes', {}))

    def url_ok(u, where):
        if not isinstance(u, str) or not u.startswith('https://'):
            err(f'{where}: URL muss mit https:// beginnen: {u!r}')

    project_ids = set()
    for p in db['projects']:
        where = f"projects.json/{p.get('id')}"
        if not ID_RE.match(p.get('id', '')):
            err(f'{where}: ungültige id')
        if p['id'] in project_ids:
            err(f'{where}: doppelte id')
        project_ids.add(p['id'])
        if not p.get('name'):
            err(f'{where}: name fehlt')
        url_ok(p.get('url'), where)
        if p.get('kind') not in PROJECT_KINDS:
            err(f"{where}: kind {p.get('kind')!r} nicht in {sorted(PROJECT_KINDS)}")

    game_ids, titles = set(), {}
    for g in db['games']:
        where = f"games/{g['_file']}"
        gid = g.get('id', '')
        if not ID_RE.match(gid):
            err(f'{where}: ungültige id {gid!r}')
        if g['_file'] != f'{gid}.json':
            err(f'{where}: Dateiname muss {gid}.json sein')
        if gid in game_ids:
            err(f'{where}: doppelte id')
        game_ids.add(gid)
        for key in ('title', 'franchise'):
            if not isinstance(g.get(key), str) or not g[key].strip():
                err(f'{where}: {key} fehlt')
        tkey = re.sub(r'[^a-z0-9]', '', g.get('title', '').lower())
        if tkey in titles:
            err(f'{where}: gleicher Titel wie games/{titles[tkey]} – zusammenführen')
        titles[tkey] = g['_file']
        if not isinstance(g.get('platforms', []), list):
            err(f'{where}: platforms muss eine Liste sein')
        if g.get('cover'):
            url_ok(g['cover'].get('url'), f'{where}/cover')
        for s in g.get('screenshots', []):
            url_ok(s.get('url'), f'{where}/screenshots')
        version_ids = set()
        for v in g.get('versions', []):
            vw = f"{where}/versions/{v.get('id')}"
            if not ID_RE.match(v.get('id', '')):
                err(f'{vw}: ungültige id')
            if v.get('id') in version_ids:
                err(f'{vw}: doppelte Fassung')
            version_ids.add(v.get('id'))
            if not v.get('name'):
                err(f'{vw}: name fehlt')
            if v.get('type') not in version_types:
                err(f"{vw}: type {v.get('type')!r} nicht in {sorted(version_types)}")
            if not isinstance(v.get('platforms'), list) or not v['platforms']:
                err(f'{vw}: platforms (Liste) fehlt')
            if 'year' in v and not (isinstance(v['year'], int) and 1970 < v['year'] < 2100):
                err(f'{vw}: year muss eine Jahreszahl sein')
            for t in v.get('traits', []):
                if t not in features:
                    err(f'{vw}: trait {t!r} unbekannt (meta.json features)')
            for l in v.get('links', []):
                url_ok(l.get('url'), f'{vw}/links')
        if g.get('routes') and not version_ids:
            err(f'{where}: Spiel mit Spielwegen braucht mindestens eine Fassung (versions)')
        route_ids = set()
        for r in g.get('routes', []):
            rw = f"{where}/routes/{r.get('id')}"
            if not ID_RE.match(r.get('id', '')):
                err(f'{rw}: ungültige id')
            if r.get('id') in route_ids:
                err(f'{rw}: doppelte Route')
            route_ids.add(r.get('id'))
            if not r.get('name'):
                err(f'{rw}: name fehlt')
            if r.get('kind') not in kinds:
                err(f"{rw}: kind {r.get('kind')!r} unbekannt (meta.json kinds)")
            for f in r.get('features', []):
                if f not in features:
                    err(f'{rw}: feature {f!r} unbekannt (meta.json features)')
            for t in r.get('targets', []):
                if t not in targets:
                    err(f'{rw}: target {t!r} unbekannt (meta.json targets)')
            if r.get('verification') not in verif:
                err(f"{rw}: verification {r.get('verification')!r} nicht in {sorted(verif)}")
            if r.get('effort', 'guided') not in effort:
                err(f"{rw}: effort {r.get('effort')!r} unbekannt")
            if r.get('status', 'active') not in ROUTE_STATUS:
                err(f"{rw}: status {r.get('status')!r} nicht in {sorted(ROUTE_STATUS)}")
            for p in r.get('projects', []):
                if p not in project_ids:
                    err(f'{rw}: Projekt {p!r} fehlt in projects.json')
            if not r.get('projects') and not r.get('links'):
                err(f'{rw}: braucht mindestens ein Projekt oder einen Link als Quelle')
            if r.get('release') not in version_ids:
                err(f"{rw}: release {r.get('release')!r} ist keine Fassung dieses Spiels ({sorted(version_ids)})")
            for s in r.get('screenshots', []):
                url_ok(s.get('url'), f'{rw}/screenshots')
            for l in r.get('links', []):
                url_ok(l.get('url'), f'{rw}/links')
            for rep in r.get('reports', []):
                url_ok(rep.get('url'), f'{rw}/reports')
                if not rep.get('summary'):
                    err(f'{rw}/reports: summary fehlt')
            for perf in r.get('performance') or []:
                if not perf.get('device') or not perf.get('result'):
                    err(f'{rw}/performance: device und result sind Pflicht')
                url_ok(perf.get('source'), f'{rw}/performance')
            if r.get('checkedAt') and not DATE_RE.match(r['checkedAt']):
                err(f'{rw}: checkedAt muss YYYY-MM-DD sein')
        for m in g.get('mods', []):
            mw = f"{where}/mods/{m.get('id')}"
            if not m.get('name'):
                err(f'{mw}: name fehlt')
            url_ok(m.get('url'), mw)
            if m.get('verification', 'documented') not in verif:
                err(f'{mw}: verification unbekannt')

    for p in db['projects']:
        for gid in p.get('games', []):
            if gid not in game_ids:
                err(f"projects.json/{p['id']}: Spiel {gid!r} existiert nicht")
    for plat, routes in db['platforms'].items():
        for r in routes:
            if r.get('project') not in project_ids:
                err(f"platforms.json/{plat}: Projekt {r.get('project')!r} fehlt in projects.json")
            if r.get('kind') not in kinds:
                err(f"platforms.json/{plat}: kind {r.get('kind')!r} unbekannt")
    for e in db['changelog']:
        if e.get('type') not in CHANGELOG_TYPES:
            err(f"changelog.json: type {e.get('type')!r} nicht in {sorted(CHANGELOG_TYPES)}")
        if not DATE_RE.match(e.get('date', '')):
            err(f'changelog.json: Datum {e.get("date")!r} ungültig')
        if e.get('game') and e['game'] not in game_ids:
            err(f"changelog.json: Spiel {e['game']!r} existiert nicht")
    for lead in db['inbox'].get('leads', []):
        url_ok(lead.get('url'), 'inbox.json')
    return errors


def bundle(db):
    """The single data file the app loads."""
    games = []
    for g in db['games']:
        g = {k: v for k, v in g.items() if not k.startswith('_')}
        games.append(g)
    return {
        'builtAt': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'meta': db['meta'],
        'games': games,
        'projects': {p['id']: p for p in db['projects']},
        'platforms': db['platforms'],
        'changelog': db['changelog'][:300],
        'inboxCount': len(db['inbox'].get('leads', [])),
        'agent': db['inbox'].get('agent', {}),
    }


def build():
    db = load_db()
    problems = validate(db)
    if problems:
        print('\n'.join(problems), file=sys.stderr)
        sys.exit(f'{len(problems)} Fehler – Build abgebrochen.')
    data = bundle(db)
    data_json = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
    version = hashlib.sha256(data_json.encode()).hexdigest()[:12]
    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(APP, DIST)
    (DIST / 'data.json').write_text(data_json, encoding='utf-8')
    (DIST / 'version.json').write_text(json.dumps({'version': version, 'builtAt': data['builtAt']}), encoding='utf-8')
    sw = (DIST / 'sw.js').read_text(encoding='utf-8').replace('__VERSION__', version)
    (DIST / 'sw.js').write_text(sw, encoding='utf-8')
    # Offline single-file version: same app with data embedded, for sideloading without internet.
    html = (DIST / 'index.html').read_text(encoding='utf-8')
    css = (DIST / 'style.css').read_text(encoding='utf-8')
    js = (DIST / 'app.js').read_text(encoding='utf-8')
    embedded = data_json.replace('</', '<\\/')
    offline = (html.replace('<link rel="stylesheet" href="style.css">', f'<style>{css}</style>')
                   .replace('<script src="app.js" defer></script>',
                            f'<script>window.ATLAS_EMBEDDED={embedded};</script><script>{js}</script>')
                   .replace('<link rel="manifest" href="manifest.webmanifest">', ''))
    (DIST / 'Handheld-Atlas-offline.html').write_text(offline, encoding='utf-8')
    (DIST / '.nojekyll').write_text('', encoding='utf-8')
    print(f"dist/ gebaut: {len(data['games'])} Spiele, Version {version}")


def stats():
    db = load_db()
    games = db['games']
    routes = [r for g in games for r in g.get('routes', [])]
    from collections import Counter
    print(f"Spiele: {len(games)}  (mit Spielwegen: {sum(1 for g in games if g.get('routes'))})")
    print(f'Spielwege: {len(routes)}  Projekte: {len(db["projects"])}  Plattformen: {len(db["platforms"])}')
    print('Prüfstatus:', dict(Counter(r['verification'] for r in routes)))
    print('Dual Screen:', sum(1 for r in routes if 'dual-screen' in r.get('features', [])))
    print('Mit Screenshots:', sum(1 for r in routes if r.get('screenshots')), 'Spielwege,',
          sum(1 for g in games if g.get('cover')), 'Cover')
    print('Inbox:', len(db['inbox'].get('leads', [])), 'Funde warten auf den Agenten')
    no_fr = sum(1 for g in games if g['franchise'] == g['title'])
    print('Franchise = Titel (prüfen):', no_fr)


def fmt():
    for f in (DATA / 'games').glob('*.json'):
        write(f, read(f))
    for name in ('projects.json', 'platforms.json', 'changelog.json', 'inbox.json', 'meta.json'):
        write(DATA / name, read(DATA / name))
    print('formatiert')


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'build'
    if cmd == 'validate':
        problems = validate()
        print('\n'.join(problems) or 'OK – keine Fehler')
        sys.exit(1 if problems else 0)
    {'build': build, 'stats': stats, 'format': fmt}.get(cmd, lambda: sys.exit(__doc__))()
