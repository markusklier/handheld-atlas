#!/usr/bin/env python3
"""Reihen (Franchises) konsistent halten.

Regel: "franchise" ist die Spielereihe, unter der ein Spiel erscheint – nicht das übergeordnete Universum.
Ableger mit eigener Reihe bekommen ihre eigene Reihe, auch wenn dieselbe Figur vorkommt:
Luigi's Mansion, Paper Mario, Mario & Luigi, Mario Party, Mario Kart sind eigene Reihen, nicht "Super Mario".

Prüfungen:
  1. Feste Ableger-Regeln (SERIES): Titel beginnt mit einem bekannten Reihennamen → diese Reihe.
  2. Konsistenz: beginnt ein Titel mit dem Namen einer anderen, bereits vorhandenen Reihe (längster Treffer)
     und steht trotzdem woanders, wird die andere Reihe vorgeschlagen.

    python3 scripts/franchises.py          # Vorschläge anzeigen
    python3 scripts/franchises.py --fix    # anwenden
"""
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from atlas import DATA, read, write  # noqa: E402

# (title prefix, series) – checked before the generic rule; longest prefix wins
SERIES = [
    ("Luigi's Mansion", "Luigi's Mansion"), ('Paper Mario', 'Paper Mario'), ('Mario & Luigi', 'Mario & Luigi'),
    ('Mario Party', 'Mario Party'), ('Super Mario Party', 'Mario Party'), ('Mario Kart', 'Mario Kart'),
    ('Super Mario Kart', 'Mario Kart'), ('Mario Tennis', 'Mario Sports'), ('Mario Golf', 'Mario Sports'),
    ('Mario Strikers', 'Mario Sports'), ('Mario Superstar Baseball', 'Mario Sports'), ('Mario Power Tennis', 'Mario Sports'),
    ('Wario', 'Wario'), ("Yoshi's", 'Yoshi'), ('Yoshi', 'Yoshi'), ('Donkey Kong', 'Donkey Kong'),
    ('Super Smash Bros', 'Super Smash Bros.'), ('Kirby', 'Kirby'), ('Metroid', 'Metroid'),
    ('Pokémon', 'Pokémon'), ('Pokemon', 'Pokémon'), ('The Legend of Zelda', 'The Legend of Zelda'),
    ('Fire Emblem', 'Fire Emblem'), ('Xenoblade', 'Xenoblade Chronicles'), ('Animal Crossing', 'Animal Crossing'),
    ('Grand Theft Auto', 'Grand Theft Auto'), ('Final Fantasy', 'Final Fantasy'), ('Dragon Quest', 'Dragon Quest'),
    ('Tomb Raider', 'Tomb Raider'), ('DOOM', 'Doom'), ('Doom', 'Doom'), ('Half-Life', 'Half-Life'), ('Portal', 'Portal'),
    ('Resident Evil', 'Resident Evil'), ('Metal Gear', 'Metal Gear'), ('Sonic', 'Sonic the Hedgehog'),
    ('Castlevania', 'Castlevania'), ('Mega Man', 'Mega Man'), ('Persona', 'Persona'), ('Monster Hunter', 'Monster Hunter'),
    ('Ecco', 'Ecco the Dolphin'), ('The Legend of Heroes', 'Trails'), ('Trails', 'Trails'),
    ('Ratchet & Clank', 'Ratchet & Clank'), ('Crash', 'Crash Bandicoot'), ('Spyro', 'Spyro'), ('Minecraft', 'Minecraft'),
]


def norm(s):
    s = unicodedata.normalize('NFKD', s or '').encode('ascii', 'ignore').decode().lower()
    return re.sub(r'[^a-z0-9]+', ' ', s).strip()


def starts(title, prefix):
    t, p = norm(title), norm(prefix)
    return t == p or t.startswith(p + ' ')


def suggest(games):
    """Yield (game, current, suggested, reason)."""
    names = {g['franchise'] for g in games}
    # series that exist as a real group (2+ games) are trusted anchors for the generic rule
    groups = {}
    for g in games:
        groups.setdefault(g['franchise'], []).append(g)
    anchors = {n for n, gs in groups.items() if len(gs) >= 2} | {s for _, s in SERIES}
    for g in games:
        current = g['franchise']
        fixed = [s for p, s in sorted(SERIES, key=lambda x: -len(x[0])) if starts(g['title'], p)]
        if fixed:
            if fixed[0] != current:
                yield g, current, fixed[0], 'Ableger-Regel'
            continue
        candidates = sorted((n for n in anchors | names if n != current and n != g['title'] and starts(g['title'], n)),
                            key=len, reverse=True)
        if candidates and not starts(g['title'], current):
            yield g, current, candidates[0], 'Titel beginnt mit vorhandener Reihe'


def main():
    files = sorted((DATA / 'games').glob('*.json'))
    games = [read(f) for f in files]
    found = list(suggest(games))
    for g, cur, new, why in found:
        print(f"{g['id']}: „{cur}“ → „{new}“ ({why})")
    if '--fix' in sys.argv:
        by_id = {g['id']: new for g, _, new, _ in found}
        for f in files:
            g = read(f)
            if g['id'] in by_id:
                g['franchise'] = by_id[g['id']]
                write(f, g)
        print(f'{len(found)} Reihen korrigiert')
    else:
        print(f'{len(found)} Vorschläge (mit --fix anwenden)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
