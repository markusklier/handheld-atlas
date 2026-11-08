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
MAX_NEW_VERSIONS = 12
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
    mod_cats = {'type': 'string', 'enum': sorted(meta.get('modCategories') or ['other'])}
    return {'type': 'json_schema', 'name': 'atlas_game_research', 'strict': True, 'schema': obj({
        'summary': s(),
        'series': s(),
        'versions': arr(obj({'key': s(), 'name': s(), 'type': {'type': 'string', 'enum': sorted(meta['versionTypes'])},
                             'year': {'type': 'integer'}, 'platforms': arr(s()), 'traits': arr(features),
                             'note': s(), 'sourceUrl': s()})),
        'routes': arr(obj({'name': s(), 'versionKey': s(), 'kind': {'type': 'string', 'enum': KINDS}, 'runtime': s(),
                           'features': arr(features), 'dualScreen': s(),
                           'dualScreenType': {'type': 'string', 'enum': ['', 'integrated', 'companion', 'info', 'native']},
                           'requires': arr(s()), 'benefit': s(),
                           'caveat': s(), 'steps': arr(s()),
                           'effort': {'type': 'string', 'enum': sorted(meta['effort'])},
                           'status': {'type': 'string', 'enum': ['active', 'experimental', 'archived']},
                           'projectName': s(), 'projectUrl': s(), 'sourceUrl': s(),
                           'screenshots': arr(obj({'url': s(), 'caption': s()})),
                           'reports': arr(obj({'url': s(), 'device': s(), 'summary': s()}))})),
        'mods': arr(obj({'name': s(), 'url': s(), 'category': mod_cats, 'versionKeys': arr(s()), 'edition': s(),
                         'description': s(), 'sourceUrl': s()})),
    })}


RULES = """Finde mit der Websuche:
1. versions: VOLLSTÄNDIG alle offiziell erschienenen Fassungen (Atlas ist auch ein Archiv): Original mit allen
   Erstplattformen, spätere Portierungen, Editionen (z. B. Special/Anniversary/GOTY), offizielle Android-Fassungen (auch
   eingestellte), Remaster, Remakes, Neuauflagen. Gleiche Veröffentlichung auf mehreren Plattformen = EINE Fassung mit
   mehreren Plattformen (z. B. "Original (2011)": PC, Xbox 360, PlayStation 3). Höchstens 15. Weglassen nur:
   angekündigte/unveröffentlichte Fassungen und reine Sammelboxen ohne Unterschied. Jeweils Plattformen, Erscheinungsjahr,
   was sie auszeichnet (traits, note: 1–2 Sätze, warum man sie wählen würde oder was anders ist).
   Für bekannte Fassungen den vorhandenen key wiederverwenden (auch wenn du weitere Plattformen ergänzt), sonst einen
   neuen kurzen key (z. B. "remastered-2024").
2. routes: konkrete Wege, eine Fassung auf Android zu spielen, die über einen allgemeinen Emulator hinausgehen:
   offizielle Android-App, native Ports/Decomps/Recomps/Source-Ports, PC-Laufzeit (GameNative, Winlator, GameHub …)
   mit spielspezifischen Belegen, Dual-Screen-Mods/Companions, Emulator-Forks mit Spiel-Patches (Widescreen, 60 FPS).
   Dual Screen hat Priorität: suche gezielt nach Dual-Screen-Mods, Companions und Forks („<Spiel> dual screen“,
   „<Spiel> second screen AYN Thor“, GitHub, r/SBCGaming, r/AYN). dualScreenType: integrated = das Spiel/der Port
   zeichnet selbst auf den zweiten Bildschirm (live), companion = separate Begleit-App, info = nur statische Infos/Karte,
   native = das Original hatte zwei Bildschirme (DS, 3DS, Wii U); "" wenn kein Dual Screen. Feature "two-screens" NUR
   für Originale mit zwei Bildschirmen, sonst "dual-screen".
   Je Weg: versionKey, Projekt-URL (Projektseite/GitHub/Google Play), kurze deutsche Texte (benefit, caveat,
   requires = was man selbst besitzen muss), Aufwand, Status. reports: echte Erfahrungsberichte (Reddit, Foren,
   Videos, EmuReady) mit Gerät, 1 Satz Zusammenfassung – bevorzugt AYN Thor, Odin 2, Retroid Pocket 5.
   screenshots: bis zu 4 direkte Bild-URLs (png/jpg/webp/gif), die genau diesen Weg zeigen (README, Release-Notes,
   Projektseite, Beitrag des Autors) – bei Dual-Screen-Wegen bevorzugt Bilder mit beiden Bildschirmen.
3. mods: bekannte Mods für Android-taugliche Fassungen, auch Grafik/Texturen, Shader/ReShade, Widescreen-/FPS-Patches,
   Fehlerbehebungen, Übersetzungen. category passend wählen; versionKeys = Fassungen, mit denen der Mod funktioniert.
4. series: die Spielereihe, unter der das Spiel erscheint (z. B. "Luigi's Mansion", nicht "Super Mario"); "" wenn Einzeltitel.

summary: 1–2 Sätze für Spieler (welche Fassung/welcher Weg ist auf dem Handheld interessant), kein Rechercheprotokoll.

Regeln: Jede Angabe braucht sourceUrl/url aus deiner Websuche. Nichts erfinden, keine FPS-Zahlen ohne Quelle.
Keine Links zu ROMs, ISOs, Spieldaten, APK-Spiegeln oder Piraterie. Alle Texte auf Deutsch mit Umlauten.
year = 0, wenn unbekannt. Leere Felder als "" bzw. []."""


