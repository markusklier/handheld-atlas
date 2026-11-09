#!/usr/bin/env python3
"""Handheld Atlas: validate the database and build the web app.

    python3 scripts/atlas.py validate     # check every data file, exit 1 on errors
    python3 scripts/atlas.py build        # validate, then write dist/ (app + data.json + offline HTML)
    python3 scripts/atlas.py stats        # quick overview of the database
    python3 scripts/atlas.py format       # rewrite all data files with canonical formatting
    python3 scripts/atlas.py repair       # drop non-https entries, strip markdown citations (runs before validate in workflows)
    python3 scripts/atlas.py merge SRC INTO [--type remake] [--year 2011] [--name "…"] [--same]
                                          # duplicate game SRC becomes a version of INTO (routes, mods, images move along)

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


PLATFORM_ALIASES = {
    'PC (Windows)': 'PC', 'PC (MS-DOS)': 'PC', 'PC (MS-DOS, Windows)': 'PC', 'MS-DOS': 'PC', 'DOS': 'PC', 'Windows': 'PC',
    'PC (Microsoft Store)': 'PC', 'PC / SteamVR': 'PC', 'Microsoft Windows': 'PC', 'Steam': 'PC',
    'Mac': 'Macintosh', 'macOS': 'Macintosh', 'Mac OS': 'Macintosh', 'Classic Mac OS': 'Macintosh',
    'Xbox Series X|S': 'Xbox Series', 'Xbox Series X/S': 'Xbox Series', 'Xbox Series X': 'Xbox Series',
    'GameCube': 'Nintendo GameCube', 'Stadia': 'Google Stadia', 'PlayStation 4 / PlayStation VR': 'PlayStation 4',
    'PS1': 'PlayStation', 'PSX': 'PlayStation', 'PlayStation 1': 'PlayStation', 'PS2': 'PlayStation 2', 'PS3': 'PlayStation 3',
    'PS4': 'PlayStation 4', 'PS5': 'PlayStation 5', 'PS Vita': 'PlayStation Vita', 'Switch': 'Nintendo Switch',
    'Nintendo Entertainment System': 'NES', 'Super Nintendo': 'SNES', 'Super NES': 'SNES', 'N64': 'Nintendo 64',
    'Sega Genesis': 'Sega Mega Drive', 'Mega Drive': 'Sega Mega Drive', 'Genesis': 'Sega Mega Drive', 'Sega Dreamcast': 'Dreamcast',
    'Game Boy': 'Game Boy / Game Boy Color', 'Game Boy Color': 'Game Boy / Game Boy Color', 'GBA': 'Game Boy Advance',
    '3DS': 'Nintendo 3DS', 'NDS': 'Nintendo DS', 'DS': 'Nintendo DS', 'iPhone': 'iOS', 'iPadOS': 'iOS',
}


def canon_platforms(plats):
    """Canonical platform names (the AI writes "PC (MS-DOS)", "Xbox Series X|S" …), without duplicates."""
    return list(dict.fromkeys(PLATFORM_ALIASES.get((p or '').strip(), (p or '').strip()) for p in plats or [] if (p or '').strip()))


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
            for rep in v.get('reports', []):
                url_ok(rep.get('url'), f'{vw}/reports')
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
            if r.get('dualScreenType') and r['dualScreenType'] not in meta.get('dualScreenTypes', {}):
                err(f"{rw}: dualScreenType {r['dualScreenType']!r} unbekannt")
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
        mod_cats = set(meta.get('modCategories', {}))
        for m in g.get('mods', []):
            mw = f"{where}/mods/{m.get('id')}"
            if mod_cats and m.get('category', 'other') not in mod_cats:
                err(f"{mw}: category {m.get('category')!r} nicht in {sorted(mod_cats)}")
            for vid in m.get('release', []):
                if vid not in version_ids:
                    err(f'{mw}: release {vid!r} ist keine Fassung dieses Spiels')
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
        'research': research_spec(db['meta']),
        'researched': db['inbox'].get('aiResearch', {}),
        'queue': [{'game': j['game'], 'reason': j.get('reason', '')} for j in
                  (read(DATA / 'queue.json')['jobs'] if (DATA / 'queue.json').exists() else [])],
        'dualScan': db['inbox'].get('dualScan', {}),
        'franchiseScan': db['inbox'].get('franchiseScan', {}),
        'imageRequests': db['inbox'].get('imageRequests', {}),
        'usage': db['inbox'].get('usage', {}),
        'queueDay': db['inbox'].get('queueDay', {}),
        'agent': db['inbox'].get('agent', {}),
    }


def research_spec(meta):
    """Prompt rules + JSON schema of the AI research, so the app's instant analysis asks exactly the same."""
    import ai_research  # local import: ai_research imports this module
    return {'rules': ai_research.RULES, 'format': ai_research.schema(meta), 'model': 'gpt-6.1-sol'}


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
    shots = [sh for r in routes for sh in r.get('screenshots', [])]
    print('Spielweg-Bilder nach Prüfung:', dict(Counter(sh.get('check', 'ohne Angabe') for sh in shots)))
    print('Spielwege ohne Bild:', sum(1 for r in routes if not r.get('screenshots')), '| Dual Screen ohne Bild:',
          sum(1 for r in routes if 'dual-screen' in r.get('features', []) and not r.get('screenshots')))
    versions = [v for g in games for v in g.get('versions', [])]
    print('Fassungen:', len(versions), '| mit Jahr:', sum(1 for v in versions if v.get('year')),
          '| mit Community-Berichten:', sum(1 for v in versions if v.get('reports')))
    print('Inbox:', len(db['inbox'].get('leads', [])), 'Funde warten auf den Agenten')
    no_fr = sum(1 for g in games if g['franchise'] == g['title'])
    print('Franchise = Titel (prüfen):', no_fr)


