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


def title_key(title):
    t = re.sub(r'\(.*?\)', '', unicodedata.normalize('NFKD', title or '').encode('ascii', 'ignore').decode().lower())
    return re.sub(r'^the', '', re.sub(r'[^a-z0-9]', '', t))


def game_year(g):
    m = re.search(r'\((\d{4})\)', g.get('title', ''))
    if m:
        return int(m.group(1))
    years = [v['year'] for v in g.get('versions', []) if v.get('year') and v.get('type') == 'original'] or \
            [v['year'] for v in g.get('versions', []) if v.get('year')]
    return min(years) if years else None


def find_game(title, year=None):
    """Atlas id of this game or None. With a year, a same-named game from another year (reboot: Tomb Raider 2013,
    DOOM 2016) is NOT a match, while a subtitle variant from the same year is (Doom II: Hell on Earth = DOOM II)."""
    want, base = title_key(title), title_key(re.split(r':| - ', title or '')[0])
    m = re.search(r'\((\d{4})\)', title or '')
    year = year or (int(m.group(1)) if m else None)
    subtitle_hit = None
    for f in (DATA / 'games').glob('*.json'):
        g = read(f)
        key = title_key(g['title'])
        gy = game_year(g)
        close = not year or not gy or abs(gy - year) <= 1
        if key == want and close:
            return g['id']
        if year and gy and abs(gy - year) <= 1 and key and (key == base or title_key(re.split(r':| - ', g['title'])[0]) == want):
            subtitle_hit = g['id']
    return subtitle_hit


def create_game(title, platforms=(), franchise=None, year=None, log=print):
    """Skeleton for a game Atlas does not know yet; returns its id (existing id if the title is known)."""
    existing = find_game(title, year)
    if existing:
        return existing, False
    if year and find_game(title) and not re.search(r'\(\d{4}\)', title):
        title = f'{title} ({year})'          # same name as an older game: reboot gets its year in the title
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


def franchise_format():
    vtypes = sorted(read(DATA / 'meta.json')['versionTypes'])
    return {'type': 'json_schema', 'name': 'atlas_franchise', 'strict': True, 'schema': {
        'type': 'object', 'additionalProperties': False, 'required': ['games'], 'properties': {'games': {'type': 'array', 'items': {
            'type': 'object', 'additionalProperties': False,
            'required': ['title', 'year', 'platforms', 'sourceUrl', 'relation', 'atlasId', 'versionType'],
            'properties': {'title': {'type': 'string'}, 'year': {'type': 'integer'},
                           'platforms': {'type': 'array', 'items': {'type': 'string'}}, 'sourceUrl': {'type': 'string'},
                           'relation': {'type': 'string', 'enum': ['new', 'existing', 'version']},
                           'atlasId': {'type': 'string'}, 'versionType': {'type': 'string', 'enum': vtypes}}}}}}}


def source_ok(url, sources):
    """Franchise lists: the URL itself was returned by the search, or at least its site was (list articles are
    often cited by sub-page)."""
    if ok_url(url, sources):
        return True
    host = lambda u: re.sub(r'^www\.', '', (re.match(r'https://([^/]+)', u or '') or [None, ''])[1].lower())
    return bool(ok_url(url) and sources and host(url) in {host(x) for x in sources})