def prompt(game, platforms, focus=None):
    known = {
        'versions': [{'key': v['id'], 'name': v['name'], 'platforms': v['platforms'], 'year': v.get('year')} for v in game.get('versions', [])],
        'routes': [{'name': r['name'], 'version': r.get('release'), 'kind': r['kind']} for r in game.get('routes', [])],
        'mods': [m['name'] for m in game.get('mods', [])],
    }
    focus_text = ''
    if focus:
        v = next((v for v in game.get('versions', []) if v['id'] == focus), None)
        if v:
            focus_text = (f"\nSCHWERPUNKT: Fassung „{v['name']}“ (key {v['id']}, {', '.join(v['platforms'])}). Suche vor allem Wege, "
                          f"Erfahrungsberichte, Einstellungen und Mods für genau diese Fassung auf dem AYN Thor.\n")
    return f"""Du recherchierst für „Handheld Atlas“, einen spielzentrierten Katalog für Android-Handhelds
(Referenzgerät AYN Thor: Snapdragon 8 Gen 2, zwei Displays, Controller). Spiel: „{game['title']}“ ({', '.join(game.get('platforms', [])) or 'Plattformen unbekannt'}).
{focus_text}
Bereits bekannt (nicht wiederholen, nur ergänzen oder korrigieren): {json.dumps(known, ensure_ascii=False)}
Allgemeine Emulatoren je Plattform sind schon hinterlegt: {', '.join(sorted(platforms))} – liste sie NICHT als Spielweg,
außer es gibt spielspezifische Belege (Kompatibilität, Patches, empfohlene Einstellungen, Fork mit Dual Screen).

""" + RULES


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


IMG = re.compile(r'\.(png|jpe?g|webp|gif)(\?|$)|user-attachments/assets|user-images\.githubusercontent', re.I)


MD_CITE = re.compile(r'\s*\(\[[^\]]*\]\([^)]*\)\)')        # " ([site.com](https://…))" citation markers
MD_LINK = re.compile(r'\[([^\]]+)\]\((https?://[^)]+)\)')   # [text](url) -> text


def clean(text, limit=None):
    """Strip markdown citations/links the model sometimes puts into plain-text fields; cut at a sentence end."""
    if not isinstance(text, str):
        return text
    t = MD_LINK.sub(r'\1', MD_CITE.sub('', text))
    t = re.sub(r'\s+', ' ', t).strip()
    if limit and len(t) > limit:
        cut = max(t.rfind('. ', 0, limit), t.rfind('! ', 0, limit), t.rfind('? ', 0, limit))
        t = t[:cut + 1] if cut > limit // 3 else t[:limit].rsplit(' ', 1)[0] + ' …'
    return t


def clean_result(result):
    for key in ('summary', 'series'):
        result[key] = clean(result.get(key, ''))
    for v in result.get('versions', []):
        v['note'], v['name'] = clean(v.get('note', ''), 400), clean(v.get('name', ''))
    for r in result.get('routes', []):
        for k in ('name', 'runtime', 'dualScreen', 'benefit', 'caveat'):
            r[k] = clean(r.get(k, ''), 500)
        r['requires'] = [clean(x) for x in r.get('requires', [])]
        r['steps'] = [clean(x) for x in r.get('steps', [])]
        for rep in r.get('reports', []):
            rep['summary'] = clean(rep.get('summary', ''), 300)
    for m in result.get('mods', []):
        m['description'] = clean(m.get('description', ''), 400)
    return result


def shots_of(nr, project, credit=None):
    """Screenshots the model found for a way; linked only, checked later by ai_vision.py / the agent."""
    out = []
    for sh in nr.get('screenshots', [])[:4]:
        url = sh.get('url')
        if ok_url(url) and IMG.search(url):
            out.append({'url': url, 'caption': (sh.get('caption') or 'Screenshot')[:80], 'source': nr['sourceUrl'],
                        'credit': credit or (project or {}).get('name') or nr.get('projectName') or '', 'check': 'ai'})
    return out


