#!/usr/bin/env python3
"""Wikidata as free backbone of the catalogue (stage 0/1 – no AI, no cost).

For every game Atlas finds the Wikidata item and fills in what Wikidata knows reliably:
  - release years per platform → versions ("Original (1993)", "Portierung – PlayStation (1995)", official Android release)
  - genre, the Wikipedia article (used by the image search), the Wikidata id
For a series it lists every released game (also spin-offs and mobile games) and adds the missing ones as index
entries; remakes/remasters/compilations of games Atlas already has become versions of those games.

    python3 scripts/wikidata.py --enrich 150        # daily in the watcher: games without Wikidata data
    python3 scripts/wikidata.py --series "Doom"     # complete one series (also used by the franchise analysis)
"""
import argparse
import json
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import atlas  # noqa: E402
from atlas import DATA, read, write  # noqa: E402

SPARQL = 'https://query.wikidata.org/sparql'
API = 'https://www.wikidata.org/w/api.php'
UA = 'HandheldAtlas/1.4 (https://github.com/markusklier/handheld-atlas; private game catalogue)'
TODAY = date.today().isoformat()
STATE = DATA / 'wikidata_state.json'

# Wikidata platform labels → Atlas platform names (others go through atlas.canon_platforms)
PLATFORMS = {
    'Microsoft Windows': 'PC', 'MS-DOS': 'PC', 'DOS': 'PC', 'IBM PC compatible': 'PC', 'Windows': 'PC', 'personal computer': 'PC',
    'macOS': 'Macintosh', 'classic Mac OS': 'Macintosh', 'Mac OS': 'Macintosh', 'Macintosh': 'Macintosh',
    'Nintendo Entertainment System': 'NES', 'Family Computer': 'NES', 'Super Nintendo Entertainment System': 'SNES',
    'Super Famicom': 'SNES', 'Nintendo 64': 'Nintendo 64', 'GameCube': 'Nintendo GameCube', 'Nintendo GameCube': 'Nintendo GameCube',
    'Wii': 'Wii', 'Wii U': 'Wii U', 'Nintendo Switch': 'Nintendo Switch', 'Nintendo Switch 2': 'Nintendo Switch 2',
    'Game Boy': 'Game Boy / Game Boy Color', 'Game Boy Color': 'Game Boy / Game Boy Color', 'Game Boy Advance': 'Game Boy Advance',
    'Nintendo DS': 'Nintendo DS', 'Nintendo DSi': 'Nintendo DS', 'Nintendo 3DS': 'Nintendo 3DS', 'New Nintendo 3DS': 'Nintendo 3DS',
    'PlayStation': 'PlayStation', 'PlayStation 2': 'PlayStation 2', 'PlayStation 3': 'PlayStation 3', 'PlayStation 4': 'PlayStation 4',
    'PlayStation 5': 'PlayStation 5', 'PlayStation Portable': 'PSP', 'PlayStation Vita': 'PlayStation Vita',
    'Xbox': 'Xbox', 'Xbox 360': 'Xbox 360', 'Xbox One': 'Xbox One', 'Xbox Series X and Series S': 'Xbox Series',
    'Xbox Series X/S': 'Xbox Series', 'Sega Genesis': 'Sega Mega Drive', 'Mega Drive': 'Sega Mega Drive', 'Sega Saturn': 'Sega Saturn',
    'Dreamcast': 'Dreamcast', 'Sega Dreamcast': 'Dreamcast', 'Android': 'Android', 'iOS': 'iOS', 'iPadOS': 'iOS',
    'Linux': 'Linux', 'Stadia': 'Google Stadia', 'Google Stadia': 'Google Stadia', 'arcade video game': 'Arcade',
    'arcade game machine': 'Arcade', 'arcade cabinet': 'Arcade', 'Nokia N-Gage': 'Nokia N-Gage', 'N-Gage': 'Nokia N-Gage',
    'Sega CD': 'Sega CD', 'Sega 32X': '32X', 'Master System': 'Sega Master System', 'Game Gear': 'Sega Game Gear',
    'TurboGrafx-16': 'PC Engine', 'PC Engine': 'PC Engine', 'Atari Jaguar': 'Atari Jaguar', '3DO Interactive Multiplayer': '3DO',
    'Neo Geo': 'Neo Geo', 'Amiga': 'Amiga', 'Commodore 64': 'Commodore 64', 'ZX Spectrum': 'ZX Spectrum', 'Amstrad CPC': 'Amstrad CPC',
    'Atari ST': 'Atari ST', 'Java Platform, Micro Edition': 'Java ME', 'Windows Phone': 'Windows Phone', 'BlackBerry OS': 'BlackBerry OS',
}
# instances that are not standalone games for Atlas
SKIP_KINDS = re.compile(r'expansion|downloadable content|\bdlc\b|video game mod|demo|cancel|unreleased|add-on|level pack|'
                        r'mission pack|soundtrack|film|television|novel|comic|board game|card game|tabletop', re.I)
