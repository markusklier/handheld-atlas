"""Validate the published, human-reviewed catalog without third-party packages."""
import json
import re
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def https(value):
    if not isinstance(value, str):
        return False
    try:
        u = urlsplit(value)
        return u.scheme == 'https' and bool(u.hostname) and not u.username and not u.password
    except ValueError:
        return False


def validate(catalog):
    assert catalog['schemaVersion'] == 1, 'Unsupported catalog version'
    source_ids, game_ids, route_ids = set(), set(), set()
    for source in catalog['sources']:
        assert source['id'] not in source_ids, 'Duplicate source'
        source_ids.add(source['id'])
        assert https(source['url']), 'Invalid source URL'
        assert source['role'] in {'primary', 'discovery', 'planned'}, 'Unknown source role'
        if source.get('repo'):
            assert re.fullmatch(r'[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+', source['repo']), 'Invalid repository'
    platform_ids = {p['platform'] for p in catalog['profiles'] if p['platform'] != 'all'}
    for game in catalog['games']:
        assert re.fullmatch(r'[a-z0-9-]+', game['id']), 'Invalid game ID'
        assert game['id'] not in game_ids, 'Duplicate game ID'
        game_ids.add(game['id'])
        assert game['title'] and game['franchise'] and game['routes'], 'Incomplete game'
        for route in game['routes']:
            assert re.fullmatch(r'[a-z0-9-]+', route['id']), 'Invalid route ID'
            assert route['id'] not in route_ids, 'Duplicate route ID'
            route_ids.add(route['id'])
            assert route['kind'] in catalog['kinds'], 'Unknown route kind'
            assert route['status'] in {'documented', 'experimental', 'archived'}, 'Unknown evidence status'
            assert route['targets'] and set(route['targets']) <= platform_ids, 'Unknown platform'
            assert set(route['features']) <= set(catalog['features']), 'Unknown feature'
            assert route['sources'] and set(route['sources']) <= source_ids, 'Missing provenance'
            assert isinstance(route['requires'], list) and route['requires'], 'Missing requirements'
            assert isinstance(route['steps'], list) and route['steps'], 'Missing setup preparation'
            assert route['benefit'] and route['caveat'], 'Missing tradeoffs'
            if 'fps60-tested' in route['features']:
                assert route['testedOn'] and route['performance'], 'Measured FPS requires test evidence'
            for store in route['stores']:
                assert https(store['url']), 'Invalid store URL'
            for shot in route.get('media',[]):
                assert https(shot.get('url')) and https(shot.get('sourceUrl')), 'Unsafe screenshot URL'
                assert isinstance(shot.get('caption'),str) and len(shot['caption'])<=180, 'Invalid screenshot caption'
                assert 'review' in shot and 'rights' in shot, 'Screenshot provenance missing'
    for entry in catalog.get('gameIndex',[]):
        assert isinstance(entry.get('id'),str) and re.fullmatch(r'[a-z0-9-]+',entry['id']), 'Invalid index ID'
        assert entry['id'] not in game_ids, 'Index/curated ID collision'
        game_ids.add(entry['id'])
        assert isinstance(entry.get('title'),str) and entry['title'].strip(), 'Missing game name'
        assert isinstance(entry.get('platforms'),list), 'Missing index platforms'
    return len(catalog['games']), len(route_ids), len(source_ids)


if __name__ == '__main__':
    try:
        n = validate(json.loads((ROOT / 'data/catalog.json').read_text(encoding='utf-8')))
        print('Validated: %d games, %d routes, %d sources.' % n)
    except (AssertionError, KeyError, TypeError, ValueError) as error:
        raise SystemExit('Catalog validation failed: ' + str(error))