def merge(game, projects, result, sources, log):
    """Apply one research result to copies; returns (game, projects, changelog entries)."""
    g, prj = copy.deepcopy(game), copy.deepcopy(projects)
    result = clean_result(copy.deepcopy(result))
    by_url = {norm_url(p['url']): p for p in prj['projects']}
    entries = []
    versions = g.setdefault('versions', [])
    vmap = {v['id']: v for v in versions}
    vname = {slug(v['name']): v for v in versions}

    added_versions = 0
    this_year = int(TODAY[:4])
    for nv in result.get('versions', []):
        if nv.get('year', 0) > this_year:
            log(f"  verworfen (noch nicht erschienen): {nv.get('name')}")
            continue
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
            for pl in nv.get('platforms', []):           # e.g. Xbox 360 / PS3 added to "Original (2011)"
                if pl not in v['platforms'] and len(v['platforms']) < 10:
                    v['platforms'].append(pl)
                    if pl not in g['platforms']:
                        g['platforms'].append(pl)
        else:
            if added_versions >= MAX_NEW_VERSIONS:
                log(f"  übersprungen (max. {MAX_NEW_VERSIONS} neue Fassungen pro Lauf): {nv['name']}")
                continue
            added_versions += 1
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
                    if not r.get('screenshots'):
                        r['screenshots'] = shots_of(nr, None, r['name'])
                        if r['screenshots']:
                            entries.append({'type': 'screenshot-added', 'text': f"Screenshots für {r['name']} (KI-Recherche)", 'url': r['screenshots'][0]['source']})
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
                 **({'dualScreenType': nr['dualScreenType']} if nr.get('dualScreenType') and 'dual-screen' in nr.get('features', []) else {}),
                 'benefit': nr.get('benefit', ''), 'caveat': nr.get('caveat', ''), 'steps': nr.get('steps', []),
                 'version': None, 'effort': nr['effort'], 'status': nr['status'], 'verification': 'ai-unverified',
                 'testedOn': [], 'screenshots': shots_of(nr, p), 'links': [{'label': 'Quelle', 'url': nr['sourceUrl']}],
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
        release = sorted({vmap[k]['id'] for k in nm.get('versionKeys', []) if k in vmap})
        mod = {'id': slug(nm['name']), 'name': nm['name'], 'category': nm.get('category') or 'other',
               'url': nm['url'], 'edition': nm.get('edition') or None,
               'description': nm.get('description', ''), 'verification': 'ai-unverified'}
        if release:
            mod['release'] = release
        while any(m['id'] == mod['id'] for m in g.get('mods', [])):
            mod['id'] += '-2'
        g.setdefault('mods', []).append(mod)
        have_mods.add(norm_url(nm['url']))
        entries.append({'type': 'mod-added', 'text': f"Neuer Mod: {nm['name']} (KI-Recherche)", 'url': nm['url']})

    series = (result.get('series') or '').strip()
    if series and (g.get('franchise') in (None, '', g['title'])) and len(series) < 80:
        g['franchise'] = series
    if result.get('summary') and not g.get('summary'):
        g['summary'] = clean(result['summary'], 300)
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


def research(game_id, token, model, log=print, focus=None):
    path = DATA / 'games' / f'{game_id}.json'
    game, projects, meta = read(path), read(DATA / 'projects.json'), read(DATA / 'meta.json')
    platforms = read(DATA / 'platforms.json')['platforms']
    resp = call_openai({'model': model, 'tools': [{'type': 'web_search', 'search_context_size': 'high'}],
                        'include': ['web_search_call.action.sources'], 'tool_choice': 'required',
                        'reasoning': {'effort': 'medium'}, 'text': {'format': schema(meta)},
                        'input': prompt(game, platforms, focus), 'max_output_tokens': 16000}, token)
    result = output_json(resp)
    g, prj, entries = merge(game, projects, result, searched_urls(resp), log)
    return apply(game_id, g, prj, entries, log)


def find_game(title):
    want = re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode().lower())
    for f in (DATA / 'games').glob('*.json'):
        g = read(f)
        if re.sub(r'[^a-z0-9]', '', unicodedata.normalize('NFKD', g['title']).encode('ascii', 'ignore').decode().lower()) == want:
            return g['id']
    return None


def create_game(title, platforms=(), franchise=None, year=None, log=print):
    """Skeleton for a game Atlas does not know yet; returns its id (existing id if the title is known)."""
    existing = find_game(title)
    if existing:
        return existing, False
    gid = slug(title)
    while (DATA / 'games' / f'{gid}.json').exists():
        gid += '-2'
    versions = [{'id': slug(p), 'name': f'{p} ({year})' if year and i == 0 else p, 'type': 'original' if i == 0 else 'release',
                 'platforms': [p], **({'year': year} if year and i == 0 else {})} for i, p in enumerate(platforms)]
    write(DATA / 'games' / f'{gid}.json', {'id': gid, 'title': title, 'franchise': franchise or title,
                                          'platforms': list(platforms), 'versions': versions, 'routes': [], 'mods': [],
                                          'updatedAt': TODAY})
    log(f'  neues Spiel angelegt: {gid}')
    return gid, True