REMAKE = re.compile(r'remake', re.I)
REMASTER = re.compile(r'remaster|enhanced|definitive|hd version', re.I)
COMPILATION = re.compile(r'compilation|collection|bundle', re.I)


# ---------- HTTP ----------
def http(url, data=None):
    req = urllib.request.Request(url, data=data, headers={'User-Agent': UA, 'Accept': 'application/json'})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode())
        except urllib.error.HTTPError as e:
            if e.code in (429, 503) and attempt < 3:
                time.sleep(int(e.headers.get('Retry-After') or 10 * (attempt + 1)))
                continue
            raise
    return {}


def sparql(query, fetch=http):
    data = urllib.parse.urlencode({'query': query, 'format': 'json'}).encode()
    res = fetch(SPARQL, data)
    rows = []
    for b in res.get('results', {}).get('bindings', []):
        rows.append({k: v.get('value') for k, v in b.items()})
    return rows


def entities(ids, fetch=http, props='claims|labels|sitelinks'):
    out = {}
    ids = [i for i in dict.fromkeys(ids) if i]
    for i in range(0, len(ids), 50):
        q = urllib.parse.urlencode({'action': 'wbgetentities', 'ids': '|'.join(ids[i:i + 50]), 'props': props,
                                    'languages': 'de|en', 'sitefilter': 'enwiki|dewiki', 'format': 'json'})
        out.update(fetch(f'{API}?{q}').get('entities', {}))
    return out


def qid(url):
    return (url or '').rsplit('/', 1)[-1]


# ---------- facts of one item ----------
def label_of(ent, lang_order=('en', 'de')):
    for lang in lang_order:
        v = (ent.get('labels') or {}).get(lang, {}).get('value')
        if v:
            return v
    return None


def claim_ids(ent, prop):
    out = []
    for c in (ent.get('claims') or {}).get(prop, []):
        v = ((c.get('mainsnak') or {}).get('datavalue') or {}).get('value')
        if isinstance(v, dict) and v.get('id'):
            out.append(v['id'])
    return out


def year_of(time_value):
    m = re.match(r'[+-]?(\d{4})', time_value or '')
    return int(m.group(1)) if m else None


def facts(ent, labels):
    """What Atlas uses from a Wikidata item. `labels` maps referenced ids (platforms, genres, kinds) to labels."""
    plat_year, years = {}, []
    for c in (ent.get('claims') or {}).get('P577', []):
        y = year_of((((c.get('mainsnak') or {}).get('datavalue') or {}).get('value') or {}).get('time'))
        if not y:
            continue
        years.append(y)
        for q in (c.get('qualifiers') or {}).get('P400', []):
            pid = ((q.get('datavalue') or {}).get('value') or {}).get('id')
            if pid:
                plat_year[pid] = min(y, plat_year.get(pid, 9999))
    platforms = {}
    for pid in claim_ids(ent, 'P400'):
        name = map_platform(labels.get(pid))
        if name:
            y = plat_year.get(pid)
            platforms[name] = min(y, platforms.get(name) or 9999) if y else platforms.get(name)
    for pid, y in plat_year.items():               # dated platform not listed in P400
        name = map_platform(labels.get(pid))
        if name and name not in platforms:
            platforms[name] = y
    sl = ent.get('sitelinks') or {}
    wiki = lambda k, host: f"https://{host}.wikipedia.org/wiki/{urllib.parse.quote(sl[k]['title'].replace(' ', '_'))}" if k in sl else None
    genres = [labels.get(g) for g in claim_ids(ent, 'P136') if labels.get(g)]
    return {'qid': ent.get('id'), 'title': label_of(ent), 'titleDe': label_of(ent, ('de',)),
            'year': min(years) if years else None, 'platforms': platforms,
            'kinds': [labels.get(k) or k for k in claim_ids(ent, 'P31')],
            'genre': genres[0] if genres else None, 'series': claim_ids(ent, 'P179'),
            'basedOn': claim_ids(ent, 'P144'), 'parts': claim_ids(ent, 'P527'),
            'enwiki': wiki('enwiki', 'en'), 'dewiki': wiki('dewiki', 'de')}


