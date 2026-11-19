#!/usr/bin/env python3
"""Handheld Atlas: data rules that keep the catalogue tidy without manual work (run by `atlas.py repair`).

    python3 scripts/quality.py            # same as `atlas.py check`: list what still needs a human/agent decision

Automatic (repair):
- One version per playable platform: a version that lists several platforms with different ways to play them
  (PS2 → NetherSX2, GameCube → Dolphin, PC → GameNative …) is split into one version per platform. Platforms
  without an Android emulator (PS4, PS5, Xbox One …) stay together. Routes, mods and community reports go with the
  platform they belong to.
- Remake re-releases: a version of an original whose name carries the remake's distinctive title
  ("Tomb Raider: Anniversary – PS4/PS5" at Tomb Raider) moves to the remake; a collection the remake already lists
  ("The Tomb Raider Trilogy") is dropped from the original.

Checks (`atlas.py check`): remake suspects without "remakeOf", remasters that are described as rebuilt, versions that
still mix playable platforms, platform names Atlas does not know.
Standard library only.
"""
import re
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import atlas  # noqa: E402
from atlas import canon_platforms, read, write  # noqa: E402

TODAY = datetime.now(timezone.utc).strftime('%Y-%m-%d')
PC_RUNTIME = re.compile(r'gamenative|winlator|gamehub|game hub|droiddeck|mobox|exagear|cassia|wine|box64|proton', re.I)
PC_MOD_HOSTS = re.compile(r'nexusmods\.com|moddb\.com|steamcommunity\.com|pcgamingwiki\.com', re.I)
SHORT = {'PlayStation': ['PS1', 'PSX', 'PSone'], 'PlayStation 2': ['PS2'], 'PlayStation 3': ['PS3'], 'PlayStation 4': ['PS4'],
         'PlayStation 5': ['PS5'], 'PlayStation Vita': ['PS Vita', 'Vita'], 'PSP': ['PlayStation Portable'],
         'Nintendo GameCube': ['GameCube', 'GCN', 'NGC'], 'Nintendo Switch': ['Switch'], 'Nintendo 64': ['N64'],
         'Nintendo DS': ['NDS'], 'Nintendo 3DS': ['3DS'], 'Game Boy Advance': ['GBA'], 'Xbox 360': ['X360'],
         'Xbox': ['Original Xbox'], 'Sega Mega Drive': ['Mega Drive', 'Genesis'], 'Dreamcast': ['DC'], 'Java ME': ['J2ME', 'Handy'],
         'Macintosh': ['Mac', 'macOS', 'Mac OS', 'Apple Macintosh'], 'Nokia N-Gage': ['N-Gage'], 'Xbox One': ['XB1', 'XONE'],
         'Xbox Series': ['Xbox Series X', 'Xbox Series S', 'XSX', 'Series X'], 'Nintendo Switch 2': ['Switch 2'],
         'Android': ['Google Play'], 'Sega Saturn': ['Saturn'], 'Sega Mega Drive': ['Mega Drive', 'Genesis'], 'iOS': ['iPhone', 'iPad', 'App Store'], 'Linux': ['SteamOS', 'Steam Deck']}
# words that are left over from platform lists ("PC, PS3/4, Xbox 360/One") – such a name is generic
LEFTOVER = re.compile(r'(?i)^(?:\d{1,3}|one|series|x|s|xl|classic|konsolen?|consoles?|mobiltelefone?|handys?|mobile|smartphones?|'
                      r'heimcomputer|computer|plattformen|systeme|weitere|alle|gleichzeitig|zeitgleich|multi|multiplattform)$')


