#!/usr/bin/env python3
"""Handheld Atlas: research a whole series in one go – without AI costs for everything that is free.

    python3 scripts/series.py "Dead Space"              # complete the series and fill every game right away
    python3 scripts/series.py "Dead Space" --no-queue   # same, but do not put the games into the research queue

What it does (the same for the API mode and the Claude subscription):
1. Wikidata: missing games of the series, remasters/collections as versions, remakes as games of their own.
2. Every game of the series: Wikidata base profile (years, platforms, versions), one version per platform,
   covers and original screenshots (libretro-thumbnails, Steam, Wikipedia, official website), a cover per version.
3. Every game that has no deep research yet goes to the front of the research queue (data/queue.json) – the
   API run picks the worthwhile ones with one cheap call (ai_research.triage), the subscription agent works the queue.
So one request for the series gives every game a complete basic entry with pictures at once, instead of
"series, then each game, then each way" separately.
Standard library only (plus the other scripts in this folder).
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import atlas  # noqa: E402
from atlas import read  # noqa: E402


def series_ids(name):
    return sorted(f.stem for f in (atlas.DATA / 'games').glob('*.json') if read(f).get('franchise') == name)


def fill_free(ids, log=print):
    """Base profile, versions, covers and screenshots for these games – free sources only. Every step is optional:
    a source that is not reachable is skipped, the rest still runs."""
    ids = set(ids)
    if not ids:
        return {}
    done = {}

    def step(name, fn):
        try:
            done[name] = fn()
        except Exception as e:  # noqa: BLE001
            log(f'  ! {name}: {type(e).__name__}: {str(e)[:120]}')

    import wikidata
    step('wikidata', lambda: wikidata.enrich(len(ids) + 5, log=log, only={i for i in ids if not read(atlas.DATA / 'games' / f'{i}.json').get('wikidata')}))
    import quality
    step('fassungen', lambda: len(quality.split_platforms(log=log, only=ids)))
    step('remakes', lambda: len(atlas.split_remakes(log=log)) + len(quality.move_remake_versions(log=log)))
    ids = {i for i in ids if (atlas.DATA / 'games' / f'{i}.json').exists()}
    import covers
    step('libretro', lambda: covers.main(only=ids))
    import media
    step('steam', lambda: media.fill_steam(only=ids))
    step('wikipedia', lambda: media.fill_wikipedia(only=ids, limit=len(ids) + 5))
    step('website', lambda: media.fill_website_covers(only=ids))
    step('fassungs-cover', lambda: covers.fill_versions(only=ids, log=log))
    step('readme-bilder', lambda: media.fill_route_shots(only=ids))
    return done


def run(name, queue=True, log=print):
    import ai_research
    import wikidata
    try:
        report = wikidata.complete_series(name, log=log)
    except Exception as e:  # noqa: BLE001
        log(f'  ! Wikidata-Reihe: {type(e).__name__}: {str(e)[:120]}')
        report = {'members': 0, 'added': [], 'versions': [], 'skipped': []}
    ids = series_ids(name)
    log(f'Reihe {name}: {len(ids)} Spiele in Atlas, {len(report.get("added", []))} neu aus Wikidata')
    fill_free(ids, log=log)
    games = [read(atlas.DATA / 'games' / f'{i}.json') for i in series_ids(name)]
    with_cover = sum(1 for g in games if g.get('cover'))
    with_shots = sum(1 for g in games if g.get('screenshots'))
    queued = 0
    if queue:
        researched = read(atlas.DATA / 'inbox.json').get('aiResearch', {})
        todo = sorted((g for g in games if g['id'] not in researched),
                      key=lambda g: (not g.get('routes'), min([v.get('year') or 9999 for v in g.get('versions', [])] or [9999])))
        queued = ai_research.queue_add([g['id'] for g in todo], f'Reihe {name}', front=True)
    log(f'Reihe {name}: {len(games)} Spiele, {with_cover} mit Cover, {with_shots} mit Originalbildern, {queued} zur Tiefenrecherche eingereiht')
    inbox = read(atlas.DATA / 'inbox.json')
    scan = inbox.setdefault('franchiseScan', {}).get(name, {})
    scan.update({'date': ai_research.TODAY, 'source': scan.get('source') or 'wikidata',
                 'listed': report.get('members', scan.get('listed', 0)), 'added': report.get('added', scan.get('added', [])),
                 'versions': report.get('versions', scan.get('versions', [])), 'skipped': report.get('skipped', scan.get('skipped', [])),
                 'filled': len(games), 'covers': with_cover, 'queued': queued})
    inbox['franchiseScan'][name] = scan
    atlas.write(atlas.DATA / 'inbox.json', inbox)
    return {'games': len(games), 'covers': with_cover, 'shots': with_shots, 'queued': queued, 'added': report.get('added', [])}


if __name__ == '__main__':
    import ai_research  # noqa: F401  (TODAY, queue)
    ap = argparse.ArgumentParser()
    ap.add_argument('name')
    ap.add_argument('--no-queue', action='store_true')
    a = ap.parse_args()
    run(a.name, queue=not a.no_queue)