def map_platform(label):
    if not label or re.fullmatch(r'Q\d+', label):
        return None
    name = PLATFORMS.get(label, label)
    return atlas.canon_platforms([name])[0] if name else None


def referenced(ents):
    ids = set()
    for e in ents.values():
        for prop in ('P400', 'P136', 'P31'):
            ids.update(claim_ids(e, prop))
        for c in (e.get('claims') or {}).get('P577', []):
            for q in (c.get('qualifiers') or {}).get('P400', []):
                v = ((q.get('datavalue') or {}).get('value') or {}).get('id')
                if v:
                    ids.add(v)
    return ids


class Labels:
    """Label cache for platforms, genres and kinds (kept in wikidata_state.json)."""
    def __init__(self, state, fetch):
        self.cache = state.setdefault('labels', {})
        self.fetch = fetch

    def resolve(self, ids):
        missing = [i for i in ids if not self.cache.get(i) or re.fullmatch(r'Q\d+', self.cache[i])]
        for qid_, ent in entities(missing, self.fetch, props='labels').items():
            lab = label_of(ent)
            if lab:
                self.cache[qid_] = lab
        rest = [i for i in missing if not self.cache.get(i) or re.fullmatch(r'Q\d+', self.cache[i])]
        for i in range(0, len(rest), 60):          # API answered without label (seen for big items): ask SPARQL
            values = ' '.join(f'wd:{q}' for q in rest[i:i + 60])
            for r in sparql(f"""SELECT ?i ?l WHERE {{ VALUES ?i {{ {values} }} ?i rdfs:label ?l .
  FILTER(LANG(?l) = "en" || LANG(?l) = "de") }}""", self.fetch):
                q = qid(r['i'])
                if r.get('l') and (not self.cache.get(q) or re.fullmatch(r'Q\d+', self.cache[q]) or r.get('l').isascii()):
                    self.cache[q] = r['l']
        for i in rest:
            if re.fullmatch(r'Q\d+', self.cache.get(i) or ''):
                self.cache.pop(i, None)            # never store an id as label; retried next run
        return self.cache


# ---------- versions from release years ----------
def version_rows(f):
    """[(type, year, [platforms])] – earliest year = original, later years = ports."""
    by_year = {}
    for p, y in f['platforms'].items():
        if y:
            by_year.setdefault(y, []).append(p)
    rows = []
    for i, y in enumerate(sorted(by_year)):
        plats = sorted(by_year[y])
        kind = 'original' if i == 0 else 'android' if 'Android' in plats and set(plats) <= {'Android', 'iOS'} else 'port'
        rows.append((kind, y, plats))
    return rows


def vname(kind, year, plats):
    short = ', '.join(plats[:3]) + (' u. a.' if len(plats) > 3 else '')
    return f'Original ({year})' if kind == 'original' else f'{short} ({year})'


def slug(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:60]