FRANCHISE_FORMAT = {'type': 'json_schema', 'name': 'atlas_franchise', 'strict': True, 'schema': {
    'type': 'object', 'additionalProperties': False, 'required': ['games'], 'properties': {'games': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False, 'required': ['title', 'year', 'platforms', 'sourceUrl'],
        'properties': {'title': {'type': 'string'}, 'year': {'type': 'integer'}, 'platforms': {'type': 'array', 'items': {'type': 'string'}},
                       'sourceUrl': {'type': 'string'}}}}}}}


def research_franchise(name, token, model, log=print):
    """List the games of a series and create the missing ones (deep research then happens per game)."""
    known_platforms = sorted(read(DATA / 'platforms.json')['platforms'])
    resp = call_openai({'model': model, 'tools': [{'type': 'web_search', 'search_context_size': 'medium'}],
                        'include': ['web_search_call.action.sources'], 'tool_choice': 'required',
                        'reasoning': {'effort': 'low'}, 'text': {'format': FRANCHISE_FORMAT}, 'max_output_tokens': 8000,
                        'input': f"""Liste die veröffentlichten Hauptspiele, Remakes und wichtigen Ableger der Spielereihe „{name}“
(höchstens 30), jeweils Originaltitel (englisch), Erscheinungsjahr der Erstveröffentlichung, Plattformen der Erstveröffentlichung
und eine Quelle. Plattformnamen wenn möglich aus dieser Liste: {', '.join(known_platforms)}, sonst üblicher Name
(z. B. "PlayStation 4", "Xbox One", "Android"). Keine angekündigten Spiele."""}, token)
    data, sources = output_json(resp), searched_urls(resp)
    entries = []
    for item in data.get('games', [])[:30]:
        if not item.get('title') or not ok_url(item.get('sourceUrl'), sources) or item.get('year', 0) > int(TODAY[:4]):
            continue
        gid, created = create_game(item['title'], item.get('platforms', [])[:6], name, item.get('year') or None, log)
        if created:
            entries.append({'date': TODAY, 'type': 'game-added', 'by': 'ai-research', 'game': gid,
                            'text': f"Neues Spiel aus der Reihe {name}: {item['title']} (KI-Recherche)", 'url': item['sourceUrl']})
    if entries:
        problems = __import__('atlas').validate()
        if problems:
            for e in entries:
                (DATA / 'games' / f"{e['game']}.json").unlink(missing_ok=True)
            log(f'  NICHT übernommen: {problems[:3]}')
            return []
        cl = read(DATA / 'changelog.json')
        cl['entries'][0:0] = entries
        write(DATA / 'changelog.json', cl)
    # deep research for every game of the series that has not been researched yet
    queued = queue_add([g['id'] for g in franchise_games(name)], f'Reihe {name}', front=True)
    log(f'  {queued} Spiele der Reihe in die Warteschlange gestellt')
    return entries


SHOTS_FORMAT = {'type': 'json_schema', 'name': 'atlas_route_screenshots', 'strict': True, 'schema': {
    'type': 'object', 'additionalProperties': False, 'required': ['screenshots'], 'properties': {'screenshots': {
        'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['url', 'caption', 'sourceUrl'],
                                   'properties': {'url': {'type': 'string'}, 'caption': {'type': 'string'}, 'sourceUrl': {'type': 'string'}}}}}}}


# ---------------- queue: research that the owner asked for, processed in small portions ----------------
def queue_load():
    path = DATA / 'queue.json'
    return read(path) if path.exists() else {'jobs': []}


def queue_add(game_ids, reason, front=False):
    q = queue_load()
    done = read(DATA / 'inbox.json').get('aiResearch', {})
    known = {j['game'] for j in q['jobs']}
    new = []
    for gid in game_ids:
        if gid not in known and gid not in done:
            known.add(gid)
            new.append({'game': gid, 'reason': reason, 'added': TODAY})
    q['jobs'] = (new + q['jobs']) if front else (q['jobs'] + new)
    write(DATA / 'queue.json', q)
    return len(new)


def queue_pop(n):
    q = queue_load()
    jobs, q['jobs'] = q['jobs'][:n], q['jobs'][n:]
    write(DATA / 'queue.json', q)
    return jobs


def franchise_games(name):
    return sorted((read(f) for f in (DATA / 'games').glob('*.json') if read(f).get('franchise') == name),
                  key=lambda g: (min([v.get('year') or 9999 for v in g.get('versions', [])] or [9999]), g['title']))