def research_franchise(name, token, model, log=print):
    """List the games of a series; create missing games, add re-releases/remasters/compilations as versions of the
    game they belong to, then queue every game of the series for deep research."""
    known_platforms = sorted(read(DATA / 'platforms.json')['platforms'])
    nk = title_key(name)
    known = [g for g in (read(f) for f in (DATA / 'games').glob('*.json'))
             if g.get('franchise') == name or (len(nk) > 3 and title_key(g['title']).startswith(nk))]
    known = sorted(known, key=lambda g: (g.get('franchise') != name, g['title']))[:120]
    known_txt = '\n'.join(f"- {g['id']} | {g['title']} | {game_year(g) or '?'}" for g in known) or '- (noch keine)'
    resp = call_openai({'model': model, 'tools': [{'type': 'web_search', 'search_context_size': 'high'}],
                        'include': ['web_search_call.action.sources'], 'tool_choice': 'required',
                        'reasoning': {'effort': 'medium'}, 'text': {'format': franchise_format()}, 'max_output_tokens': 12000,
                        'input': f"""Liste ALLE veröffentlichten Spiele der Spielereihe „{name}“ vollständig (höchstens 45): Hauptteile,
Ableger, Mobile-Spiele, Reboots, Remakes, Remaster, Neuauflagen und Sammlungen. Je Eintrag: Originaltitel (englisch),
Jahr der Erstveröffentlichung, Plattformen der Erstveröffentlichung, eine Quelle (am besten die Wikipedia-Liste der Reihe
oder der Artikel des Spiels, die du über die Websuche geöffnet hast). Keine angekündigten Spiele.

Atlas kennt bereits (id | Titel | Jahr):
{known_txt}

relation + atlasId:
- "existing": dasselbe Spiel steht schon oben (auch unter anderem Namen, z. B. "Doom II: Hell on Earth" = "DOOM II") → atlasId = dessen id.
- "version": Remaster, Remake mit gleichem Namen, Neuauflage, Portierung oder Sammlung eines Spiels oben
  (z. B. "Tomb Raider: Anniversary" → tomb-raider, "DOOM + DOOM II" (2024) → doom-1993) → atlasId = id des Spiels,
  zu dem es als Fassung gehört; versionType passend (remaster/remake/rerelease/port/collection).
- "new": eigenständiges Spiel, das oben fehlt; atlasId = "". Reboots mit gleichem Namen sind eigene Spiele: Titel mit
  Jahr, z. B. "DOOM (2016)", "Tomb Raider (2013)". versionType = "original".
Plattformnamen wenn möglich aus dieser Liste: {', '.join(known_platforms)}, sonst üblicher Name (z. B. "PlayStation 4")."""}, token)
    data, sources = output_json(resp), searched_urls(resp)
    ids = {g['id'] for g in known}
    entries, report = [], {'date': TODAY, 'listed': len(data.get('games', [])), 'added': [], 'versions': [], 'skipped': []}
    for item in data.get('games', [])[:45]:
        title = (item.get('title') or '').strip()
        why = ('kein Titel' if not title else 'Quelle nicht aus der Websuche' if not source_ok(item.get('sourceUrl'), sources)
               else 'noch nicht erschienen' if item.get('year', 0) > int(TODAY[:4]) else None)
        if why:
            report['skipped'].append({'title': title, 'reason': why})
            log(f'  übersprungen ({why}): {title}')
            continue
        target = item.get('atlasId') if item.get('atlasId') in ids else None
        if item.get('relation') == 'version' and target:
            path = DATA / 'games' / f'{target}.json'
            g = read(path)
            if any(title_key(v['name']).startswith(title_key(title)) or (v.get('year') == item.get('year') and
                   v.get('type') == item.get('versionType')) for v in g.get('versions', [])):
                continue
            plats = [p for p in item.get('platforms', [])[:8] if p]
            vid = slug(title if title_key(title) != title_key(g['title']) else f"{'-'.join(plats[:2])}-{item['year']}")[:40]
            while any(v['id'] == vid for v in g.get('versions', [])):
                vid += '-2'
            vname = title if title_key(title) != title_key(g['title']) else ', '.join(plats or ['Fassung'])   # "DOOM 3" → "Xbox"
            g.setdefault('versions', []).append({'id': vid, 'name': f"{vname} ({item['year']})", 'type': item.get('versionType') or 'rerelease',
                                                 'year': item['year'], 'platforms': plats or g.get('platforms', [])[:1],
                                                 'links': [{'label': 'Quelle', 'url': item['sourceUrl']}]})
            g['platforms'] += [p for p in plats if p not in g['platforms']]
            write(path, g)
            report['versions'].append(f'{target}: {title}')
            entries.append({'date': TODAY, 'type': 'route-updated', 'by': 'ai-research', 'game': target,
                            'text': f"Neue Fassung aus der Reihen-Analyse: {title} ({item['year']})", 'url': item['sourceUrl']})
            continue
        if item.get('relation') == 'existing' and target:
            continue
        gid, created = create_game(title, item.get('platforms', [])[:6], name, item.get('year') or None, log)
        if created:
            ids.add(gid)
            report['added'].append(gid)
            entries.append({'date': TODAY, 'type': 'game-added', 'by': 'ai-research', 'game': gid,
                            'text': f"Neues Spiel aus der Reihe {name}: {title} (KI-Recherche)", 'url': item['sourceUrl']})
    if entries:
        problems = __import__('atlas').validate()
        if problems:
            for e in entries:
                if e['type'] == 'game-added':
                    (DATA / 'games' / f"{e['game']}.json").unlink(missing_ok=True)
            log(f'  NICHT übernommen: {problems[:3]}')
            return []
        cl = read(DATA / 'changelog.json')
        cl['entries'][0:0] = entries
        write(DATA / 'changelog.json', cl)
    inbox = read(DATA / 'inbox.json')
    inbox.setdefault('franchiseScan', {})[name] = report
    write(DATA / 'inbox.json', inbox)
    log(f"  Reihe {name}: {report['listed']} Titel gelistet, {len(report['added'])} neu, {len(report['versions'])} Fassungen, "
        f"{len(report['skipped'])} übersprungen")
    # deep research for every game of the series that has not been researched yet (new ones first)
    order = report['added'] + [g['id'] for g in franchise_games(name) if g['id'] not in report['added']]
    queued = queue_add(order, f'Reihe {name}', front=True)
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
Je Projekt und Spiel ein Eintrag (unterstützt ein Projekt mehrere Spiele, mehrere Einträge): gameTitle (genau EIN englischer Originaltitel), platform (Plattform der Spielfassung, die es nutzt, z. B. "PC", "SNES",
"Nintendo Switch", "Android"), name, projectUrl, kind, dualScreen (deutsch: was zeigt Bildschirm 2), dualScreenType
(integrated/companion/info/native), sourceUrl, released (YYYY-MM oder ""). Keine Piraterie-Seiten. Höchstens {max_new}."""}, token)
    data, sources = output_json(resp), searched_urls(resp)
    sources |= {norm_url(l['url']) for l in leads}
    inbox['dualScanSeen'] = sorted(seen | {l['url'] for l in leads})
    added, touched_games = [], set()
    atlas_mod = __import__('atlas')
    items = []
    for item in data.get('projects', [])[:max_new]:
        # one project for several games ("A; B; C") -> one entry per game
        titles = [t.strip() for t in re.split(r'\s*;\s*|\s+\|\s+', item.get('gameTitle') or '') if t.strip()]
        items += [{**item, 'gameTitle': t} for t in titles] or [item]
    known_before, batch_seen = set(known_urls), set()
    for item in items:
        purl = item.get('projectUrl')
        pair = (norm_url(purl), (item.get('gameTitle') or '').lower())
        if not ok_url(purl) or not ok_url(item.get('sourceUrl'), sources) or norm_url(purl) in known_before or pair in batch_seen:
            continue
        batch_seen.add(pair)
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
                 'repo': m.group(1) if m else None, 'description': clean(item.get('dualScreen', ''), 300), 'games': [], 'checkedAt': TODAY}
            projects['projects'].append(p)
        if gid not in p['games']:
            p['games'].append(gid)
        rid = slug('ds-' + item['name'])
        while any(r['id'] == rid for r in g.get('routes', [])):
            rid += '-2'
        g.setdefault('routes', []).append({
            'id': rid, 'name': item['name'], 'kind': item['kind'], 'release': version['id'], 'runtime': None, 'projects': [p['id']],
            'targets': ['android'], 'features': ['two-screens'] if item['dualScreenType'] == 'native' else ['dual-screen'],
            'dualScreen': clean(item.get('dualScreen'), 300) or None, 'dualScreenType': item['dualScreenType'], 'requires': [], 'benefit': '',
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


PAGES_FORMAT = {'type': 'json_schema', 'name': 'atlas_image_pages', 'strict': True, 'schema': {
    'type': 'object', 'additionalProperties': False, 'required': ['pages'], 'properties': {'pages': {
        'type': 'array', 'items': {'type': 'object', 'additionalProperties': False, 'required': ['url', 'shows'],
                                   'properties': {'url': {'type': 'string'}, 'shows': {'type': 'string'}}}}}}}
MAX_SHOTS = 6
reachable = None    # image URL check; set lazily (tests replace it)


def _reachable(url):
    global reachable
    if reachable is None:
        from ai_vision import reachable_image
        reachable = reachable_image
    return reachable(url)


def rejected_images():
    return set((read(DATA / 'media_state.json') if (DATA / 'media_state.json').exists() else {}).get('rejectedImages', []))


def ask_pages(text, token, model):
    """The model names pages (videos, posts, READMEs, store pages) – it finds those reliably, unlike image URLs."""
    resp = call_openai({'model': model, 'tools': [{'type': 'web_search', 'search_context_size': 'medium'}],
                        'include': ['web_search_call.action.sources'], 'tool_choice': 'required', 'reasoning': {'effort': 'low'},
                        'text': {'format': PAGES_FORMAT}, 'max_output_tokens': 3000, 'input': text}, token)
    data, sources = output_json(resp), searched_urls(resp)
    return [p['url'] for p in data.get('pages', [])[:8] if ok_url(p.get('url'), sources)]


def collect(pages, have, limit, log=print, fetch=None, fetch_json=None):
    """Pictures from the pages, in page order; dead links, rejected and known pictures are skipped."""
    import images
    fetch = fetch or images.get
    rejected, out = rejected_images(), []
    for page in dict.fromkeys(pages):
        for sh in images.images_from_page(page, fetch, fetch_json, log):
            if len(out) >= limit:
                return out
            url = sh['url']
            if url in rejected or not ok_url(url) or any(images.same_image(url, x) for x in list(have) + [o['url'] for o in out]):
                continue
            if '/maxresdefault.jpg' in url and not _reachable(url):
                url = url.replace('/maxresdefault.jpg', '/hqdefault.jpg')        # older/low-res videos
            if not _reachable(url):
                continue
            out.append(dict(sh, url=url))
    return out


def route_pages(g, r, projects):
    """Pages that certainly belong to this way: its project pages and links (no AI needed)."""
    pages = []
    for pid in r.get('projects', []):
        p = projects.get(pid) or {}
        if p.get('kind') in ('emulator', 'directory', 'data-source', 'runtime') or len(p.get('games', [])) > 3:
            continue              # a generic emulator page says nothing about this game
        pages.append(p.get('url'))
    pages += [l['url'] for l in r.get('links', [])]
    return [x for x in pages if x and x.startswith('https://')]


def route_candidates(g, r, token, model, log=print):
    """Pictures for one way: known project pages first, then pages the AI found (videos, posts, articles)."""
    projects = {p['id']: p for p in read(DATA / 'projects.json')['projects']}
    have = {x['url'] for x in r.get('screenshots', [])}
    room = MAX_SHOTS - len(have)
    if room <= 0:
        return []
    found = collect(route_pages(g, r, projects), have, room, log)
    dual = 'dual-screen' in r.get('features', []) or 'two-screens' in r.get('features', [])
    if token and len(found) < (3 if dual else 2):
        proj = [projects[p] for p in r.get('projects', []) if p in projects]
        where = ', '.join(p['url'] for p in proj) or ', '.join(l['url'] for l in r.get('links', []))
        wish = (f" Wichtig: Der zweite Bildschirm zeigt {r.get('dualScreen') or 'Zusatzinhalte'} – bevorzuge Videos und Fotos, "
                "auf denen BEIDE Bildschirme des Geräts (z. B. AYN Thor, Ayaneo Flip DS, Dual-Screen-Handheld) zu sehen sind.") if dual else ''
        pages = ask_pages(f"""Finde bis zu 6 Seiten, auf denen man sieht, wie „{g['title']}“ über den Weg „{r['name']}“
