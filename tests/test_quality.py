"""Data rules of scripts/quality.py: one version per playable platform, remake re-releases go to the remake."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import atlas  # noqa: E402
import quality  # noqa: E402

QUIET = dict(log=lambda *a: None)


class QualityTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(atlas.DATA, self.tmp / 'data')
        self.orig = atlas.DATA
        atlas.DATA = self.tmp / 'data'

    def tearDown(self):
        atlas.DATA = self.orig
        shutil.rmtree(self.tmp)

    def game(self, gid, **kw):
        g = {'id': gid, 'title': kw.pop('title', gid.title()), 'franchise': 'Testreihe', 'platforms': ['PC'],
             'versions': [], 'routes': [], 'mods': [], 'screenshots': [], 'updatedAt': '2026-11-19', **kw}
        atlas.write(atlas.DATA / 'games' / f'{gid}.json', g)
        return g

    def read(self, gid):
        return atlas.read(atlas.DATA / 'games' / f'{gid}.json')

    def test_database_has_no_mixed_versions(self):
        plays = quality.playable()
        for g in atlas.load_db()['games']:
            for v in g.get('versions', []):
                self.assertFalse(quality.needs_split(v, plays), f"{g['id']}/{v['id']} {v['platforms']}")

    def test_split_one_version_per_platform_with_routes_mods_reports(self):
        self.game('zz-racer', platforms=['PC', 'PlayStation 2', 'Nintendo GameCube'], versions=[
            {'id': 'multi', 'name': 'PC/PS2/GameCube (2004)', 'type': 'original', 'year': 2004,
             'platforms': ['PC', 'PlayStation 2', 'Nintendo GameCube', 'PlayStation 4'],
             'reports': [{'source': 'EmuReady', 'emulator': 'Dolphin', 'url': 'https://example.org/r1'},
                         {'source': 'EmuReady', 'emulator': 'Winlator', 'url': 'https://example.org/r2'}]}],
            routes=[{'id': 'w-pc', 'name': 'Über GameNative', 'release': 'multi', 'kind': 'pc-runtime'},
                    {'id': 'w-ps2', 'name': 'Widescreen-Patch', 'release': 'multi', 'kind': 'emulator-mod', 'edition': 'PS2-Fassung'},
                    {'id': 'w-x', 'name': 'Irgendwas', 'release': 'multi', 'kind': 'native'}],
            mods=[{'id': 'm-pc', 'name': 'HD-Texturen', 'release': ['multi'], 'url': 'https://www.nexusmods.com/x'},
                  {'id': 'm-all', 'name': 'Übersetzung', 'release': ['multi'], 'url': 'https://example.org/t'}])
        quality.split_platforms(only={'zz-racer'}, **QUIET)
        g = self.read('zz-racer')
        by_plat = {tuple(v['platforms']): v for v in g['versions']}
        self.assertEqual(set(by_plat), {('PC',), ('PlayStation 2',), ('Nintendo GameCube',), ('PlayStation 4',)})
        self.assertEqual(by_plat[('PC',)]['id'], 'multi')                       # old id stays with the first platform
        self.assertEqual(by_plat[('PlayStation 2',)]['name'], 'PlayStation 2 (2004)')
        routes = {r['id']: r['release'] for r in g['routes']}
        self.assertEqual(routes['w-pc'], 'multi')
        self.assertEqual(routes['w-ps2'], by_plat[('PlayStation 2',)]['id'])
        self.assertEqual(routes['w-x'], 'multi')                                # unknown → first platform
        self.assertEqual([r['emulator'] for r in by_plat[('Nintendo GameCube',)]['reports']], ['Dolphin'])
        self.assertEqual([r['emulator'] for r in by_plat[('PC',)]['reports']], ['Winlator'])
        mods = {m['id']: m['release'] for m in g['mods']}
        self.assertEqual(mods['m-pc'], ['multi'])
        self.assertEqual(len(mods['m-all']), 4)

    def test_names_keep_the_edition(self):
        cases = [({'name': 'Skyrim Special Edition für PC', 'platforms': ['PC', 'PlayStation 4']}, 'Skyrim Special Edition'),
                 ({'name': 'PC, PS3/4, Xbox 360/One (2014)', 'platforms': ['PC', 'PlayStation 3', 'PlayStation 4', 'Xbox 360', 'Xbox One']}, ''),
                 ({'name': "Restless Dreams / Director's Cut (2001)", 'platforms': ['Xbox', 'PC']}, "Restless Dreams / Director's Cut"),
                 ({'name': 'PSone Classic (PS3/PSP/Vita, 2009)', 'platforms': ['PlayStation 3', 'PSP', 'PlayStation Vita']}, 'PSone Classic'),
                 ({'name': 'Nintendo Switch Online (2019)', 'platforms': ['Nintendo Switch', 'Nintendo Switch 2']}, 'Nintendo Switch Online')]
        for v, want in cases:
            self.assertEqual(quality.core_name(v), want, v['name'])

    def test_unplayable_platforms_stay_together(self):
        plays = quality.playable()
        self.assertFalse(quality.needs_split({'platforms': ['PlayStation 4', 'PlayStation 5', 'Xbox Series']}, plays))
        self.assertFalse(quality.needs_split({'type': 'android', 'platforms': ['Android', 'iOS']}, plays))
        self.assertTrue(quality.needs_split({'platforms': ['PC', 'PlayStation 5']}, plays))

    def test_remake_rerelease_moves_and_known_collection_is_dropped(self):
        self.game('zz-quest', title='ZZ Quest', versions=[
            {'id': 'pc', 'name': 'PC (1996)', 'type': 'original', 'year': 1996, 'platforms': ['PC']},
            {'id': 'ann-ps5', 'name': 'ZZ Quest: Jubilee – PS5-Neuauflage', 'type': 'rerelease', 'year': 2025, 'platforms': ['PlayStation 5']},
            {'id': 'trilogy', 'name': 'The ZZ Trilogy (2011)', 'type': 'collection', 'year': 2011, 'platforms': ['PlayStation 3']}])
        self.game('zz-quest-jubilee', title='ZZ Quest: Jubilee', remakeOf='zz-quest', versions=[
            {'id': 'pc', 'name': 'PC (2007)', 'type': 'remake', 'year': 2007, 'platforms': ['PC']},
            {'id': 'ps3', 'name': 'The ZZ Trilogy (PS3, 2011)', 'type': 'collection', 'year': 2011, 'platforms': ['PlayStation 3']}])
        quality.move_remake_versions(**QUIET)
        self.assertEqual([v['id'] for v in self.read('zz-quest')['versions']], ['pc'])
        self.assertIn('ann-ps5', [v['id'] for v in self.read('zz-quest-jubilee')['versions']])
        self.assertEqual(len(self.read('zz-quest-jubilee')['versions']), 3)

    def test_split_remake_on_several_platforms_folds_into_existing_game(self):
        self.game('zz-kart', title='ZZ Kart', platforms=['PlayStation'], versions=[
            {'id': 'ps1', 'name': 'PlayStation (1999)', 'type': 'original', 'year': 1999, 'platforms': ['PlayStation']},
            {'id': 'nf', 'name': 'ZZ Kart Turbo – Nintendo Switch (2019)', 'type': 'remake', 'year': 2019, 'platforms': ['Nintendo Switch']},
            {'id': 'nf-ps4', 'name': 'ZZ Kart Turbo – PlayStation 4 (2019)', 'type': 'remake', 'year': 2019, 'platforms': ['PlayStation 4']}],
            routes=[{'id': 'eden', 'name': 'Eden', 'release': 'nf', 'kind': 'emulation', 'targets': ['android'],
                     'verification': 'ai-unverified', 'links': [{'label': 'x', 'url': 'https://example.org/e'}]}])
        self.game('zz-kart-turbo', title='ZZ Kart Turbo', platforms=['Nintendo Switch'], versions=[
            {'id': 'nintendo-switch', 'name': 'Nintendo Switch', 'type': 'original', 'platforms': ['Nintendo Switch']}])
        made = atlas.split_remakes(**QUIET)
        self.assertEqual(made, ['zz-kart-turbo'])
        self.assertFalse((atlas.DATA / 'games' / 'zz-kart-turbo-remake.json').exists())
        t = self.read('zz-kart-turbo')
        self.assertEqual(t['remakeOf'], 'zz-kart')
        self.assertEqual(len(t['versions']), 2)
        self.assertEqual(t['versions'][0]['year'], 2019)
        self.assertEqual(t['routes'][0]['release'], 'nintendo-switch')
        self.assertEqual([v['id'] for v in self.read('zz-kart')['versions']], ['ps1'])


if __name__ == '__main__':
    unittest.main()


class SeriesTest(unittest.TestCase):
    """scripts/series.py: one request fills every game of the series (free sources stubbed) and queues them."""
    def setUp(self):
        import ai_research
        import covers
        import media
        import wikidata
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(atlas.DATA, self.tmp / 'data')
        self.saved = (atlas.DATA, ai_research.DATA, wikidata.DATA, covers.DATA, media.DATA, wikidata.STATE)
        atlas.DATA = ai_research.DATA = wikidata.DATA = covers.DATA = media.DATA = self.tmp / 'data'
        wikidata.STATE = self.tmp / 'data' / 'wikidata_state.json'
        self.calls = []
        self.patches = [(wikidata, 'complete_series', lambda name, log=print: {'members': 3, 'added': ['zz-two'], 'versions': [], 'skipped': []}),
                        (wikidata, 'enrich', lambda *a, **k: self.calls.append('wikidata') or 0),
                        (covers, 'main', lambda only=None, **k: self.calls.append(('covers', sorted(only))) or 0),
                        (covers, 'fill_versions', lambda only=None, **k: 0),
                        (media, 'fill_steam', lambda **k: 0), (media, 'fill_wikipedia', lambda **k: 0),
                        (media, 'fill_website_covers', lambda **k: 0), (media, 'fill_route_shots', lambda **k: 0)]
        self.orig = [(m, n, getattr(m, n)) for m, n, _ in self.patches]
        for m, n, f in self.patches:
            setattr(m, n, f)
        for gid, title, plats in (('zz-one', 'ZZ One', ['PC', 'PlayStation 2']), ('zz-two', 'ZZ Two', ['PC'])):
            atlas.write(atlas.DATA / 'games' / f'{gid}.json', {
                'id': gid, 'title': title, 'franchise': 'ZZ Reihe', 'platforms': plats, 'routes': [], 'mods': [], 'updatedAt': '2026-11-19',
                'versions': [{'id': 'multi', 'name': ' / '.join(plats) + ' (2004)', 'type': 'original', 'year': 2004, 'platforms': plats}]})

    def tearDown(self):
        import ai_research
        import covers
        import media
        import wikidata
        for m, n, f in self.orig:
            setattr(m, n, f)
        atlas.DATA, ai_research.DATA, wikidata.DATA, covers.DATA, media.DATA, wikidata.STATE = self.saved
        shutil.rmtree(self.tmp)

    def test_series_fills_and_queues_every_game(self):
        import series
        r = series.run('ZZ Reihe', log=lambda *a: None)
        self.assertEqual(r['games'], 2)
        self.assertEqual(r['queued'], 2)
        self.assertIn(('covers', ['zz-one', 'zz-two']), self.calls)
        one = atlas.read(atlas.DATA / 'games' / 'zz-one.json')
        self.assertEqual(sorted(v['platforms'][0] for v in one['versions']), ['PC', 'PlayStation 2'])   # one version per platform
        q = atlas.read(atlas.DATA / 'queue.json')
        self.assertEqual([j['game'] for j in q['jobs'][:2]], ['zz-one', 'zz-two'])
        self.assertEqual(atlas.read(atlas.DATA / 'inbox.json')['franchiseScan']['ZZ Reihe']['queued'], 2)
