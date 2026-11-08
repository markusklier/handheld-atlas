#!/usr/bin/env python3
"""Community-Berichte von EmuReady (https://www.emuready.com) an die Fassungen hängen.

EmuReady sammelt Berichte "Spiel × Gerät × Emulator → Bewertung (Perfect … Nothing), Notizen, Einstellungen".
Wir holen nur Berichte von Geräten mit demselben SoC wie das Referenzgerät (AYN Thor),
weil die direkt übertragbar sind, und speichern je Fassung eine kurze Zusammenfassung mit Link zurück.

Höflich: öffentliche Mobile-API, eindeutiger User-Agent, Pause zwischen Anfragen, begrenzte Spiele pro Lauf,
Ergebnis wird 14 Tage gemerkt. Optional EMUREADY_API_KEY (Header x-api-key).

    python3 scripts/emuready.py [--limit 40] [--game <id>]
"""
import argparse
import json
import os
import re
import sys
import time
import unicodedata
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from atlas import DATA, read, write  # noqa: E402

BASE = 'https://www.emuready.com/api/mobile/trpc/'
SITE = 'https://www.emuready.com'
UA = 'HandheldAtlas/1.2 (+https://github.com/markusklier/handheld-atlas; non-commercial game catalog)'
RATING_DE = {'Perfect': 'Perfekt', 'Great': 'Sehr gut', 'Playable': 'Spielbar', 'Poor': 'Schwach',
             'Ingame': 'Mit Fehlern', 'Intro': 'Nur Intro/Menü', 'Loadable': 'Lädt nur', 'Nothing': 'Läuft nicht'}
# EmuReady system name fragments -> Atlas platform names
SYSTEMS = [
    ('playstation 2', 'PlayStation 2'), ('playstation portable', 'PSP'), ('psp', 'PSP'), ('playstation vita', 'PlayStation Vita'),
    ('playstation 3', 'PlayStation 3'), ('playstation 4', 'PlayStation 4'), ('playstation 5', 'PlayStation 5'),
    ('playstation', 'PlayStation'), ('switch', 'Nintendo Switch'),
    ('3ds', 'Nintendo 3DS'), ('nintendo ds', 'Nintendo DS'), ('gamecube', 'Nintendo GameCube'), ('wii u', 'Wii U'),
    ('wii', 'Wii'), ('nintendo 64', 'Nintendo 64'), ('super nintendo', 'SNES'), ('snes', 'SNES'),
    ('game boy advance', 'Game Boy Advance'), ('game boy', 'Game Boy / Game Boy Color'), ('dreamcast', 'Dreamcast'),
    ('saturn', 'Sega Saturn'), ('mega drive', 'Sega Mega Drive'), ('genesis', 'Sega Mega Drive'),
    ('xbox 360', 'Xbox 360'), ('xbox', 'Xbox'), ('windows', 'PC'), ('pc', 'PC'), ('dos', 'PC'),
]
SETTING_KEYS = 10   # keep the most useful settings only
MAX_REPORTS = 12    # per version


def norm(s):
    s = re.sub(r'[™®©]', '', s or '')
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower().replace('&', 'and')
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def platform_of(system_name):
    n = (system_name or '').lower()
    for frag, plat in SYSTEMS:
        if frag in n:
            return plat
    return None


class Client:
    def __init__(self, pause=1.2, fetch=None):
        self.pause, self.fetch = pause, fetch or self._fetch
        self.key = os.environ.get('EMUREADY_API_KEY')

    def _fetch(self, url):
        headers = {'User-Agent': UA, 'Accept': 'application/json'}
        if self.key:
            headers['x-api-key'] = self.key
        with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=30) as r:
            return json.loads(r.read().decode())

    def call(self, procedure, payload):
        url = BASE + procedure + '?input=' + urllib.parse.quote(json.dumps({'json': payload}, separators=(',', ':')))
        data = self.fetch(url)
        if self.pause:
            time.sleep(self.pause)
        res = data[0] if isinstance(data, list) else data
        return ((res.get('result') or {}).get('data') or {}).get('json')


def reference_devices(client, state):
    """All EmuReady device ids that share the AYN Thor's SoC (devices.get returns socName, not an id)."""
    if state.get('deviceIds'):
        return state['deviceIds']
    res = client.call('devices.get', {'limit': 1000}) or {}
    devices = res.get('devices', res) if isinstance(res, dict) else res
    thor = next((d for d in devices if 'thor' in norm(d.get('modelName')) and 'ayn' in norm(d.get('brandName'))), None)
    if not thor or not thor.get('socName'):
        raise RuntimeError('AYN Thor (mit SoC) nicht in EmuReady gefunden')
    same = [d for d in devices if d.get('socName') == thor['socName']]
    state.update(socName=thor['socName'], deviceIds=[d['id'] for d in same][:40],
                 devices=sorted(f"{d.get('brandName')} {d.get('modelName')}" for d in same)[:40])
    return state['deviceIds']