def repair():
    """Drop list entries whose URL is not https (images, links, reports) so one bad item never blocks a whole run."""
    bad = lambda x: not str((x or {}).get('url') or (x or {}).get('source') or '').startswith('https://')
    removed = 0
    for f in (DATA / 'games').glob('*.json'):
        g = read(f)
        before = json.dumps(g)
        for holder in [g, *g.get('versions', []), *g.get('routes', []), *g.get('mods', [])]:
            for key in ('screenshots', 'links', 'reports'):
                if key in holder:
                    keep = [x for x in holder[key] if not bad(x)]
                    removed += len(holder[key]) - len(keep)
                    holder[key] = keep
        if g.get('cover') and bad(g['cover']):
            g.pop('cover')
            removed += 1
        from images import same_image                     # lazy: images → media → atlas
        for holder in [g, *g.get('routes', []), *g.get('mods', [])]:
            if holder.get('screenshots'):
                keep = []
                for x in holder['screenshots']:
                    if not any(same_image(x['url'], k['url']) for k in keep):
                        keep.append(x)
                removed += len(holder['screenshots']) - len(keep)
                holder['screenshots'] = keep
        g['platforms'] = canon_platforms(g.get('platforms'))
        for v in g.get('versions', []):
            v['platforms'] = canon_platforms(v.get('platforms'))
        for holder in [g, *g.get('versions', []), *g.get('routes', []), *g.get('mods', [])]:
            for key in ('summary', 'note', 'dualScreen', 'benefit', 'caveat', 'description'):
                if isinstance(holder.get(key), str) and MD_CITE.search(holder[key]):
                    holder[key] = MD_CITE.sub('', holder[key]).strip()
                    removed += 1
        if json.dumps(g) != before:
            write(f, g)
    print(f'repair: {removed} ungültige Einträge entfernt')


MD_CITE = re.compile(r'\s*\(\[[^\]]*\]\([^)]*\)\)')   # " ([site.com](https://…))" citation markers from the model