({r.get('runtime') or r.get('kind')}) auf einem Android-Gerät oder Handheld aussieht.{wish}
Gute Seiten: YouTube-Videos oder Shorts (am besten), GitHub-README oder Release-Seiten, Projekt- oder Store-Seiten
(Google Play), Artikel und Blogbeiträge mit Screenshots. Reddit nur, wenn es nichts anderes gibt (oft nicht abrufbar). Projekt: {where or '–'}.
url = genau die Seite, die du über die Websuche geöffnet hast; shows = was darauf zu sehen ist (kurz, deutsch).""", token, model)
        found += collect(pages, have | {x['url'] for x in found}, room - len(found), log)
    cap = r['name'] + (' (Dual Screen)' if dual else '')
    return [{'url': x['url'], 'caption': clean(x.get('caption') or cap, 80) or cap, 'source': x['source'],
             'credit': x['source'].split('/')[2].replace('www.', ''), 'check': 'ai'} for x in found]


def apply_route_shots(game_id, route_id, shots, log=print):
    path = DATA / 'games' / f'{game_id}.json'
    g = read(path)
    r = next((x for x in g['routes'] if x['id'] == route_id), None)
    if r is None:
        return 0
    inbox = read(DATA / 'inbox.json')
    inbox.setdefault('shotSearch', {})[f'{game_id}/{route_id}'] = TODAY
    write(DATA / 'inbox.json', inbox)
    before = list(r.get('screenshots', []))
    have = {x['url'] for x in before}
    shots = [x for x in shots if x['url'] not in have]
    if not shots:
        log(f'  {game_id}/{route_id}: keine neuen Bilder')
        return 0
    r['screenshots'] = (before + shots)[:MAX_SHOTS]
    write(path, g)
    if __import__('atlas').validate():
        r['screenshots'] = before
        write(path, g)
        return 0
    cl = read(DATA / 'changelog.json')
    cl['entries'].insert(0, {'date': TODAY, 'type': 'screenshot-added', 'by': 'ai-research', 'game': game_id,
                             'text': f"{len(shots)} Bilder für {r['name']} gefunden (Prüfung folgt)", 'url': shots[0]['source']})
    write(DATA / 'changelog.json', cl)
    log(f'  {game_id}/{route_id}: {len(shots)} Bilder')
    return len(shots)


def find_screenshots(game_id, route_id, token, model, log=print):
    g = read(DATA / 'games' / f'{game_id}.json')
    r = next(x for x in g['routes'] if x['id'] == route_id)
    return apply_route_shots(game_id, route_id, route_candidates(g, r, token, model, log), log)


def original_shots(g):
    return [x for x in g.get('screenshots', []) if x.get('caption') != 'Titelbild']


def game_candidates(g, token, model, log=print):
    """Original-game pictures: Wikipedia article and Steam first (no AI), then store pages/videos the AI finds."""
    import images
    import media
    have = {x['url'] for x in g.get('screenshots', [])} | {(g.get('cover') or {}).get('url')}
    room = MAX_SHOTS - len(original_shots(g))
    if room <= 0:
        return []
    pages = []
    src = (g.get('cover') or {}).get('source', '')
    if '.wikipedia.org/wiki/' in src:
        pages.append(src)
    else:                                     # find the article even if the cover came from elsewhere
        try:
            _, wiki = media.wikipedia_cover(g['title'], images.get)
            if wiki:
                pages.append(wiki)
        except Exception as e:  # noqa: BLE001
            log(f'    ! Wikipedia {g["title"]}: {e}')
    if 'PC' in g.get('platforms', []):
        try:
            appid = media.steam_lookup(re.sub(r'\s*\(\d{4}\)$', '', g['title']), images.get)
            if appid:
                pages.append(f'https://store.steampowered.com/app/{appid}/')
        except Exception as e:  # noqa: BLE001
            log(f'    ! Steam {g["title"]}: {e}')
    found = collect(pages, have, room, log)
    if token and len(found) < 3:
        vers = '; '.join(f"{v['name']} ({', '.join(v['platforms'][:3])})" for v in g.get('versions', [])[:8])
        ai = ask_pages(f"""Finde bis zu 6 Seiten mit echten Spielszenen (Screenshots oder Gameplay-Video) von „{g['title']}“