DUAL_FORMAT = {'type': 'json_schema', 'name': 'atlas_dual_scan', 'strict': True, 'schema': {
    'type': 'object', 'additionalProperties': False, 'required': ['projects'], 'properties': {'projects': {'type': 'array', 'items': {
        'type': 'object', 'additionalProperties': False,
        'required': ['gameTitle', 'platform', 'name', 'projectUrl', 'kind', 'dualScreen', 'dualScreenType', 'sourceUrl', 'released'],
        'properties': {'gameTitle': {'type': 'string'}, 'platform': {'type': 'string'}, 'name': {'type': 'string'},
                       'projectUrl': {'type': 'string'}, 'kind': {'type': 'string', 'enum': KINDS},
                       'dualScreen': {'type': 'string'},
                       'dualScreenType': {'type': 'string', 'enum': ['integrated', 'companion', 'info', 'native']},
                       'sourceUrl': {'type': 'string'}, 'released': {'type': 'string'}}}}}}}


def dual_scan(token, model, log=print, max_new=25):
    """Find dual-screen projects for Android handhelds that Atlas does not list yet (incl. dual-screen inbox leads)."""
    known_urls = set()
    for f in (DATA / 'games').glob('*.json'):
        g = read(f)
        for r in g.get('routes', []):
            known_urls |= {norm_url(l['url']) for l in r.get('links', [])}
    projects = read(DATA / 'projects.json')
    known_urls |= {norm_url(p['url']) for p in projects['projects']}
    inbox = read(DATA / 'inbox.json')
    seen = set(inbox.get('dualScanSeen', []))
    leads = [l for l in inbox.get('leads', []) if re.search(r'dual|second.screen|zweit|two.screen|companion', f"{l['title']} {l.get('excerpt') or ''}", re.I)
             and l['url'] not in seen][:40]
    lead_list = [{'url': l['url'], 'title': l['title'], 'excerpt': (l.get('excerpt') or '')[:200]} for l in leads]
    resp = call_openai({'model': model, 'tools': [{'type': 'web_search', 'search_context_size': 'high'}],
                        'include': ['web_search_call.action.sources'], 'tool_choice': 'required', 'reasoning': {'effort': 'medium'},
                        'text': {'format': DUAL_FORMAT}, 'max_output_tokens': 12000,
                        'input': f"""Suche aktuelle Dual-Screen-Projekte für Android-Handhelds mit zwei Displays (AYN Thor u. ä.):
Mods, Companion-Apps, Emulator-Forks und native Ports, die den zweiten Bildschirm für ein bestimmtes Spiel nutzen
(Karte, Inventar, HUD, Touch-Steuerung). Besonders Neues der letzten 90 Tage (GitHub, r/SBCGaming, r/AYN, r/EmulationOnAndroid).
Prüfe zusätzlich diese Kandidaten aus unserem Watcher und nimm die echten Dual-Screen-Projekte auf:
{json.dumps(lead_list, ensure_ascii=False)}
Diese Projekte kennen wir schon (nicht erneut nennen): {json.dumps(sorted(known_urls)[:400])}
Je Projekt: gameTitle (englischer Originaltitel), platform (Plattform der Spielfassung, die es nutzt, z. B. "PC", "SNES",
"Nintendo Switch", "Android"), name, projectUrl, kind, dualScreen (deutsch: was zeigt Bildschirm 2), dualScreenType
(integrated/companion/info/native), sourceUrl, released (YYYY-MM oder ""). Keine Piraterie-Seiten. Höchstens {max_new}."""}, token)
    data, sources = output_json(resp), searched_urls(resp)
    sources |= {norm_url(l['url']) for l in leads}
    inbox['dualScanSeen'] = sorted(seen | {l['url'] for l in leads})
    added, touched_games = [], set()
    atlas_mod = __import__('atlas')
    for item in data.get('projects', [])[:max_new]:
        purl = item.get('projectUrl')
        if not ok_url(purl) or not ok_url(item.get('sourceUrl'), sources) or norm_url(purl) in known_urls:
            continue
        if len((item.get('gameTitle') or '').strip()) < 2 or not (item.get('platform') or '').strip():
            log(f"  übersprungen (Titel/Plattform fehlt): {item.get('name')}")
            continue
        # every find is applied on its own and rolled back if the database would become invalid
        existing_gid = find_game(item['gameTitle'])
        snap_game = (DATA / 'games' / f'{existing_gid}.json').read_text(encoding='utf-8') if existing_gid else None
        snap_projects = copy.deepcopy(projects)
        gid, created = create_game(item['gameTitle'], [item['platform']], None, None, log)
        g = read(DATA / 'games' / f'{gid}.json')
        version = next((v for v in g.get('versions', []) if item['platform'] in v['platforms']), None)
        if not version:
            vid = slug(item['platform'] or 'fassung')
            while any(v['id'] == vid for v in g.get('versions', [])):
                vid += '-2'
            version = {'id': vid, 'name': item['platform'], 'type': 'release', 'platforms': [item['platform']]}
            g.setdefault('versions', []).append(version)
            if item['platform'] not in g['platforms']:
                g['platforms'].append(item['platform'])
        m = re.match(r'https://github\.com/([^/]+/[^/#?]+)', purl)
        p = next((x for x in projects['projects'] if norm_url(x['url']) == norm_url(purl)), None)
        if not p:
            pid = slug(item['name'])
            while any(x['id'] == pid for x in projects['projects']):
                pid += '-2'
            p = {'id': pid, 'name': item['name'], 'kind': PROJECT_KIND.get(item['kind'], 'mod'), 'url': purl,
                 'repo': m.group(1) if m else None, 'description': item.get('dualScreen', ''), 'games': [], 'checkedAt': TODAY}
            projects['projects'].append(p)
        if gid not in p['games']:
            p['games'].append(gid)
        rid = slug('ds-' + item['name'])
        while any(r['id'] == rid for r in g.get('routes', [])):
            rid += '-2'
        g.setdefault('routes', []).append({
            'id': rid, 'name': item['name'], 'kind': item['kind'], 'release': version['id'], 'runtime': None, 'projects': [p['id']],
            'targets': ['android'], 'features': ['two-screens'] if item['dualScreenType'] == 'native' else ['dual-screen'],
            'dualScreen': item.get('dualScreen') or None, 'dualScreenType': item['dualScreenType'], 'requires': [], 'benefit': '',
            'caveat': 'Vom Dual-Screen-Suchlauf gefunden; Details folgen mit der Tiefenrecherche.', 'steps': [], 'version': None,
            'effort': 'guided', 'status': 'active', 'verification': 'ai-unverified', 'testedOn': [], 'screenshots': [],
            'links': [{'label': 'Quelle', 'url': item['sourceUrl']}], 'reports': [], 'performance': [], 'checkedAt': TODAY})
        g['updatedAt'] = TODAY
        write(DATA / 'games' / f'{gid}.json', g)
        write(DATA / 'projects.json', projects)
        problems = atlas_mod.validate()
        if problems:
            log(f"  verworfen ({item['name']} / {item['gameTitle']}): {problems[0]}")
            if created:
                (DATA / 'games' / f'{gid}.json').unlink(missing_ok=True)
            else:
                (DATA / 'games' / f'{gid}.json').write_text(snap_game, encoding='utf-8')
            projects = snap_projects
            write(DATA / 'projects.json', projects)
            continue
        known_urls.add(norm_url(purl))
        touched_games.add(gid)
        added.append({'date': TODAY, 'type': 'route-added', 'by': 'ai-research', 'game': gid,
                      'text': f"Dual Screen: {item['name']} für {g['title']} (Suchlauf)", 'url': item['sourceUrl']})
    inbox['leads'] = [l for l in inbox['leads'] if norm_url(l['url']) not in known_urls]
    inbox['dualScan'] = {'lastRun': TODAY, 'found': len(added)}
    write(DATA / 'inbox.json', inbox)
    write(DATA / 'projects.json', projects)
    problems = atlas_mod.validate()
    if problems:
        raise RuntimeError(f'Validierung nach Dual-Screen-Suchlauf fehlgeschlagen: {problems[:3]}')
    if added:
        cl = read(DATA / 'changelog.json')
        cl['entries'][0:0] = added
        write(DATA / 'changelog.json', cl)
        queue_add(sorted(touched_games), 'Dual-Screen-Suchlauf', front=True)
    return added