def summarize(listing, settings=None):
    perf = listing.get('performance') or {}
    device = listing.get('device') or {}
    name = ' '.join(x for x in [(device.get('brand') or {}).get('name'), device.get('modelName')] if x)
    rep = {
        'source': 'EmuReady',
        'url': f"{SITE}/listings/{listing['id']}",
        'device': name or 'unbekannt',
        'emulator': (listing.get('emulator') or {}).get('name') or '',
        'rating': perf.get('label') or '',
        'ratingDe': RATING_DE.get(perf.get('label'), perf.get('label') or ''),
        'rank': perf.get('rank') or 9,
        'summary': re.sub(r'\s+', ' ', (listing.get('notes') or '')).strip()[:220],
        'votes': listing.get('voteCount') or listing.get('totalVotes') or 0,
        'date': (listing.get('createdAt') or '')[:10],
    }
    if settings:
        rep['settings'] = settings
    return rep


def settings_of(client, listing_id):
    detail = client.call('listings.byId', {'id': listing_id}) or {}
    out = {}
    for v in detail.get('customFieldValues') or []:
        d = v.get('customFieldDefinition') or {}
        val = v.get('value')
        if val in (None, '', [], False) or d.get('name') in ('youtube', 'media_url'):
            continue
        if isinstance(val, (dict, list)):
            val = json.dumps(val, ensure_ascii=False)[:60]
        out[d.get('label') or d.get('name')] = str(val)[:80]
        if len(out) >= SETTING_KEYS:
            break
    return out


def sync_game(client, game, device_ids, log=print):
    """Returns number of reports attached."""
    versions = game.get('versions') or []
    if not versions:
        return 0
    hits = client.call('games.searchGames', {'query': game['title'][:100]}) or []
    want = norm(game['title'])
    matched = []
    for h in hits:
        if norm(h.get('title')) != want:
            continue
        plat = platform_of((h.get('system') or {}).get('name'))
        v = next((v for v in versions if plat and plat in v['platforms']), None)
        if v:
            matched.append((h, v))
    total = 0
    for h, v in matched:
        res = client.call('listings.get', {'gameIds': [h['id']], 'deviceIds': device_ids, 'limit': 50, 'page': 1}) or {}
        listings = res.get('listings') if isinstance(res, dict) else res
        listings = sorted(listings or [], key=lambda l: ((l.get('performance') or {}).get('rank') or 9, -(l.get('voteCount') or 0)))
        reports, per_emu = [], {}
        for l in listings[:MAX_REPORTS]:
            emu = (l.get('emulator') or {}).get('name') or ''
            per_emu[emu] = per_emu.get(emu, 0) + 1
            settings = settings_of(client, l['id']) if per_emu[emu] <= 2 else None   # settings for the 2 best per emulator
            reports.append(summarize(l, settings))
        others = [r for r in v.get('reports', []) if r.get('source') != 'EmuReady']
        v['reports'] = others + reports
        v.setdefault('links', [])
        link = {'label': 'EmuReady', 'url': f"{SITE}/games/{h['id']}"}
        if not any(l['url'] == link['url'] for l in v['links']):
            v['links'].append(link)
        total += len(reports)
    return total


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--limit', type=int, default=40)
    ap.add_argument('--game')
    args = ap.parse_args()
    state_path = DATA / 'emuready_state.json'
    state = read(state_path) if state_path.exists() else {'games': {}}
    client = Client()
    try:
        devices = reference_devices(client, state)
    except Exception as e:  # noqa: BLE001
        print(f'EmuReady nicht erreichbar oder Gerät unbekannt: {e}')
        return 0
    cutoff = (date.today() - timedelta(days=14)).isoformat()
    files = [DATA / 'games' / f'{args.game}.json'] if args.game else sorted((DATA / 'games').glob('*.json'))
    # games with ways first (most useful), then the rest; skip recently synced ones
    games = [(f, read(f)) for f in files]
    games.sort(key=lambda x: (not x[1].get('routes'), state['games'].get(x[1]['id'], '')))
    done = added = 0
    changelog = read(DATA / 'changelog.json')
    for f, g in games:
        if done >= args.limit:
            break
        if not args.game and state['games'].get(g['id'], '') >= cutoff:
            continue
        done += 1
        try:
            n = sync_game(client, g, devices)
        except Exception as e:  # noqa: BLE001
            print(f'! {g["id"]}: {e}', file=sys.stderr)
            continue
        state['games'][g['id']] = date.today().isoformat()
        if n:
            write(f, g)
            added += n
            changelog['entries'].insert(0, {'date': date.today().isoformat(), 'type': 'route-updated', 'game': g['id'],
                                            'text': f"{n} Community-Berichte von EmuReady für {g['title']} (Geräte mit dem Chip des AYN Thor)"})
    write(state_path, state)
    write(DATA / 'changelog.json', changelog)
    print(f'emuready.py: {done} Spiele geprüft, {added} Berichte übernommen')
    return 0


if __name__ == '__main__':
    sys.exit(main())