def enrich_game(g, f):
    """Fill gaps of one game from its Wikidata facts. Never overwrites, never deletes. Returns a list of changes."""
    changes = []
    if g.get('wikidata') != f['qid']:
        g['wikidata'] = f['qid']
    if f.get('enwiki') and not g.get('wikipedia'):
        g['wikipedia'] = f['enwiki']
    if f.get('genre') and not g.get('genre'):
        g['genre'] = f['genre']
        changes.append('Genre')
    versions = g.setdefault('versions', [])
    covered = {}
    for v in versions:
        for p in v.get('platforms', []):
            covered.setdefault(p, v)
    new_rows = []
    for kind, year, plats in version_rows(f):
        todo = []
        for p in plats:
            v = covered.get(p)
            if v is None:
                todo.append(p)
            elif not v.get('year') and v.get('type') in ('original', 'release', 'port', 'android') and (kind == 'original' or v.get('type') != 'original'):
                v['year'] = year
                changes.append(f'Jahr {year} für {v["name"]}')
        if todo:
            new_rows.append((kind, year, todo))
    has_original = any(v.get('type') == 'original' for v in versions)
    for kind, year, plats in new_rows:
        if kind == 'original' and has_original:
            kind = 'port'
        vid = slug(f"{plats[0]}-{year}")
        while any(v['id'] == vid for v in versions):
            vid += '-2'
        versions.append({'id': vid, 'name': vname(kind, year, plats), 'type': kind, 'year': year, 'platforms': plats,
                         'links': [{'label': 'Wikidata', 'url': f"https://www.wikidata.org/wiki/{f['qid']}"}]})
        has_original = has_original or kind == 'original'
        changes.append(f"Fassung {vname(kind, year, plats)}")
    originals = [p for v in versions if v.get('type') == 'original' for p in v['platforms']]
    for p in originals:
        if p not in g.setdefault('platforms', []):
            g['platforms'].append(p)
    return changes


def new_game(f, franchise):
    rows = version_rows(f)
    title = f['title']
    gid = slug(title)
    if (DATA / 'games' / f'{gid}.json').exists():
        gid = slug(f"{title}-{f['year']}") if f.get('year') else gid + '-2'
        if f.get('year'):
            title = f"{title} ({f['year']})"
    g = {'id': gid, 'title': title, 'franchise': franchise, 'platforms': rows[0][2] if rows else list(f['platforms'])[:4],
         'versions': [], 'routes': [], 'mods': [], 'updatedAt': TODAY, 'tier': 'basis'}
    if not rows and f['platforms']:            # no dated releases: one undated original
        g['versions'] = [{'id': slug(list(f['platforms'])[0]), 'name': 'Original', 'type': 'original',
                          'platforms': sorted(f['platforms'])[:8]}]
    enrich_game(g, f)
    return g


# ---------- finding items for Atlas games ----------
def title_variants(title):
    base = re.sub(r'\s*\((?:\d{4}|[^)]*video game[^)]*)\)\s*$', '', title).strip()
    out = {base, base.replace('’', "'")}
    if any(w.isupper() and len(w) > 2 for w in base.split()):          # "DOOM" → "Doom"
        out.add(' '.join(w.capitalize() if w.isupper() and len(w) > 2 else w for w in base.split()))
    if base.lower().startswith('the '):
        out.add(base[4:])
    return [t for t in out if t]


def lookup(games, fetch=http):
    """{game id: [(qid, year)]} – Wikidata video games whose English label (or alias) equals the title."""
    want = {}
    for g in games:
        for t in title_variants(g['title']):
            want.setdefault(t, []).append(g['id'])
    found = {}
    keys = list(want)
    for i in range(0, len(keys), 40):
        values = ' '.join(json.dumps(t, ensure_ascii=False) + '@en' for t in keys[i:i + 40])
        rows = sparql(f"""SELECT ?label ?item (MIN(YEAR(?d)) AS ?y) WHERE {{
  VALUES ?label {{ {values} }}
  {{ ?item rdfs:label ?label }} UNION {{ ?item skos:altLabel ?label }}
  ?item wdt:P31/wdt:P279* wd:Q7889 .
  OPTIONAL {{ ?item wdt:P577 ?d }}
}} GROUP BY ?label ?item""", fetch)
        for r in rows:
            for gid in want.get(r['label'], []):
                found.setdefault(gid, []).append((qid(r['item']), int(r['y']) if r.get('y') else None))
    return found