def routes_without_shots(limit):
    """Dual-screen and curated ways first – they matter most in the card preview."""
    found = []
    state = read(DATA / 'inbox.json').get('shotSearch', {})
    for f in sorted((DATA / 'games').glob('*.json')):
        g = read(f)
        for r in g.get('routes', []):
            if not r.get('screenshots') and state.get(f"{g['id']}/{r['id']}", '') < TODAY[:7]:   # once a month at most
                found.append(((('dual-screen' not in r.get('features', [])), r.get('verification') == 'ai-unverified', g['id']), g['id'], r['id']))
    return [(gid, rid) for _, gid, rid in sorted(found)[:limit]]


def find_screenshots(game_id, route_id, token, model, log=print):
    path = DATA / 'games' / f'{game_id}.json'
    g = read(path)
    r = next(x for x in g['routes'] if x['id'] == route_id)
    projects = {p['id']: p for p in read(DATA / 'projects.json')['projects']}
    proj = [projects[p] for p in r.get('projects', []) if p in projects]
    where = ', '.join(p['url'] for p in proj) or ', '.join(l['url'] for l in r.get('links', []))
    dual = f" Der zweite Bildschirm zeigt: {r.get('dualScreen')}. Bevorzuge Bilder, auf denen beide Bildschirme zu sehen sind." \
        if 'dual-screen' in r.get('features', []) else ''
    resp = call_openai({'model': model, 'tools': [{'type': 'web_search', 'search_context_size': 'medium'}],
                        'include': ['web_search_call.action.sources'], 'tool_choice': 'required', 'reasoning': {'effort': 'low'},
                        'text': {'format': SHOTS_FORMAT}, 'max_output_tokens': 4000,
                        'input': f"""Finde bis zu 4 direkte Bild-URLs (png/jpg/webp/gif, https), die „{g['title']}“ über den Weg
„{r['name']}“ ({r.get('runtime') or r['kind']}) auf einem Android-Gerät zeigen.{dual} Suche auf der Projektseite, in README und
Release-Notes ({where}), in Beiträgen des Autors (Reddit, Foren) und in Videos-Thumbnails nur, wenn sie das Spiel zeigen.
Keine Logos, Icons, Werbegrafiken, Stockfotos. Nur echte Bild-URLs, die in der Quelle eingebunden sind; caption auf Deutsch."""}, token)
    data, sources = output_json(resp), searched_urls(resp)
    shots = []
    for sh in data.get('screenshots', [])[:4]:
        if ok_url(sh.get('url')) and IMG.search(sh['url']) and ok_url(sh.get('sourceUrl'), sources):
            shots.append({'url': sh['url'], 'caption': (sh.get('caption') or 'Screenshot')[:80], 'source': sh['sourceUrl'],
                          'credit': proj[0]['name'] if proj else '', 'check': 'ai'})
    rejected = set((read(DATA / 'media_state.json') if (DATA / 'media_state.json').exists() else {}).get('rejectedImages', []))
    shots = [s for s in shots if s['url'] not in rejected]
    inbox = read(DATA / 'inbox.json')
    inbox.setdefault('shotSearch', {})[f'{game_id}/{route_id}'] = TODAY
    write(DATA / 'inbox.json', inbox)
    if shots:
        r['screenshots'] = shots
        write(path, g)
        if __import__('atlas').validate():
            r['screenshots'] = []
            write(path, g)
            return 0
        cl = read(DATA / 'changelog.json')
        cl['entries'].insert(0, {'date': TODAY, 'type': 'screenshot-added', 'by': 'ai-research', 'game': game_id,
                                 'text': f"{len(shots)} Screenshots für {r['name']} gefunden (KI, Prüfung folgt)", 'url': shots[0]['source']})
        write(DATA / 'changelog.json', cl)
    log(f'  {game_id}/{route_id}: {len(shots)} Bilder')
    return len(shots)