def slug(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', '-', s).strip('-')[:40]


def playable():
    """Platforms with their own Android emulator(s) in platforms.json → {platform: {project ids}}."""
    return {p: {o['project'] for o in lst} for p, lst in read(atlas.DATA / 'platforms.json')['platforms'].items()}


# ---------------- one version per playable platform ----------------
def group_of(platform, plays):
    if platform in plays or platform == 'PC':
        return platform
    if platform in ('Android', 'iOS'):
        return 'mobile'
    return 'other'


def groups_of(v, plays):
    out = {}
    for p in v.get('platforms', []):
        out.setdefault(group_of(p, plays), []).append(p)
    return out


def needs_split(v, plays):
    if v.get('type') == 'android':
        return False
    groups = groups_of(v, plays)
    return len([k for k in groups if k not in ('other', 'mobile')]) + (1 if set(groups) & {'other', 'mobile'} else 0) > 1


def _platform_words(plats):
    words = []
    for p in plats:
        words += [p, *SHORT.get(p, [])]
    return sorted(set(words), key=len, reverse=True)


def core_name(v):
    """Version name without its platforms and year: "Skyrim Special Edition für PC" → "Skyrim Special Edition",
    "PC/PS2/Xbox/GameCube (2004)" → "" (generic)."""
    name = v.get('name') or ''
    name = re.sub(r'\s*\((?:19|20)\d\d\)\s*', ' ', name)
    name = re.sub(r',?\s*\b(?:19|20)\d\d\b(?=[^()]*\))', '', name)        # "(PS3/PSP, 2009)"
    for w in _platform_words(v.get('platforms', [])):
        # "Nintendo Switch Online", "PlayStation Classic": the platform is part of a product name and stays
        name = re.sub(r'(?:\b(?:für|auf|on|for)\s+)?(?<![\w-])' + re.escape(w)
                      + r'(?![\w-])(?!\s+(?:Online|Classic|Mini|Arcade|Network|Store|Shop|Live)\b)', '§', name, flags=re.I)
    sep = r'(?:[,/&+]|\bund\b|\band\b|u\.\s*a\.)'
    name = re.sub(r'(?:\s*' + sep + r'?\s*§)+(?:\s*' + sep + r'(?=\s*(?:\)|$)))?', ' ', name)
    name = re.sub(r'\(\s*[,/&+–-]*\s*\)', ' ', name)
    name = re.sub(r'\s+[–-]\s*$|^\s*[–-]\s+', '', name.strip())
    name = re.sub(r'\s{2,}', ' ', name).strip(' –-:,')
    if all(LEFTOVER.match(w) for w in re.findall(r'[\w’\'-]+', name)):
        return ''
    return '' if re.fullmatch(r'(?i)(original|fassung|release|portierung|port|veröffentlichung|konsolen?|erstveröffentlichung)?', name) else name


def platform_label(plats):
    return ', '.join(plats)


def split_name(v, plats, generic_ok=True):
    core = core_name(v)
    year = v.get('year')
    label = platform_label(plats)
    if not core:
        return f'{label} ({year})' if year else label
    return f'{core} – {label}' + (f' ({year})' if year else '')


def route_group(r, groups, plays, projects):
    """Which platform of a split version a route plays."""
    pids = set(r.get('projects') or [])
    text = ' '.join(str(r.get(k) or '') for k in ('name', 'edition', 'runtime'))
    for key in groups:
        if key in plays and pids & plays[key]:
            return key
    if 'PC' in groups and (r.get('kind') == 'pc-runtime' or PC_RUNTIME.search(text)
                           or any(PC_RUNTIME.search(projects.get(p, {}).get('name', '')) for p in pids)):
        return 'PC'
    for key, plats in groups.items():
        for w in _platform_words(plats):
            if re.search(r'(?<!\w)' + re.escape(w) + r'(?!\w)', text, re.I):     # also "Android-App", "PS2-Fassung"
                return key
    for key in groups:                                   # emulator named in the text ("Dolphin", "NetherSX2")
        for pid in plays.get(key, ()):
            name = projects.get(pid, {}).get('name')
            if name and re.search(r'\b' + re.escape(name) + r'\b', text, re.I):
                return key
    return None


def report_group(rep, groups, plays, projects):
    emu = (rep.get('emulator') or '').lower()
    if not emu:
        return None
    if 'PC' in groups and PC_RUNTIME.search(emu):
        return 'PC'
    for key in groups:
        for pid in plays.get(key, ()):
            name = (projects.get(pid, {}).get('name') or '').lower()
            if name and (name in emu or emu in name):
                return key
    return None


LINK_PLATFORM = [(re.compile(r'pcsx2|aethersx2|nethersx2', re.I), 'PlayStation 2'), (re.compile(r'dolphin-emu|dolphin', re.I), 'Nintendo GameCube'),
                 (re.compile(r'pcgamingwiki|steampowered|gog\.com|nexusmods', re.I), 'PC'), (re.compile(r'duckstation', re.I), 'PlayStation'),
                 (re.compile(r'ppsspp', re.I), 'PSP'), (re.compile(r'xenia', re.I), 'Xbox 360'), (re.compile(r'cemu', re.I), 'Wii U')]


def link_group(link, groups, first):
    """Which part of a split version a link belongs to (None = all): EmuReady stays with the first, a PCSX2 wiki page goes
    to the PS2 version, a PCGamingWiki page to the PC version."""
    if link.get('label') == 'EmuReady':
        return first
    text = f"{link.get('label', '')} {link.get('url', '')}"
    for rx, plat in LINK_PLATFORM:
        if rx.search(text):
            if plat in groups:
                return plat
            if plat == 'Nintendo GameCube' and 'Wii' in groups:
                return 'Wii'
    return None


def note_group(note, groups, first):
    """A note stays with the platform it talks about, otherwise with the first platform – not copied to every part."""
    if not note:
        return first
    hit = link_group({'label': note}, groups, None)
    if hit:
        return hit
    for k, plats in groups.items():
        if any(re.search(r'(?<!\w)' + re.escape(w) + r'(?!\w)', note, re.I) for w in _platform_words(plats)):
            return k
    return first


def dedupe_split_notes(log=print):
    """Clean-up for versions split before notes were assigned: identical notes and platform-wiki links on the parts of
    one split version are kept only where they belong."""
    plays = playable()
    fixed = 0
    for f in sorted(atlas.DATA.glob('games/*.json')):
        g = read(f)
        changed = False
        vs = g.get('versions', [])
        for base in vs:
            parts = [x for x in vs if x is not base and x['id'].startswith(base['id'] + '-') and x.get('type') == base.get('type')
                     and x.get('year') == base.get('year')]
            if not parts:
                continue
            fam = [base, *parts]
            groups = {group_of(x['platforms'][0], plays): x['platforms'] for x in fam if x.get('platforms')}
            first = group_of(base['platforms'][0], plays)
            note = base.get('note')
            if note and all(x.get('note') == note for x in parts):
                k = note_group(note, groups, first)
                for x in fam:
                    if group_of(x['platforms'][0], plays) != k:
                        x.pop('note', None)
                changed = True
            for x in fam:
                k = group_of(x['platforms'][0], plays)
                keep = [l for l in x.get('links', []) if link_group(l, groups, first) in (k, None)]
                if len(keep) != len(x.get('links', [])):
                    x['links'] = keep
                    changed = True
                if 'links' in x and not x['links']:
                    x.pop('links')
        if changed:
            write(f, g)
            fixed += 1
    log(f'  Hinweise/Links aufgeteilter Fassungen bereinigt: {fixed} Spiele')
    return fixed


def split_platforms(log=print, only=None):
    """Every version that mixes platforms with different ways to play becomes one version per platform."""
    plays = playable()
    projects = {p['id']: p for p in read(atlas.DATA / 'projects.json')['projects']}
    done = []
    for f in sorted((atlas.DATA / 'games').glob('*.json')):
        if only is not None and f.stem not in only:
            continue
        g = read(f)
        changed = False
        out = []
        for v in g.get('versions', []):
            v['platforms'] = canon_platforms(v.get('platforms'))
            if not needs_split(v, plays):
                out.append(v)
                continue
            groups = groups_of(v, plays)
            # the old id stays with the platform it names ("nintendo-switch"), else with the first platform
            first = next((k for k, ps in groups.items() if any(slug(p) and slug(p) in v['id'] for p in ps)),
                         group_of(v['platforms'][0], plays))
            order = [first] + [k for k in groups if k != first]
            ids = {}
            used = {x['id'] for x in g['versions']} | {x['id'] for x in out}
            for k in order:
                if k == first:
                    ids[k] = v['id']
                    continue
                vid = f"{v['id']}-{slug(groups[k][0] if k in ('other', 'mobile') else k)}"[:60]
                while vid in used:
                    vid += '-2'
                used.add(vid)
                ids[k] = vid
            parts = {}
            for k in order:
                nv = {key: val for key, val in v.items() if key not in ('reports',)}
                nv['id'], nv['platforms'] = ids[k], groups[k]
                nv['name'] = split_name(v, groups[k])
                nv['links'] = [dict(x) for x in v.get('links', []) if link_group(x, groups, first) in (k, None)]
                if not nv['links']:
                    nv.pop('links')
                note_k = note_group(v.get('note'), groups, first)
                if v.get('note') and note_k != k:
                    nv.pop('note', None)
                parts[k] = nv
            for rep in v.get('reports', []):
                k = report_group(rep, groups, plays, projects) or first
                parts[k].setdefault('reports', []).append(rep)
            for r in g.get('routes', []):
                if r.get('release') == v['id']:
                    k = route_group(r, groups, plays, projects) or first
                    r['release'] = ids[k]
            for m in g.get('mods', []):
                rel = m.get('release') or []
                if v['id'] not in rel:
                    continue
                text = ' '.join(str(m.get(x) or '') for x in ('name', 'edition', 'description', 'url'))
                k = route_group({'name': text}, groups, plays, projects)
                if not k and 'PC' in groups and PC_MOD_HOSTS.search(m.get('url') or ''):
                    k = 'PC'
                new = [ids[k]] if k else [ids[x] for x in order]
                m['release'] = list(dict.fromkeys([x for x in rel if x != v['id']] + new))
            out += [parts[k] for k in order]
            changed = True
            done.append(f"{g['id']}/{v['id']} → {', '.join(parts[k]['name'] for k in order)}")
        if changed:
            g['versions'] = out
            g['updatedAt'] = TODAY
            write(f, g)
    for line in done:
        log(f'  Fassung je Plattform: {line}')
    return done


# ---------------- remakes ----------------
STOP = {'the', 'of', 'and', 'a', 'an', 'hd', 'edition', 'remake', 'remastered', 'remaster', 'der', 'die', 'das', 'und'}


def tokens(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.findall(r'[a-z0-9]+', s)


def distinctive(remake, original):
    """Words of the remake's title that the original's title does not have ("Anniversary", "Twin Snakes", "3D")."""
    own = set(tokens(original['title']))
    return [t for t in tokens(re.sub(r'\((?:19|20)\d\d\)', '', remake['title'])) if t not in own and t not in STOP and not re.fullmatch(r'(19|20)\d\d', t)]


def simple(name):
    return ' '.join(tokens(re.sub(r'\([^)]*\)', ' ', name or '')))


def move_remake_versions(log=print):
    """Versions of an original that belong to its remake move there (re-releases, ports and collections of the remake)."""
    games = {f.stem: read(f) for f in (atlas.DATA / 'games').glob('*.json')}
    moved = []
    for rid, rm in sorted(games.items()):
        oid = rm.get('remakeOf')
        if not oid or oid not in games:
            continue
        orig = games[oid]
        words = distinctive(rm, orig)
        rm_names = {(simple(core_name(v)), v.get('year')) for v in rm.get('versions', []) if core_name(v)}
        keep, changed = [], False
        for v in orig.get('versions', []):
            vt = set(tokens(v.get('name')))
            belongs = bool(words) and all(w in vt for w in words) and v.get('type') != 'original'
            # the same named release (not just "PC (2004)") is already listed at the remake
            duplicate = bool(core_name(v)) and v.get('type') in ('collection', 'rerelease', 'port') and any(
                n == simple(core_name(v)) and (not y or not v.get('year') or y == v.get('year')) for n, y in rm_names)
            if not (belongs or duplicate):
                keep.append(v)
                continue
            routes = [r for r in orig.get('routes', []) if r.get('release') == v['id']]
            if duplicate and not belongs and not routes:
                moved.append(f'{oid}: „{v["name"]}“ steht schon beim Remake {rid} – entfernt')
                changed = True
                continue
            nv = dict(v)
            while any(x['id'] == nv['id'] for x in rm['versions']):
                nv['id'] += '-2'
            if nv.get('type') == 'remake':
                nv['type'] = 'rerelease'
            rm['versions'].append(nv)
            for r in routes:
                orig['routes'].remove(r)
                rm.setdefault('routes', []).append(dict(r, release=nv['id']))
            for m in orig.get('mods', []):
                if v['id'] in (m.get('release') or []):
                    m['release'] = [x for x in m['release'] if x != v['id']]
            rm['platforms'] += [p for p in nv.get('platforms', []) if p not in rm['platforms']]
            moved.append(f'{oid}: „{v["name"]}“ → Remake {rid}')
            changed = True
        if changed and keep:
            orig['versions'] = keep
            plats = {p for v in keep for p in v.get('platforms', [])}
            orig['platforms'] = [p for p in orig['platforms'] if p in plats] or orig['platforms']
            orig['updatedAt'] = rm['updatedAt'] = TODAY
            write(atlas.DATA / 'games' / f'{oid}.json', orig)
            write(atlas.DATA / 'games' / f'{rid}.json', rm)
    for line in moved:
        log(f'  Remake: {line}')
    return moved


# ---------------- checks for the agent ----------------
REMAKE_WORDS = re.compile(r'\bremake\b|von grund auf neu|neu entwickelt|neuentwicklung|komplett neu gebaut|neu gebaut|'
                          r'reimagin|neuinterpretation|rebuilt from|built from the ground', re.I)
NEGATION = re.compile(r'\b(kein|keine|nicht|no|not)\b[^.]{0,30}$', re.I)


def check(log=print):
    """Things that need a decision (no automatic fix): returns a list of strings."""
    plays = playable()
    known = set(read(atlas.DATA / 'platforms.json')['platforms']) | {'PC', 'Android', 'iOS'}
    games = {f.stem: read(f) for f in (atlas.DATA / 'games').glob('*.json')}
    out = []
    by_title = {}
    for g in games.values():
        by_title.setdefault(simple(re.sub(r'\((?:19|20)\d\d\)', '', g['title'])), []).append(g)
    for g in sorted(games.values(), key=lambda x: x['id']):
        for v in g.get('versions', []):
            text = f"{v.get('name', '')}. {v.get('note') or ''}"
            m = REMAKE_WORDS.search(text)
            if m and v.get('type') != 'remake' and not g.get('remakeOf') and not NEGATION.search(text[:m.start()]):
                out.append(f"Remake? {g['id']}/{v['id']} „{v['name']}“ ({v.get('type')}) – neu gebaut? Dann eigenes Spiel: "
                           f"type remake setzen (repair spaltet ab)")
            if needs_split(v, plays):
                out.append(f"Fassung mischt Plattformen: {g['id']}/{v['id']} {v['platforms']}")
    for key, same in by_title.items():
        if len(same) < 2:
            continue
        same.sort(key=lambda x: min([v.get('year') or 9999 for v in x.get('versions', [])] or [9999]))
        first = same[0]
        for later in same[1:]:
            if not later.get('remakeOf') and later.get('franchise') == first.get('franchise') and not later.get('notRemake'):
                out.append(f"Remake oder Reboot? {later['id']} (gleicher Titel wie {first['id']}) – Remake: \"remakeOf\": "
                           f"\"{first['id']}\", Reboot: \"notRemake\": true")
    unknown = {}
    for g in games.values():
        for v in g.get('versions', []):
            for p in v.get('platforms', []):
                if p not in known:
                    unknown.setdefault(p, 0)
                    unknown[p] += 1
    if unknown:
        out.append('Plattformen ohne Emulator-Eintrag (nur Info): ' + ', '.join(f'{p} ({n})' for p, n in sorted(unknown.items(), key=lambda x: -x[1])[:25]))
    for line in out:
        log(line)
    return out


if __name__ == '__main__':
    check()
