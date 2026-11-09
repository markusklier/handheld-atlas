#!/usr/bin/env python3
"""Fill missing covers and original-game screenshots from libretro-thumbnails (GitHub).

Only file *listings* are fetched (git tree, no image download); images are linked, not copied.
Titles are matched against No-Intro/Redump file names, e.g.
    "The Legend of Zelda: A Link to the Past" -> "Legend of Zelda, The - A Link to the Past (USA).png"

    python3 scripts/covers.py            # fill games that have no cover yet
    python3 scripts/covers.py --force    # re-match everything that came from libretro
"""
import re
import subprocess
import sys
import unicodedata
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from atlas import DATA, ROOT, read, write  # noqa: E402

CACHE = ROOT / '.cache' / 'libretro'
REPOS = {
    'SNES': ['Nintendo_-_Super_Nintendo_Entertainment_System'],
    'NES': ['Nintendo_-_Nintendo_Entertainment_System'],
    'Nintendo 64': ['Nintendo_-_Nintendo_64'],
    'Game Boy Advance': ['Nintendo_-_Game_Boy_Advance'],
    'Game Boy / Game Boy Color': ['Nintendo_-_Game_Boy_Color', 'Nintendo_-_Game_Boy'],
    'Nintendo DS': ['Nintendo_-_Nintendo_DS'],
    'Nintendo 3DS': ['Nintendo_-_Nintendo_3DS'],
    'Nintendo GameCube': ['Nintendo_-_GameCube'],
    'Wii': ['Nintendo_-_Wii'],
    'PlayStation': ['Sony_-_PlayStation'],
    'PlayStation 2': ['Sony_-_PlayStation_2'],
    'PSP': ['Sony_-_PlayStation_Portable'],
    'PlayStation Vita': ['Sony_-_PlayStation_Vita'],
    'Dreamcast': ['Sega_-_Dreamcast'],
    'Sega Mega Drive': ['Sega_-_Mega_Drive_-_Genesis'],
}
REGION_RANK = ['(USA)', '(USA, Europe)', '(World)', '(Europe)', '(Japan, USA)', '(Germany)', '(Japan)']
SKIP = re.compile(r'\((Beta|Proto|Demo|Sample|Kiosk|Pirate|Unl|Hack)|Virtual Console|Redux|\[', re.I)


def norm(s):
    s = unicodedata.normalize('NFKD', s).encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'^(.*), the( - |$)', r'the \1\2', s)  # "Legend of Zelda, The - X" -> "the legend of zelda - x"
    s = s.replace('&', 'and').replace(' - ', ' ').replace(':', ' ')
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def listing(repo):
    target = CACHE / repo
    if not target.exists():
        CACHE.mkdir(parents=True, exist_ok=True)
        subprocess.run(['git', 'clone', '-q', '--depth', '1', '--filter=blob:none', '--no-checkout',
                        f'https://github.com/libretro-thumbnails/{repo}', str(target)], check=True, timeout=600)
    out = subprocess.run(['git', '-C', str(target), 'ls-tree', '-r', '--name-only', 'HEAD'],
                         capture_output=True, text=True, check=True).stdout
    index = {}
    for path in out.splitlines():
        folder, _, name = path.partition('/')
        if folder not in ('Named_Boxarts', 'Named_Snaps', 'Named_Titles') or not name.endswith('.png'):
            continue
        if SKIP.search(name):
            continue
        stem = name[:-4].split(' (')[0]
        base = norm(stem)
        keys = {base, re.sub(r' version$', '', base)}
        acro = re.match(r'^([A-Z0-9]{2,5}) - (.+)$', stem)       # "CTR - Crash Team Racing" also as "crash team racing"
        if acro:
            keys.add(norm(acro.group(2)))
        for key in keys:
            index.setdefault(key, {}).setdefault(folder, []).append(name)
    return index


def lookup(index, title, exact=True):
    key = norm(title)
    if exact:
        return (key, index[key]) if key in index else None
    # "Wave Race 64" -> "Wave Race 64 - Kawasaki Jet Ski": accept the shortest longer name with a box art
    longer = sorted((k for k in index if k.startswith(key + ' ') and 'Named_Boxarts' in index[k]), key=len)
    return (longer[0], index[longer[0]]) if longer and len(key) >= 8 else None


def pick(names):
    def rank(n):
        for i, r in enumerate(REGION_RANK):
            if r in n:
                return i
        return len(REGION_RANK)
    return sorted(names, key=lambda n: (rank(n), len(n)))[0]


def url(repo, folder, name):
    return (f'https://raw.githubusercontent.com/libretro-thumbnails/{repo}/master/{folder}/'
            + urllib.parse.quote(name))


def main(force=False, only=None):
    indexes = {}
    filled = 0
    for f in sorted((DATA / 'games').glob('*.json')):
        if only is not None and f.stem not in only:
            continue
        g = read(f)
        has_libretro = 'libretro-thumbnails' in (g.get('cover') or {}).get('url', '')
        has_snaps = any('libretro-thumbnails' in x['url'] for x in g.get('screenshots', []))
        # normally only games without cover; on request (only=…) also games that still lack original screenshots
        if g.get('cover') and not (force and has_libretro) and not (only is not None and not has_snaps):
            continue
        repos = [r for plat in g.get('platforms', []) for r in REPOS.get(plat, [])]
        for repo in repos:
            if repo not in indexes:
                try:
                    indexes[repo] = listing(repo)
                except Exception as e:  # noqa: BLE001
                    print(f'! {repo}: {e}', file=sys.stderr)
                    indexes[repo] = {}
        # exact title matches in every set win over prefix matches
        best = None
        for exact in (True, False):
            found = [(len(m[0]), repo, m[1]) for repo in repos
                     if (m := lookup(indexes[repo], g['title'], exact)) and 'Named_Boxarts' in m[1]]
            if found:
                best = min(found, key=lambda x: x[0])
                break
        if best:
            _, repo, hit = best
            source = f'https://github.com/libretro-thumbnails/{repo}'
            if not g.get('cover') or has_libretro:
                g['cover'] = {'url': url(repo, 'Named_Boxarts', pick(hit['Named_Boxarts'])), 'source': source}
            shots = [s for s in g.get('screenshots', []) if 'libretro-thumbnails' not in s['url']]
            for folder, caption in (('Named_Snaps', 'Originalspiel'), ('Named_Titles', 'Titelbild')):
                if hit.get(folder):
                    shots.append({'url': url(repo, folder, pick(hit[folder])), 'caption': caption, 'source': source})
            g['screenshots'] = shots
            write(f, g)
            filled += 1
    print(f'covers.py: {filled} Spiele mit Cover/Screenshots ergänzt')
    return filled


if __name__ == '__main__':
    main(force='--force' in sys.argv)