def from_app_result(game_id, result, log=print):
    """Result of an in-app instant analysis, pasted into an issue by the owner. No new API call needed."""
    game, projects = read(DATA / 'games' / f'{game_id}.json'), read(DATA / 'projects.json')
    g, prj, entries = merge(game, projects, result, None, log)
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
    ap.add_argument('--version', help='Schwerpunkt auf eine Fassung (id)')
    ap.add_argument('--new-game', help='Titel eines Spiels, das Atlas noch nicht kennt')
    ap.add_argument('--franchise', help='Reihe: fehlende Spiele anlegen')
    ap.add_argument('--screenshots', type=int, default=0, help='Bilder für N Spielwege ohne Screenshot suchen')
    ap.add_argument('--queue', type=int, default=0, help='N Spiele aus der Warteschlange recherchieren')
    ap.add_argument('--dual-scan', action='store_true', help='Dual-Screen-Suchlauf über alle Quellen')
    args = ap.parse_args()
    token = os.environ.get('OPENAI_API_KEY')
    app_payload = '```json' in (args.issue_body or '')
    if not token and not app_payload:
        print('OPENAI_API_KEY fehlt – keine KI-Recherche ausgeführt.')
        return 0
    model = os.environ.get('OPENAI_MODEL') or 'gpt-6.1-sol'
    jobs = []   # (kind, value, focus)
    if args.dual_scan:
        try:
            found = dual_scan(token, model)
            print(f'Dual-Screen-Suchlauf: {len(found)} neue Wege' + (': ' + '; '.join(e['text'] for e in found) if found else ''))
            Path(os.environ.get('RESEARCH_REPORT', '/tmp/atlas-research.md')).write_text(
                f'Dual-Screen-Suchlauf: {len(found)} neue Wege\n' + '\n'.join('- ' + e['text'] for e in found) + '\n', encoding='utf-8')
        except Exception as e:  # noqa: BLE001
            print(f'! Dual-Screen-Suchlauf: {type(e).__name__}: {str(e)[:200]}')
        args.queue = max(args.queue, 3)
    if args.screenshots:
        total = 0
        for gid, rid in routes_without_shots(args.screenshots):
            try:
                total += find_screenshots(gid, rid, token, model)
            except Exception as e:  # noqa: BLE001
                print(f'! {gid}/{rid}: {type(e).__name__}: {str(e)[:150]}')
        print(f'Bildersuche: {total} Screenshots gefunden')
        if not (args.game or args.batch or args.issue_body or args.new_game or args.franchise or args.queue):
            return 0
    if args.game:
        jobs = [('game', args.game, args.version)]
    elif args.new_game:
        jobs = [('new', args.new_game, None)]
    elif args.franchise:
        jobs = [('franchise', args.franchise, None)]
    elif args.issue_body or args.issue_title:
        body = args.issue_body or ''
        m = {k: re.search(rf'^{k}:\s*(.+)$', body, re.M | re.I) for k in ('game', 'version', 'new-game', 'franchise', 'dual-scan')}
        val = {k: v.group(1).strip() for k, v in m.items() if v}
        payload = re.search(r'```json\s*(\{.*?\})\s*```', body, re.S)
        if 'game' in val and payload:
            jobs = [('app', val['game'], json.loads(payload.group(1)))]
        elif 'new-game' in val and payload:
            jobs = [('newapp', val['new-game'], json.loads(payload.group(1)))]
        elif 'game' in val:
            jobs = [('game', val['game'], val.get('version'))]
        elif 'new-game' in val:
            jobs = [('new', val['new-game'], None)]
        elif 'franchise' in val:
            jobs = [('franchise', val['franchise'], None)]
            args.queue = max(args.queue, 3)        # start the deep research right away
        elif 'dual-scan' in val:
            args.dual_scan = True
        else:
            title = re.sub(r'^recherche:\s*', '', args.issue_title, flags=re.I).strip()
            gid = find_game(title) if title else None
            jobs = [('game', gid, None)] if gid else ([('new', title, None)] if title else [])
    elif args.batch:
        jobs = [('game', gid, None) for gid in pick_games(args.batch)]
    lines = []
    for kind, value, extra in jobs:
        try:
            if kind == 'franchise':
                print(f'Reihe: {value} ({model})')
                entries = research_franchise(value, token, model)
                lines.append(f'- Reihe **{value}**: ' + (f'{len(entries)} neue Spiele angelegt: ' + ', '.join(e["game"] for e in entries) if entries else 'keine neuen Spiele'))
                continue
            if kind in ('new', 'newapp'):
                value, created = create_game(value)
                if created:
                    lines.append(f'- Neues Spiel angelegt: `{value}`')
            if not value or not (DATA / 'games' / f'{value}.json').exists():
                lines.append(f'- `{value}`: Spiel nicht gefunden')
                continue
            if kind in ('app', 'newapp'):
                print(f'Übernahme der Sofortanalyse: {value}')
                entries = from_app_result(value, extra)
            else:
                print(f'Recherche: {value} ({model})' + (f', Fassung {extra}' if extra else ''))
                entries = research(value, token, model, focus=extra)
            if kind in ('new', 'newapp') and not entries:
                g = read(DATA / 'games' / f'{value}.json')
                if not g.get('versions') and not g.get('routes'):
                    (DATA / 'games' / f'{value}.json').unlink()
                    lines.append(f'- `{value}`: nichts Belastbares gefunden, nicht aufgenommen')
                    continue
        except Exception as e:  # noqa: BLE001 – one failing job must not stop the batch
            lines.append(f'- `{value}`: Fehler – {type(e).__name__}: {str(e)[:200]}')
            continue
        lines.append(f'- **{value}**: ' + ('; '.join(e['text'] for e in entries) if entries else 'nichts Neues gefunden'))
    for job in (queue_pop(args.queue) if args.queue else []):
        try:
            print(f"Warteschlange: {job['game']} ({job['reason']})")
            entries = research(job['game'], token, model)
            lines.append(f"- **{job['game']}** ({job['reason']}): " + ('; '.join(e['text'] for e in entries) if entries else 'nichts Neues gefunden'))
        except Exception as e:  # noqa: BLE001
            lines.append(f"- `{job['game']}`: Fehler – {type(e).__name__}: {str(e)[:200]}")
    left = len(queue_load()['jobs'])
    if args.queue:
        lines.append(f'- Warteschlange: noch {left} Spiele')
    report = '\n'.join(lines) or 'Kein Spiel ausgewählt.'
    print(report)
    if os.environ.get('GITHUB_STEP_SUMMARY'):
        Path(os.environ['GITHUB_STEP_SUMMARY']).write_text('### KI-Recherche\n\n' + report + '\n', encoding='utf-8')
    Path(os.environ.get('RESEARCH_REPORT', '/tmp/atlas-research.md')).write_text(report + '\n', encoding='utf-8')
    return 0


if __name__ == '__main__':
    sys.exit(main())