def merge(src_id, into_id, vtype=None, year=None, name=None, same=False):
    """Fold the duplicate game SRC into INTO: its versions become versions of INTO (or, with same=True, are mapped onto
    INTO's versions with the same platforms), routes/mods/screenshots move along, every reference is rewritten."""
    src_path, into_path = DATA / 'games' / f'{src_id}.json', DATA / 'games' / f'{into_id}.json'
    src, into = read(src_path), read(into_path)
    vmap = {}
    for v in src.get('versions', []):
        twin = next((t for t in into.get('versions', []) if set(t['platforms']) == set(v['platforms'])), None) if same else None
        if twin:
            vmap[v['id']] = twin['id']
            continue
        nv = dict(v)
        base = re.sub(r'[^a-z0-9]+', '-', (name or src['title']).lower()).strip('-')[:40] or v['id']
        nv['id'] = base if len(src['versions']) == 1 else f"{base}-{v['id']}"
        while any(t['id'] == nv['id'] for t in into.get('versions', [])):
            nv['id'] += '-2'
        if v.get('type') == 'original' or vtype:
            nv['type'] = vtype or 'port'
        if year and not nv.get('year'):
            nv['year'] = year
        label = name or src['title']
        if len(src['versions']) > 1:
            label += f" – {', '.join(v['platforms'])}"
        nv['name'] = f"{label} ({nv['year']})" if nv.get('year') and str(nv['year']) not in label else label
        into.setdefault('versions', []).append(nv)
        vmap[v['id']] = nv['id']
    ids = {r['id'] for r in into.get('routes', [])}
    for r in src.get('routes', []):
        r = dict(r, release=vmap.get(r.get('release'), r.get('release')))
        while r['id'] in ids:
            r['id'] += '-2'
        ids.add(r['id'])
        into.setdefault('routes', []).append(r)
    mids = {m['id'] for m in into.get('mods', [])}
    for m in src.get('mods', []):
        if m['id'] in mids:
            continue
        into.setdefault('mods', []).append(dict(m, release=[vmap.get(x, x) for x in m.get('release', [])]))
    have = {s['url'] for s in into.get('screenshots', [])}
    moved = [dict(s, caption=f"{s.get('caption') or 'Originalspiel'} · {name or src['title']}") if not same else s
             for s in src.get('screenshots', []) if s['url'] not in have]
    into['screenshots'] = into.get('screenshots', []) + (moved if not same or len(have) < 2 else [])
    if not into.get('cover') and src.get('cover'):
        into['cover'] = src['cover']
    into['platforms'] = into.get('platforms', []) + [p for p in src.get('platforms', []) if p not in into.get('platforms', [])]
    into['updatedAt'] = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    write(into_path, into)
    src_path.unlink()
    # references elsewhere
    cl = read(DATA / 'changelog.json')
    for e in cl['entries']:
        if e.get('game') == src_id:
            e['game'] = into_id
        if src_id in e.get('games', []):
            e['games'] = list(dict.fromkeys(into_id if x == src_id else x for x in e['games']))
    write(DATA / 'changelog.json', cl)
    pj = read(DATA / 'projects.json')
    for p in pj['projects']:
        if src_id in p.get('games', []):
            p['games'] = list(dict.fromkeys(into_id if x == src_id else x for x in p['games']))
    write(DATA / 'projects.json', pj)
    inbox = read(DATA / 'inbox.json')
    for key in ('aiResearch',):
        inbox.get(key, {}).pop(src_id, None)
    inbox['shotSearch'] = {k: v for k, v in inbox.get('shotSearch', {}).items() if not k.startswith(src_id + '/')}
    for lead in inbox.get('leads', []):
        if lead.get('game') == src_id:
            lead['game'] = into_id
    write(DATA / 'inbox.json', inbox)
    qp = DATA / 'queue.json'
    if qp.exists():
        q = read(qp)
        seen, jobs = set(), []
        for j in q['jobs']:
            if j['game'] == src_id and into_id in inbox.get('aiResearch', {}):
                continue        # the surviving game was researched already
            j = dict(j, game=into_id if j['game'] == src_id else j['game'])
            if j['game'] not in seen:
                seen.add(j['game'])
                jobs.append(j)
        q['jobs'] = jobs
        write(qp, q)
    for state_name in ('emuready_state.json',):
        sp = DATA / state_name
        if sp.exists():
            st = read(sp)
            st.get('games', {}).pop(src_id, None)
            write(sp, st)
    print(f'merge: {src_id} → {into_id} ({len(vmap)} Fassungen, {len(src.get("routes", []))} Spielwege)')


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
    if cmd == 'merge':
        import argparse
        ap = argparse.ArgumentParser(prog='atlas.py merge')
        ap.add_argument('src'), ap.add_argument('into')
        ap.add_argument('--type'), ap.add_argument('--year', type=int), ap.add_argument('--name')
        ap.add_argument('--same', action='store_true', help='gleiches Spiel: Fassungen mit gleichen Plattformen zusammenlegen')
        a = ap.parse_args(sys.argv[2:])
        merge(a.src, a.into, a.type, a.year, a.name, a.same)
        sys.exit(0)
    {'build': build, 'stats': stats, 'format': fmt, 'repair': repair}.get(cmd, lambda: sys.exit(__doc__))()