def choose(g, candidates):
    year = atlas_year(g)
    cands = list(dict.fromkeys(candidates))
    if year:
        close = sorted((c for c in cands if c[1] and abs(c[1] - year) <= 1), key=lambda c: abs(c[1] - year))
        return close[0][0] if close else None
    return cands[0][0] if len({c[0] for c in cands}) == 1 else None      # ambiguous without a year → leave it


def atlas_year(g):
    m = re.search(r'\((\d{4})\)', g.get('title', ''))
    if m:
        return int(m.group(1))
    ys = [v['year'] for v in g.get('versions', []) if v.get('year') and v.get('type') == 'original']
    return min(ys) if ys else None


# ---------- daily enrichment ----------
def enrich(limit=150, fetch=http, log=print, only=None):
    state = read(STATE) if STATE.exists() else {}
    tried = state.setdefault('tried', {})
    cutoff = (date.today() - timedelta(days=60)).isoformat()
    games = []
    for f in sorted((DATA / 'games').glob('*.json')):
        g = read(f)
        if only is not None:
            if g['id'] in only:
                games.append(g)
            continue
        if not g.get('wikidata') and tried.get(g['id'], '') < cutoff:
            games.append(g)
    games = games[:limit]
    if not games:
        return 0
    found = lookup(games, fetch)
    chosen = {}
    for g in games:
        tried[g['id']] = TODAY
        q = g.get('wikidata') or choose(g, found.get(g['id'], []))
        if q:
            chosen[g['id']] = q
    ents = entities(list(chosen.values()), fetch)
    labels = Labels(state, fetch).resolve(referenced(ents))
    touched = 0
    for g in games:
        q = chosen.get(g['id'])
        if not q or q not in ents:
            continue
        f = facts(ents[q], labels)
        before = json.dumps(g, sort_keys=True)
        changes = enrich_game(g, f)
        if json.dumps(g, sort_keys=True) != before:
            write(DATA / 'games' / f"{g['id']}.json", g)
            touched += 1
            if changes:
                log(f"  {g['id']}: {', '.join(changes[:4])}")
    write(STATE, state)
    log(f'wikidata.py: {len(chosen)}/{len(games)} Spiele zugeordnet, {touched} ergänzt')
    return touched


# ---------- series ----------
def series_qid(name, games, ents, fetch=http):
    counts = {}
    for g in games:
        e = ents.get(g.get('wikidata') or '')
        for s in claim_ids(e or {}, 'P179'):
            counts[s] = counts.get(s, 0) + 1
    if counts:
        return max(counts, key=counts.get)
    rows = sparql(f"""SELECT ?s WHERE {{
  {{ ?s rdfs:label {json.dumps(name, ensure_ascii=False)}@en }} UNION {{ ?s skos:altLabel {json.dumps(name, ensure_ascii=False)}@en }}
  ?s wdt:P31/wdt:P279* wd:Q7058673 .
}} LIMIT 3""", fetch)
    return qid(rows[0]['s']) if rows else None


