#!/usr/bin/env python3
"""KI-Recherche pro Spiel über die OpenAI Responses API (Websuche), Ergebnis direkt in data/.

    python3 scripts/ai_research.py --game grand-theft-auto-san-andreas
    python3 scripts/ai_research.py --batch 3          # wählt Spiele selbst aus
    python3 scripts/ai_research.py --issue-body "game: doom-1993"

Ohne OPENAI_API_KEY passiert nichts. Modell: OPENAI_MODEL (Standard gpt-6.1-sol).
Sicherheitsnetz: jede Angabe braucht eine Quelle, die die Websuche wirklich geliefert hat; Piraterie-/APK-Seiten
werden verworfen; alles Neue ist "ai-unverified"; geschrieben wird nur, wenn `atlas.py validate` danach grün ist.
"""
import argparse
import copy
import json
import os
import re
import sys
import unicodedata
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import atlas  # noqa: E402
from atlas import DATA, read, write  # noqa: E402

API = 'https://api.openai.com/v1/responses'
TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')
BLOCKED = re.compile(r'romsfun|romspedia|vimm\.net|coolrom|emuparadise|nicoblog|romsgames|wowroms|cdromance|'
                     r'archive\.org|apkpure|apkmirror|apkcombo|happymod|an1\.com|modapk|apkdone|rexdl|revdl|'
                     r'getmodsapk|liteapks|torrent|1337x|piratebay|fitgirl|dodi', re.I)
KINDS = ['emulation', 'emulator-mod', 'native', 'native-mod', 'decomp', 'recomp', 'source-port', 'companion',
         'java', 'pc-runtime']
PROJECT_KIND = {'emulation': 'emulator', 'emulator-mod': 'mod', 'native': 'official', 'native-mod': 'mod',
                'decomp': 'port', 'recomp': 'port', 'source-port': 'port', 'companion': 'companion',
                'java': 'launcher', 'pc-runtime': 'runtime'}