(Fassungen: {vers or ', '.join(g.get('platforms', []))}). Gute Seiten: YouTube-Gameplay-Videos (Longplay, Trailer – je Fassung eins),
offizielle Shop-Seiten (Steam, Google Play), der Wikipedia-Artikel, offizielle Herstellerseite, Testberichte mit Screenshots.
Keine MobyGames-, GameFAQs- oder Reddit-Seiten (für uns nicht abrufbar). url = genau die Seite, die du über die Websuche geöffnet hast; shows = was zu sehen ist.""", token, model)
        found += collect(ai, have | {x['url'] for x in found}, room - len(found), log)
    return [{'url': x['url'], 'caption': clean(x.get('caption') or 'Originalspiel', 80) or 'Originalspiel',
             'source': x['source'], 'check': 'ai'} for x in found]


def find_game_images(game_id, token, model, log=print):
    path = DATA / 'games' / f'{game_id}.json'
    g = read(path)
    new = game_candidates(g, token, model, log)
    g = read(path)
    have = {x['url'] for x in g.get('screenshots', [])}
    new = [x for x in new if x['url'] not in have]
    if not new:
        log(f'  {game_id}: keine neuen Originalbilder gefunden')
        return 0
    before = path.read_text(encoding='utf-8')
    g['screenshots'] = g.get('screenshots', []) + new
    write(path, g)
    if __import__('atlas').validate():
        path.write_text(before, encoding='utf-8')
        return 0
    log(f'  {game_id}: {len(new)} Originalbilder (Prüfung folgt)')
    return len(new)


def images_basic(game_ids, log=print):
    """Free sources first (no AI): libretro-thumbnails, project READMEs/releases, Steam, Wikipedia."""
    import covers
    import media
    only = set(game_ids)
    for name, fn in (('libretro', lambda: covers.main(only=only)), ('README', lambda: media.fill_route_shots(only=only)),
                     ('Steam', lambda: media.fill_steam(pause=0.3, only=only)),
                     ('Wikipedia', lambda: media.fill_wikipedia(pause=0.5, only=only))):
        try:
            fn()
        except Exception as e:  # noqa: BLE001 – one source failing must not stop the others
            log(f'  ! Bilder {name}: {type(e).__name__}: {str(e)[:120]}')


def request_images(game_ids, token, model, log=print, max_routes=16, routes=None):
    """Owner asked for pictures (button in the app). Free sources first, then the page search for whatever is still
    thin – original game and every way with fewer than 3 pictures (dual screen first). Searches run in parallel."""
    from concurrent.futures import ThreadPoolExecutor
    images_basic(game_ids, log)
    stats = {'games': 0, 'routes': 0}
    tasks = []
    for gid in game_ids:
        g = read(DATA / 'games' / f'{gid}.json')
        if routes is None and len(original_shots(g)) < 3:
            tasks.append(('game', gid, None))
        todo = [r for r in g.get('routes', []) if (routes is not None and r['id'] in routes)
                or (routes is None and len(r.get('screenshots', [])) < 3)]
        todo.sort(key=lambda r: not ({'dual-screen', 'two-screens'} & set(r.get('features', []))))
        tasks += [('route', gid, r['id']) for r in todo]
    tasks = [t for t in tasks if t[0] == 'game'] + [t for t in tasks if t[0] == 'route'][:max_routes]

    def run(task):
        kind, gid, rid = task
        g = read(DATA / 'games' / f'{gid}.json')
        try:
            if kind == 'game':
                return task, game_candidates(g, token, model, log)
            r = next(x for x in g['routes'] if x['id'] == rid)
            return task, route_candidates(g, r, token, model, log)
        except Exception as e:  # noqa: BLE001
            log(f'  ! {gid}/{rid or "original"}: {type(e).__name__}: {str(e)[:120]}')
            return task, []
    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(run, tasks))
    for (kind, gid, rid), shots in results:        # writing stays sequential
        if kind == 'game':
            path = DATA / 'games' / f'{gid}.json'
            g = read(path)
            have = {x['url'] for x in g.get('screenshots', [])}
            new = [x for x in shots if x['url'] not in have]
            if new:
                g['screenshots'] = g.get('screenshots', []) + new
                write(path, g)
                if __import__('atlas').validate():
                    g['screenshots'] = [x for x in g['screenshots'] if x not in new]
                    write(path, g)
                else:
                    stats['games'] += len(new)
                    log(f'  {gid}: {len(new)} Originalbilder (Prüfung folgt)')
            else:
                log(f'  {gid}: keine neuen Originalbilder')
        else:
            stats['routes'] += apply_route_shots(gid, rid, shots, log)
    inbox = read(DATA / 'inbox.json')
    for gid in game_ids:
        inbox.setdefault('imageRequests', {})[gid] = TODAY
    write(DATA / 'inbox.json', inbox)
    return stats


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
    ap.add_argument('--images', help='Bilder für diese Spiele suchen (ids, durch Komma getrennt)')
    args = ap.parse_args()
    token = os.environ.get('OPENAI_API_KEY')
    app_payload = '```json' in (args.issue_body or '')
    if not token and not app_payload:
        print('OPENAI_API_KEY fehlt – keine KI-Recherche ausgeführt.')
        return 0
    model = os.environ.get('OPENAI_MODEL') or 'gpt-6.1-sol'
    jobs = []   # (kind, value, focus)
    images = []   # game ids whose pictures were requested
    image_routes = None
    if args.game:
        jobs = [('game', args.game, args.version)]
    elif args.new_game:
        jobs = [('new', args.new_game, None)]
    elif args.franchise:
        jobs = [('franchise', args.franchise, None)]
    elif args.images:
        images = [x.strip() for x in args.images.split(',') if x.strip()]
    elif args.issue_body or args.issue_title:
        body = args.issue_body or ''
        keys = ('game', 'version', 'new-game', 'franchise', 'dual-scan', 'images', 'images-franchise')
        m = {k: re.search(rf'^{k}:\s*(.+)$', body, re.M | re.I) for k in keys}
        val = {k: v.group(1).strip() for k, v in m.items() if v}
        payload = re.search(r'```json\s*(\{.*?\})\s*```', body, re.S)
        if 'images' in val:
            images = [x.strip() for x in val['images'].split(',') if x.strip()]
            if len(images) == 1 and '/' in images[0]:          # one way only: "images: game/route"
                images, image_routes = [images[0].split('/')[0]], [images[0].split('/', 1)[1]]
        elif 'images-franchise' in val:
            images = [g['id'] for g in franchise_games(val['images-franchise'])][:25]
        elif 'game' in val and payload:
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
    if args.dual_scan:
        try:
            found = dual_scan(token, model)
            lines.append(f'- Dual-Screen-Suchlauf: {len(found)} neue Wege' + ''.join('\n  - ' + e['text'] for e in found))
        except Exception as e:  # noqa: BLE001
            lines.append(f'- Dual-Screen-Suchlauf: Fehler – {type(e).__name__}: {str(e)[:200]}')
        args.queue = max(args.queue, 3)
    if args.screenshots:
        total = 0
        for gid, rid in routes_without_shots(args.screenshots):
            try:
                total += find_screenshots(gid, rid, token, model)
            except Exception as e:  # noqa: BLE001
                print(f'! {gid}/{rid}: {type(e).__name__}: {str(e)[:150]}')
        lines.append(f'- Bildersuche: {total} Screenshots für Spielwege gefunden')
    if images:
        images = [gid for gid in images if (DATA / 'games' / f'{gid}.json').exists()]
        print(f"Bilder angefordert: {', '.join(images)}")
        st = request_images(images, token, model, routes=image_routes)
        lines.append(f"- Bilder für {', '.join(images)}{' / ' + image_routes[0] if image_routes else ''}: {st['games']} Originalbilder "
                     f"und {st['routes']} Spielweg-Bilder neu (aus Wikipedia, Steam, Google Play, YouTube, Reddit, GitHub, "
                     "Projektseiten; dazu libretro-thumbnails). Die KI-Bildprüfung sortiert danach Unpassendes aus.")
    researched = set()
    for kind, value, extra in jobs:
        try:
            if kind == 'franchise':
                print(f'Reihe: {value} ({model})')
                entries = research_franchise(value, token, model)
                rep = read(DATA / 'inbox.json').get('franchiseScan', {}).get(value, {})
                lines.append(f"- Reihe **{value}**: {rep.get('listed', 0)} Titel gefunden, {len(rep.get('added', []))} neue Spiele"
                             + (f" ({', '.join(rep['added'])})" if rep.get('added') else '')
                             + f", {len(rep.get('versions', []))} Fassungen ergänzt"
                             + (f"; übersprungen: {', '.join(x['title'] + ' (' + x['reason'] + ')' for x in rep['skipped'])}" if rep.get('skipped') else ''))
                researched.update(rep.get('added', []))
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
        researched.add(value)
        lines.append(f'- **{value}**: ' + ('; '.join(e['text'] for e in entries) if entries else 'nichts Neues gefunden'))
    for job in (queue_pop(args.queue) if args.queue else []):
        try:
            print(f"Warteschlange: {job['game']} ({job['reason']})")
            entries = research(job['game'], token, model)
            researched.add(job['game'])
            lines.append(f"- **{job['game']}** ({job['reason']}): " + ('; '.join(e['text'] for e in entries) if entries else 'nichts Neues gefunden'))
        except Exception as e:  # noqa: BLE001
            lines.append(f"- `{job['game']}`: Fehler – {type(e).__name__}: {str(e)[:200]}")
    # new or freshly researched games get covers/pictures from the free sources right away, not only tomorrow
    researched = sorted(g for g in researched if g and (DATA / 'games' / f'{g}.json').exists())
    if researched:
        images_basic(researched)
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