def complete_series(name, fetch=http, log=print):
    """Every released game of the series: missing ones become index entries, remakes/remasters/compilations of
    games Atlas has become versions. Returns a report dict (empty 'members' = Wikidata has no such series)."""
    state = read(STATE) if STATE.exists() else {}
    games = [read(f) for f in (DATA / 'games').glob('*.json')]
    mine = [g for g in games if g.get('franchise') == name]
    enrich(len(mine) + 5, fetch, log, only={g['id'] for g in mine if not g.get('wikidata')})
    games = [read(f) for f in (DATA / 'games').glob('*.json')]
    mine = [g for g in games if g.get('franchise') == name]
    sq = series_qid(name, mine, entities([g['wikidata'] for g in mine if g.get('wikidata')], fetch), fetch)
    report = {'date': TODAY, 'source': 'wikidata', 'series': sq, 'members': 0, 'added': [], 'versions': [], 'skipped': []}
    if not sq:
        log(f'  Wikidata: keine Reihe „{name}“ gefunden')
        return report
    rows = sparql(f"""SELECT DISTINCT ?item WHERE {{
  ?item (wdt:P179|wdt:P361)+ wd:{sq} .
  ?item wdt:P31/wdt:P279* wd:Q7889 .
}}""", fetch)
    member_ids = [qid(r['item']) for r in rows]
    ents = entities(member_ids, fetch)
    labels = Labels(state, fetch).resolve(referenced(ents))
    by_qid = {g['wikidata']: g for g in games if g.get('wikidata')}
    report['members'] = len(member_ids)
    fs = {q: facts(e, labels) for q, e in ents.items()}
    order = sorted(fs.values(), key=lambda f: f['year'] or 9999)
    for f in order:
        title = f['title'] or f['qid']
        if any(SKIP_KINDS.search(k or '') for k in f['kinds']):
            report['skipped'].append({'title': title, 'reason': 'Erweiterung/DLC/kein eigenes Spiel'})
            continue
        if not f['year'] or f['year'] > date.today().year:
            report['skipped'].append({'title': title, 'reason': 'nicht erschienen'})
            continue
        if f['qid'] in by_qid:
            continue
        from ai_research import find_game         # same dedupe as the AI path (title, year, subtitle)
        existing = find_game(title, f['year'])
        if existing:
            g = read(DATA / 'games' / f'{existing}.json')
            if not g.get('wikidata'):
                enrich_game(g, f)
                g['franchise'] = g.get('franchise') if g.get('franchise') not in (None, '', g['title']) else name
                write(DATA / 'games' / f'{existing}.json', g)
                by_qid[f['qid']] = g
            continue
        # remake / remaster / compilation of a game we have → version of that game
        targets = [by_qid[q] for q in (f['basedOn'] or []) if q in by_qid]
        kinds = ' '.join(k or '' for k in f['kinds'])
        if COMPILATION.search(kinds) or COMPILATION.search(title):
            targets += [by_qid[q] for q in f['parts'] if q in by_qid]
        if targets:
            vtype = ('collection' if COMPILATION.search(kinds) or COMPILATION.search(title) else
                     'remaster' if REMASTER.search(kinds + ' ' + title) else 'remake' if REMAKE.search(kinds) else 'rerelease')
            for t in {t['id']: t for t in targets}.values():
                t = read(DATA / 'games' / f"{t['id']}.json")
                if any(f['qid'] in json.dumps(v.get('links', [])) for v in t.get('versions', [])):
                    continue
                plats = sorted(f['platforms'])[:8] or t.get('platforms', [])[:1]
                vid = slug(title)
                while any(v['id'] == vid for v in t['versions']):
                    vid += '-2'
                t['versions'].append({'id': vid, 'name': f"{title} ({f['year']})", 'type': vtype, 'year': f['year'],
                                      'platforms': plats,
                                      'links': [{'label': 'Wikidata', 'url': f"https://www.wikidata.org/wiki/{f['qid']}"}]})
                t['updatedAt'] = TODAY
                write(DATA / 'games' / f"{t['id']}.json", t)
                report['versions'].append(f"{t['id']}: {title}")
            continue
        g = new_game(f, name)
        if (DATA / 'games' / f"{g['id']}.json").exists():
            report['skipped'].append({'title': title, 'reason': 'Dateiname belegt'})
            continue
        write(DATA / 'games' / f"{g['id']}.json", g)
        by_qid[f['qid']] = g
        report['added'].append(g['id'])
    write(STATE, state)
    log(f"  Wikidata-Reihe {name} ({sq}): {report['members']} Einträge, {len(report['added'])} neue Spiele, "
        f"{len(report['versions'])} Fassungen, {len(report['skipped'])} übersprungen")
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--enrich', type=int, default=0)
    ap.add_argument('--series')
    args = ap.parse_args()
    if args.enrich:
        enrich(args.enrich)
    if args.series:
        complete_series(args.series)
    problems = atlas.validate()
    if problems:
        print('Validierung fehlgeschlagen:', problems[:5])
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