def slug(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode()
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')[:60] or 'x'


def norm_url(u):
    return (u or '').split('#')[0].rstrip('/').lower().replace('http://', 'https://').replace('://www.', '://')


def schema(meta):
    s = lambda: {'type': 'string'}
    arr = lambda items: {'type': 'array', 'items': items}
    obj = lambda props: {'type': 'object', 'additionalProperties': False, 'properties': props, 'required': list(props)}
    features = {'type': 'string', 'enum': sorted(meta['features'])}
    return {'type': 'json_schema', 'name': 'atlas_game_research', 'strict': True, 'schema': obj({
        'summary': s(),
        'versions': arr(obj({'key': s(), 'name': s(), 'type': {'type': 'string', 'enum': sorted(meta['versionTypes'])},
                             'year': {'type': 'integer'}, 'platforms': arr(s()), 'traits': arr(features),
                             'note': s(), 'sourceUrl': s()})),
        'routes': arr(obj({'name': s(), 'versionKey': s(), 'kind': {'type': 'string', 'enum': KINDS}, 'runtime': s(),
                           'features': arr(features), 'dualScreen': s(), 'requires': arr(s()), 'benefit': s(),
                           'caveat': s(), 'steps': arr(s()),
                           'effort': {'type': 'string', 'enum': sorted(meta['effort'])},
                           'status': {'type': 'string', 'enum': ['active', 'experimental', 'archived']},
                           'projectName': s(), 'projectUrl': s(), 'sourceUrl': s(),
                           'reports': arr(obj({'url': s(), 'device': s(), 'summary': s()}))})),
        'mods': arr(obj({'name': s(), 'url': s(), 'category': s(), 'edition': s(), 'description': s(), 'sourceUrl': s()})),
    })}


def prompt(game, platforms):
    known = {
        'versions': [{'key': v['id'], 'name': v['name'], 'platforms': v['platforms'], 'year': v.get('year')} for v in game.get('versions', [])],
        'routes': [{'name': r['name'], 'version': r.get('release'), 'kind': r['kind']} for r in game.get('routes', [])],
        'mods': [m['name'] for m in game.get('mods', [])],
    }
    return f"""Du recherchierst für „Handheld Atlas“, einen spielzentrierten Katalog für Android-Handhelds
(Referenzgerät AYN Thor: Snapdragon 8 Gen 2, zwei Displays, Controller). Spiel: „{game['title']}“ ({', '.join(game.get('platforms', []))}).

Bereits bekannt (nicht wiederholen, nur ergänzen oder korrigieren): {json.dumps(known, ensure_ascii=False)}
Allgemeine Emulatoren je Plattform sind schon hinterlegt: {', '.join(sorted(platforms))} – liste sie NICHT als Spielweg,
außer es gibt spielspezifische Belege (Kompatibilität, Patches, empfohlene Einstellungen, Fork mit Dual Screen).

Finde mit der Websuche:
1. versions: alle relevanten Fassungen: Original, Portierungen, offizielle Android-Fassung, Remaster, Remakes,
   Neuauflagen/Sammlungen. Jeweils Plattformen, Erscheinungsjahr, was sie auszeichnet (traits, note). Für bekannte
   Fassungen den vorhandenen key wiederverwenden, sonst einen neuen kurzen key (z. B. "remastered-2024").
2. routes: konkrete Wege, eine Fassung auf Android zu spielen, die über einen allgemeinen Emulator hinausgehen:
   offizielle Android-App, native Ports/Decomps/Recomps/Source-Ports, PC-Laufzeit mit spielspezifischen Belegen,
   Dual-Screen-Mods/Companions, Emulator-Forks mit Spiel-Patches (Widescreen, 60 FPS, Upscaling).
   Je Weg: versionKey, Projekt-URL (Projektseite/GitHub/Google Play), kurze deutsche Texte (benefit, caveat,
   requires = was man selbst besitzen muss), Aufwand, Status. reports: echte Erfahrungsberichte (Reddit, Foren,
   Videos) mit Gerät, 1 Satz Zusammenfassung – bevorzugt AYN Thor, Odin, Retroid.
3. mods: bekannte Mods, die auf Android-tauglichen Fassungen laufen.

Regeln: Jede Angabe braucht sourceUrl/url aus deiner Websuche. Nichts erfinden, keine FPS-Zahlen ohne Quelle.
Keine Links zu ROMs, ISOs, Spieldaten, APK-Spiegeln oder Piraterie. Alle Texte auf Deutsch mit Umlauten.
year = 0, wenn unbekannt. Leere Felder als "" bzw. [].""".strip()


def call_openai(payload, token):
    body = json.dumps({**payload, 'store': False}, ensure_ascii=False).encode()
    req = urllib.request.Request(API, data=body, method='POST', headers={
        'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'User-Agent': 'HandheldAtlas/1.1'})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode())


def output_json(resp):
    if resp.get('status', 'completed') != 'completed':
        raise ValueError(f"Antwort {resp.get('status')}: {(resp.get('incomplete_details') or {}).get('reason')}")
    text = '\n'.join(c.get('text', '') for item in resp.get('output', []) if item.get('type') == 'message'
                     for c in item.get('content', []) if c.get('type') == 'output_text').strip()
    return json.loads(text)


def searched_urls(resp):
    urls = set()
    for item in resp.get('output', []):
        if item.get('type') == 'web_search_call':
            for src in (item.get('action') or {}).get('sources', []) or []:
                urls.add(norm_url(src.get('url')))
        if item.get('type') == 'message':
            for c in item.get('content', []):
                for ann in c.get('annotations', []) or []:
                    urls.add(norm_url(ann.get('url')))
    urls.discard('')
    return urls


def ok_url(u, sources=None):
    if not isinstance(u, str) or not u.startswith('https://') or BLOCKED.search(u):
        return False
    if sources is None:
        return True
    n = norm_url(u)
    # same page or a page on the same site path the search returned (e.g. GitHub repo vs. its README)
    return n in sources or any(s.startswith(n + '/') or n.startswith(s + '/') for s in sources)


def merge(game, projects, result, sources, log):
    """Apply one research result to copies; returns (game, projects, changelog entries)."""
    g, prj = copy.deepcopy(game), copy.deepcopy(projects)
    by_url = {norm_url(p['url']): p for p in prj['projects']}
    entries = []
    versions = g.setdefault('versions', [])
    vmap = {v['id']: v for v in versions}
    vname = {slug(v['name']): v for v in versions}

    for nv in result.get('versions', []):
        if not ok_url(nv.get('sourceUrl'), sources) or not nv.get('name') or not nv.get('platforms'):
            log(f"  verworfen (Fassung ohne belegte Quelle): {nv.get('name')}")
            continue
        v = vmap.get(nv['key']) or vname.get(slug(nv['name']))
        traits = [t for t in nv.get('traits', [])]
        if v:
            if not v.get('year') and nv.get('year'):
                v['year'] = nv['year']
            if not v.get('note') and nv.get('note'):
                v['note'] = nv['note']
            v['traits'] = sorted(set(v.get('traits', [])) | set(traits))
        else:
            vid = slug(nv['key'] or nv['name'])
            while vid in vmap:
                vid += '-2'
            v = {'id': vid, 'name': nv['name'], 'type': nv['type'], 'platforms': nv['platforms'][:8]}
            if nv.get('year'):
                v['year'] = nv['year']
            if traits:
                v['traits'] = traits
            if nv.get('note'):
                v['note'] = nv['note']
            v['links'] = [{'label': 'Quelle', 'url': nv['sourceUrl']}]
            versions.append(v)
            vmap[vid] = v
            vname[slug(v['name'])] = v
            for p in v['platforms']:
                if p not in g['platforms']:
                    g['platforms'].append(p)
            entries.append({'type': 'route-updated', 'text': f"Neue Fassung: {v['name']} (KI-Recherche)", 'url': nv['sourceUrl']})
        vmap[nv['key']] = v

    existing = {norm_url(l['url']) for r in g.get('routes', []) for l in r.get('links', [])}
    existing |= {norm_url(prj_p['url']) for r in g.get('routes', []) for pid in r.get('projects', [])
                 for prj_p in prj['projects'] if prj_p['id'] == pid}
    existing_names = {slug(r['name']) for r in g.get('routes', [])}
    for nr in result.get('routes', []):
        v = vmap.get(nr.get('versionKey'))
        if not v or not ok_url(nr.get('sourceUrl'), sources) or not ok_url(nr.get('projectUrl')):
            log(f"  verworfen (Weg ohne Fassung/Quelle): {nr.get('name')}")
            continue
        reports = [{'url': rp['url'], 'device': rp.get('device', ''), 'summary': rp['summary'], 'date': TODAY}
                   for rp in nr.get('reports', []) if ok_url(rp.get('url'), sources) and rp.get('summary')]
        if norm_url(nr['projectUrl']) in existing or slug(nr['name']) in existing_names:
            # known way: only add new experience reports
            for r in g['routes']:
                urls = {norm_url(l['url']) for l in r.get('links', [])} | {norm_url(p['url']) for p in prj['projects'] if p['id'] in r.get('projects', [])}
                if norm_url(nr['projectUrl']) in urls or slug(r['name']) == slug(nr['name']):
                    have = {norm_url(x['url']) for x in r.setdefault('reports', [])}
                    new = [x for x in reports if norm_url(x['url']) not in have]
                    r['reports'].extend(new)
                    if new:
                        entries.append({'type': 'route-updated', 'text': f"{len(new)} Erfahrungsbericht(e) zu {r['name']} (KI-Recherche)", 'url': new[0]['url']})
            continue
        p = by_url.get(norm_url(nr['projectUrl']))
        if not p:
            pid = slug(nr.get('projectName') or nr['name'])
            while any(x['id'] == pid for x in prj['projects']):
                pid += '-2'
            m = re.match(r'https://github\.com/([^/]+/[^/#?]+)', nr['projectUrl'])
            p = {'id': pid, 'name': nr.get('projectName') or nr['name'], 'kind': PROJECT_KIND[nr['kind']],
                 'url': nr['projectUrl'], 'repo': m.group(1) if m else None, 'description': '', 'games': [], 'checkedAt': TODAY}
            prj['projects'].append(p)
            by_url[norm_url(p['url'])] = p
        if g['id'] not in p['games']:
            p['games'].append(g['id'])
        rid = slug(f"ai-{nr['name']}")
        while any(r['id'] == rid for r in g['routes']):
            rid += '-2'
        route = {'id': rid, 'name': nr['name'], 'kind': nr['kind'], 'release': v['id'], 'runtime': nr.get('runtime') or None,
                 'projects': [p['id']], 'targets': ['android'], 'features': sorted(set(nr.get('features', []))),
                 'dualScreen': nr.get('dualScreen') or None, 'requires': nr.get('requires', []),
                 'benefit': nr.get('benefit', ''), 'caveat': nr.get('caveat', ''), 'steps': nr.get('steps', []),
                 'version': None, 'effort': nr['effort'], 'status': nr['status'], 'verification': 'ai-unverified',
                 'testedOn': [], 'screenshots': [], 'links': [{'label': 'Quelle', 'url': nr['sourceUrl']}],
                 'reports': reports, 'performance': [], 'checkedAt': TODAY}
        g['routes'].append(route)
        existing.add(norm_url(nr['projectUrl']))
        existing_names.add(slug(nr['name']))
        entries.append({'type': 'route-added', 'text': f"Neuer Spielweg: {nr['name']} ({v['name']}, KI-Recherche)", 'url': nr['sourceUrl']})

    have_mods = {norm_url(m['url']) for m in g.get('mods', [])} | {slug(m['name']) for m in g.get('mods', [])}
    for nm in result.get('mods', []):
        if not ok_url(nm.get('url')) or not ok_url(nm.get('sourceUrl'), sources):
            continue
        if norm_url(nm['url']) in have_mods or slug(nm['name']) in have_mods:
            continue
        g.setdefault('mods', []).append({'id': slug(nm['name']), 'name': nm['name'], 'category': nm.get('category') or 'other',
                                         'url': nm['url'], 'edition': nm.get('edition') or None,
                                         'description': nm.get('description', ''), 'verification': 'ai-unverified'})
        have_mods.add(norm_url(nm['url']))
        entries.append({'type': 'mod-added', 'text': f"Neuer Mod: {nm['name']} (KI-Recherche)", 'url': nm['url']})

    if result.get('summary') and (not g.get('summary') or len(g.get('versions', [])) > len(game.get('versions', []))):
        g['summary'] = result['summary']
    if entries:
        g['updatedAt'] = TODAY
    for e in entries:
        e.update(date=TODAY, by='ai-research', game=g['id'])
    return g, prj, entries


def pick_games(n):
    """Games worth researching: popular franchises, no versions detail yet, oldest updatedAt first."""
    games = [read(f) for f in (DATA / 'games').glob('*.json')]
    franchise_size = {}
    for g in games:
        franchise_size[g['franchise']] = franchise_size.get(g['franchise'], 0) + 1
    state = read(DATA / 'inbox.json').get('aiResearch', {})
    def key(g):
        detailed = any(v.get('year') for v in g.get('versions', []))
        return (state.get(g['id'], ''), detailed, -franchise_size[g['franchise']], g['id'])
    return [g['id'] for g in sorted(games, key=key)[:n]]


def research(game_id, token, model, log=print):
    path = DATA / 'games' / f'{game_id}.json'
    game, projects, meta = read(path), read(DATA / 'projects.json'), read(DATA / 'meta.json')
    platforms = read(DATA / 'platforms.json')['platforms']
    resp = call_openai({'model': model, 'tools': [{'type': 'web_search', 'search_context_size': 'high'}],
                        'include': ['web_search_call.action.sources'], 'tool_choice': 'required',
                        'reasoning': {'effort': 'medium'}, 'text': {'format': schema(meta)},
                        'input': prompt(game, platforms), 'max_output_tokens': 16000}, token)
    result = output_json(resp)
    g, prj, entries = merge(game, projects, result, searched_urls(resp), log)
    return apply(game_id, g, prj, entries, log)


def apply(game_id, g, prj, entries, log):
    """Write only if the whole database still validates."""
    path = DATA / 'games' / f'{game_id}.json'
    old_game, old_prj = path.read_text(encoding='utf-8'), (DATA / 'projects.json').read_text(encoding='utf-8')
    write(path, g)
    write(DATA / 'projects.json', prj)
    problems = atlas.validate()
    if problems:
        path.write_text(old_game, encoding='utf-8')
        (DATA / 'projects.json').write_text(old_prj, encoding='utf-8')
        log(f'  NICHT übernommen, Validierung schlägt fehl: {problems[:3]}')
        return []
    if entries:
        cl = read(DATA / 'changelog.json')
        cl['entries'][0:0] = entries
        write(DATA / 'changelog.json', cl)
    inbox = read(DATA / 'inbox.json')
    inbox.setdefault('aiResearch', {})[game_id] = TODAY
    write(DATA / 'inbox.json', inbox)
    return entries


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--game')
    ap.add_argument('--batch', type=int, default=0)
    ap.add_argument('--issue-body', default='')
    ap.add_argument('--issue-title', default='')
    args = ap.parse_args()
    token = os.environ.get('OPENAI_API_KEY')
    if not token:
        print('OPENAI_API_KEY fehlt – keine KI-Recherche ausgeführt.')
        return 0
    model = os.environ.get('OPENAI_MODEL') or 'gpt-6.1-sol'
    ids = []
    if args.game:
        ids = [args.game]
    elif args.issue_body or args.issue_title:
        m = re.search(r'game:\s*([a-z0-9-]+)', args.issue_body)
        if m:
            ids = [m.group(1)]
        else:
            title = re.sub(r'^recherche:\s*', '', args.issue_title, flags=re.I).strip().lower()
            ids = [read(f)['id'] for f in (DATA / 'games').glob('*.json') if read(f)['title'].lower() == title][:1]
    elif args.batch:
        ids = pick_games(args.batch)
    lines = []
    for gid in ids:
        if not (DATA / 'games' / f'{gid}.json').exists():
            lines.append(f'- `{gid}`: Spiel nicht gefunden')
            continue
        print(f'Recherche: {gid} ({model})')
        try:
            entries = research(gid, token, model)
        except Exception as e:  # noqa: BLE001 – one failing game must not stop the batch
            lines.append(f'- `{gid}`: Fehler – {type(e).__name__}: {str(e)[:200]}')
            continue
        lines.append(f'- **{gid}**: ' + ('; '.join(e['text'] for e in entries) if entries else 'nichts Neues gefunden'))
    report = '\n'.join(lines) or 'Kein Spiel ausgewählt.'
    print(report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(os.environ['GITHUB_STEP_SUMMARY']).write_text('### KI-Recherche\n\n' + report + '\n', encoding='utf-8')
    Path(os.environ.get('RESEARCH_REPORT', '/tmp/atlas-research.md')).write_text(report + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
