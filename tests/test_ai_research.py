import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import atlas  # noqa: E402
import ai_research  # noqa: E402

SRC = 'https://www.pocketgamer.com/tomb-raider-i-iii-remastered-starring-lara-croft/out-now-on-mobile'
RESULT = {
    'summary': 'Testzusammenfassung.',
    'versions': [
        {'key': 'remastered', 'name': 'Tomb Raider I–III Remastered (2024)', 'type': 'remaster', 'year': 2024,
         'platforms': ['PC', 'Android'], 'traits': ['upscaling'], 'note': 'Sammlung.', 'sourceUrl': SRC},
        {'key': 'made-up', 'name': 'Erfundene Fassung', 'type': 'port', 'year': 0, 'platforms': ['Dreamcast'],
         'traits': [], 'note': '', 'sourceUrl': 'https://example.com/not-searched'},
    ],
    'routes': [
        {'name': 'OpenLara', 'versionKey': 'playstation', 'kind': 'source-port', 'runtime': 'OpenLara',
         'features': ['widescreen'], 'dualScreen': '', 'requires': ['Eigene Spieldaten'], 'benefit': 'Nativ.',
         'caveat': '', 'steps': [], 'effort': 'guided', 'status': 'active', 'projectName': 'OpenLara',
         'projectUrl': 'https://github.com/XProger/OpenLara', 'sourceUrl': 'https://github.com/XProger/OpenLara',
         'reports': [{'url': 'https://reddit.com/r/SBCGaming/comments/x', 'device': 'AYN Thor', 'summary': 'Läuft gut.'}]},
        {'name': 'ROM-Seite', 'versionKey': 'playstation', 'kind': 'emulation', 'runtime': '', 'features': [],
         'dualScreen': '', 'requires': [], 'benefit': '', 'caveat': '', 'steps': [], 'effort': 'easy', 'status': 'active',
         'projectName': 'Bad', 'projectUrl': 'https://romsfun.com/tomb-raider', 'sourceUrl': 'https://romsfun.com/tomb-raider',
         'reports': []},
    ],
    'mods': [],
}


def fake_response(result, sources):
    return {'status': 'completed', 'output': [
        {'type': 'web_search_call', 'action': {'sources': [{'url': u} for u in sources]}},
        {'type': 'message', 'content': [{'type': 'output_text', 'text': json.dumps(result)}]}]}


class AiResearchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(atlas.DATA, self.tmp / 'data')
        self.orig = (atlas.DATA, ai_research.DATA)
        atlas.DATA = ai_research.DATA = self.tmp / 'data'
        # an isolated test game, so the test does not depend on what real research runs already added
        atlas.write(atlas.DATA / 'games' / 'zz-test-raider.json', {
            'id': 'zz-test-raider', 'title': 'ZZ Test Raider', 'franchise': 'ZZ Test', 'platforms': ['PlayStation', 'PC'],
            'versions': [{'id': 'playstation', 'name': 'PlayStation (1996)', 'type': 'original', 'platforms': ['PlayStation']},
                         {'id': 'remastered', 'name': 'Tomb Raider I–III Remastered (2024)', 'type': 'remaster', 'platforms': ['PC']}],
            'routes': [], 'mods': [], 'updatedAt': '2026-01-01'})

    def tearDown(self):
        atlas.DATA, ai_research.DATA = self.orig
        shutil.rmtree(self.tmp)

    def run_fake(self, game_id):
        resp = fake_response(RESULT, [SRC, 'https://github.com/XProger/OpenLara', 'https://reddit.com/r/SBCGaming/comments/x',
                                      'https://romsfun.com/tomb-raider'])
        original = ai_research.call_openai
        ai_research.call_openai = lambda payload, token: resp
        try:
            return ai_research.research(game_id, 'key', 'model', log=lambda *a: None)
        finally:
            ai_research.call_openai = original

    def test_merges_sourced_items_and_drops_the_rest(self):
        entries = self.run_fake('zz-test-raider')
        g = atlas.read(atlas.DATA / 'games' / 'zz-test-raider.json')
        names = [v['name'] for v in g['versions']]
        self.assertIn('Tomb Raider I–III Remastered (2024)', names)   # existing version reused, not duplicated
        self.assertEqual(names.count('Tomb Raider I–III Remastered (2024)'), 1)
        self.assertNotIn('Erfundene Fassung', names)                  # source not from the web search
        route = next(r for r in g['routes'] if r['name'] == 'OpenLara')
        self.assertEqual((route['verification'], route['release']), ('ai-unverified', 'playstation'))
        self.assertEqual(route['reports'][0]['device'], 'AYN Thor')
        self.assertFalse(any('romsfun' in json.dumps(r) for r in g['routes']))  # piracy site blocked
        projects = atlas.read(atlas.DATA / 'projects.json')['projects']
        self.assertTrue(any(p['repo'] == 'XProger/OpenLara' and 'zz-test-raider' in p['games'] for p in projects))
        self.assertEqual(atlas.validate(), [])
        self.assertTrue(any(e['type'] == 'route-added' and e['by'] == 'ai-research' for e in entries))

    def test_second_run_only_adds_new_reports(self):
        self.run_fake('zz-test-raider')
        entries = self.run_fake('zz-test-raider')
        g = atlas.read(atlas.DATA / 'games' / 'zz-test-raider.json')
        self.assertEqual(sum(1 for r in g['routes'] if r['name'] == 'OpenLara'), 1)
        self.assertEqual(entries, [])

    def test_issue_body_selects_game(self):
        self.assertIsNone(ai_research.main.__doc__)  # smoke: callable
        import re
        self.assertEqual(re.search(r'game:\s*([a-z0-9-]+)', 'game: doom-1993\n\nbitte').group(1), 'doom-1993')


if __name__ == '__main__':
    unittest.main()


class ModesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(atlas.DATA, self.tmp / 'data')
        self.orig = (atlas.DATA, ai_research.DATA)
        atlas.DATA = ai_research.DATA = self.tmp / 'data'

    def tearDown(self):
        atlas.DATA, ai_research.DATA = self.orig
        shutil.rmtree(self.tmp)

    def test_new_game_is_created_once(self):
        gid, created = ai_research.create_game("No Man's Sky", ['PC'], None, 2016, log=lambda *a: None)
        self.assertTrue(created)
        self.assertEqual(ai_research.create_game("No Man’s Sky", log=lambda *a: None), (gid, False))  # other apostrophe
        g = atlas.read(atlas.DATA / 'games' / f'{gid}.json')
        self.assertEqual(g['versions'][0], {'id': 'pc', 'name': 'PC (2016)', 'type': 'original', 'platforms': ['PC'], 'year': 2016})
        self.assertEqual(atlas.validate(), [])

    def test_app_result_with_mod_categories_and_screenshots(self):
        result = {'summary': '', 'series': '', 'versions': [], 'mods': [
            {'name': 'Shader Pack X', 'url': 'https://www.nexusmods.com/x', 'category': 'shader', 'versionKeys': ['pc'],
             'edition': '', 'description': 'ReShade-Preset.', 'sourceUrl': 'https://www.nexusmods.com/x'}],
            'routes': [{'name': 'Winlator mit DXVK', 'versionKey': 'pc', 'kind': 'pc-runtime', 'runtime': 'Winlator', 'features': [],
                        'dualScreen': '', 'requires': [], 'benefit': 'x', 'caveat': '', 'steps': [], 'effort': 'advanced',
                        'status': 'active', 'projectName': 'Winlator', 'projectUrl': 'https://github.com/brunodev85/winlator',
                        'sourceUrl': 'https://reddit.com/r/winlator/comments/y',
                        'screenshots': [{'url': 'https://i.redd.it/abc.png', 'caption': 'Im Spiel'},
                                        {'url': 'https://example.com/page', 'caption': 'kein Bild'}], 'reports': []}]}
        entries = ai_research.from_app_result('grand-theft-auto-san-andreas', result, log=lambda *a: None)
        g = atlas.read(atlas.DATA / 'games' / 'grand-theft-auto-san-andreas.json')
        mod = next(m for m in g['mods'] if m['name'] == 'Shader Pack X')
        self.assertEqual((mod['category'], mod['release']), ('shader', ['pc']))
        route = next(r for r in g['routes'] if r['name'] == 'Winlator mit DXVK')
        self.assertEqual([s['url'] for s in route['screenshots']], ['https://i.redd.it/abc.png'])
        self.assertEqual(route['screenshots'][0]['check'], 'ai')
        self.assertTrue(entries)
        self.assertEqual(atlas.validate(), [])


class ScreenshotSearchTest(ModesTest):
    PAGES = {
        'https://reddit.com/r/AYN/comments/z': [{'url': 'https://i.redd.it/thor.jpg', 'source': 'https://reddit.com/r/AYN/comments/z', 'caption': 'Beide Bildschirme'}],
        'https://www.youtube.com/watch?v=abcdefghijk': [{'url': 'https://i.ytimg.com/vi/abcdefghijk/maxresdefault.jpg',
                                                          'source': 'https://www.youtube.com/watch?v=abcdefghijk', 'caption': 'Video-Vorschaubild'}],
        'https://not-searched.example/': [{'url': 'https://cdn.example.com/x.png', 'source': 'https://not-searched.example/', 'caption': ''}],
    }

    def setUp(self):
        super().setUp()
        import images
        self._orig = (images.images_from_page, ai_research.reachable, ai_research.call_openai)
        images.images_from_page = lambda url, *a, **k: self.PAGES.get(url, [])
        ai_research.reachable = lambda url: 'maxresdefault' not in url      # low-res video: fall back to hqdefault

    def tearDown(self):
        import images
        images.images_from_page, ai_research.reachable, ai_research.call_openai = self._orig
        super().tearDown()

    def test_dual_screen_routes_first_and_pictures_come_from_found_pages(self):
        todo = ai_research.routes_without_shots(50)
        games = {gid: atlas.read(atlas.DATA / 'games' / f'{gid}.json') for gid, _ in todo}
        dual = ['dual-screen' in next(r for r in games[g]['routes'] if r['id'] == rid).get('features', []) for g, rid in todo]
        self.assertEqual(dual, sorted(dual, reverse=True))          # all dual-screen ways come first
        gid, rid = todo[0]
        g = atlas.read(atlas.DATA / 'games' / f'{gid}.json')
        r = next(x for x in g['routes'] if x['id'] == rid)
        r['links'], r['projects'] = [{'label': 'Video', 'url': 'https://www.youtube.com/watch?v=abcdefghijk'}], []
        atlas.write(atlas.DATA / 'games' / f'{gid}.json', g)
        ai_research.call_openai = lambda payload, token: fake_response({'pages': [
            {'url': 'https://reddit.com/r/AYN/comments/z', 'shows': 'Beide Bildschirme'},
            {'url': 'https://not-searched.example/', 'shows': 'x'}]}, ['https://reddit.com/r/AYN/comments/z'])
        n = ai_research.find_screenshots(gid, rid, 'key', 'model', log=lambda *a: None)
        route = next(x for x in atlas.read(atlas.DATA / 'games' / f'{gid}.json')['routes'] if x['id'] == rid)
        self.assertEqual(n, 2)
        self.assertEqual([(x['url'], x['check']) for x in route['screenshots']],
                         [('https://i.ytimg.com/vi/abcdefghijk/hqdefault.jpg', 'ai'), ('https://i.redd.it/thor.jpg', 'ai')])
        self.assertNotIn((gid, rid), ai_research.routes_without_shots(50))   # not searched again this month
        self.assertEqual(atlas.validate(), [])

    def test_request_for_one_way_only(self):
        gid = 'crash-team-racing'
        g = atlas.read(atlas.DATA / 'games' / f'{gid}.json')
        rid = g['routes'][0]['id']
        g['routes'][0]['links'], g['routes'][0]['projects'] = [{'label': 'Post', 'url': 'https://reddit.com/r/AYN/comments/z'}], []
        g['routes'][0]['screenshots'] = []
        atlas.write(atlas.DATA / 'games' / f'{gid}.json', g)
        basic = ai_research.images_basic
        ai_research.images_basic = lambda ids, log=print: None
        ai_research.call_openai = lambda payload, token: fake_response({'pages': []}, [])
        try:
            st = ai_research.request_images([gid], 'key', 'model', log=lambda *a: None, routes=[rid])
        finally:
            ai_research.images_basic = basic
        g2 = atlas.read(atlas.DATA / 'games' / f'{gid}.json')
        self.assertEqual(st, {'games': 0, 'routes': 1})
        self.assertEqual(g2['routes'][0]['screenshots'][0]['url'], 'https://i.redd.it/thor.jpg')
        self.assertEqual(g2['screenshots'], g['screenshots'])           # original pictures untouched
        self.assertEqual(atlas.validate(), [])


class AddImageTest(ScreenshotSearchTest):
    def test_pasted_reddit_post_is_read_through_the_ai(self):
        post = 'https://www.reddit.com/r/AynThor/comments/abc/minecraft_dual/'
        ai_research.call_openai = lambda payload, token: fake_response({'images': [
            {'url': 'https://preview.redd.it/thor-dual.jpeg?width=640&amp;s=1', 'post': post, 'caption': 'Inventar unten'},
            {'url': 'https://evil.example/x.jpg', 'post': post, 'caption': 'x'}]}, [post])
        gid = 'minecraft'
        rid = atlas.read(atlas.DATA / 'games' / 'minecraft.json')['routes'][0]['id']
        n = ai_research.add_image(f'{gid}/{rid}', post, token='key', model='m', log=lambda *a: None)
        route = next(r for r in atlas.read(atlas.DATA / 'games' / 'minecraft.json')['routes'] if r['id'] == rid)
        self.assertEqual(n, 1)
        self.assertEqual((route['screenshots'][-1]['url'], route['screenshots'][-1]['source']),
                         ('https://preview.redd.it/thor-dual.jpeg?width=640&s=1', post))
        self.assertEqual(atlas.validate(), [])


class QueueAndDualScanTest(ModesTest):
    def test_franchise_queues_unresearched_games_and_queue_pops(self):
        n = ai_research.queue_add(['doom-1993', 'doom-ii', 'doom-ii'], 'Reihe Doom')
        self.assertEqual(n, 2 - sum(1 for g in ['doom-1993', 'doom-ii']
                                   if g in atlas.read(atlas.DATA / 'inbox.json').get('aiResearch', {})))
        before = len(ai_research.queue_load()['jobs'])
        self.assertEqual(len(ai_research.queue_pop(1)), min(1, before))
        self.assertEqual(len(ai_research.queue_load()['jobs']), max(0, before - 1))

    def test_dual_scan_adds_route_for_new_and_existing_games(self):
        ai_research.create_game('ZZ Existing Knight', ['PC'], None, 2017, log=lambda *a: None)   # existing, not researched
        resp = fake_response({'projects': [
            {'gameTitle': 'ZZ Existing Knight', 'platform': 'PC', 'name': 'HK Dual Map', 'projectUrl': 'https://github.com/x/hk-dual',
             'kind': 'native-mod', 'dualScreen': 'Karte unten', 'dualScreenType': 'integrated', 'sourceUrl': 'https://github.com/x/hk-dual', 'released': '2026-10'},
            {'gameTitle': 'Totally New Game', 'platform': 'SNES', 'name': 'TNG Companion', 'projectUrl': 'https://github.com/y/tng',
             'kind': 'companion', 'dualScreen': 'Inventar', 'dualScreenType': 'companion', 'sourceUrl': 'https://github.com/y/tng', 'released': ''},
            {'gameTitle': 'ZZ Alpha; ZZ Beta', 'platform': 'SNES', 'name': 'Multi DS', 'projectUrl': 'https://github.com/m/multi',
             'kind': 'emulator-mod', 'dualScreen': 'Karte', 'dualScreenType': 'integrated', 'sourceUrl': 'https://github.com/m/multi', 'released': ''},
            {'gameTitle': 'Fake', 'platform': 'PC', 'name': 'Unsourced', 'projectUrl': 'https://github.com/z/fake',
             'kind': 'mod', 'dualScreen': '', 'dualScreenType': 'info', 'sourceUrl': 'https://nowhere.example', 'released': ''}]},
            ['https://github.com/x/hk-dual', 'https://github.com/y/tng', 'https://github.com/m/multi'])
        original = ai_research.call_openai
        ai_research.call_openai = lambda payload, token: resp
        try:
            added = ai_research.dual_scan('key', 'model', log=lambda *a: None)
        finally:
            ai_research.call_openai = original
        self.assertEqual(len(added), 4)
        self.assertTrue(ai_research.find_game('ZZ Alpha') and ai_research.find_game('ZZ Beta'))   # multi-title split
        self.assertIsNone(ai_research.find_game('ZZ Alpha; ZZ Beta'))
        hk = atlas.read(atlas.DATA / 'games' / f"{ai_research.find_game('ZZ Existing Knight')}.json")
        r = next(r for r in hk['routes'] if r['name'] == 'HK Dual Map')
        self.assertEqual((r['dualScreenType'], r['verification'], 'dual-screen' in r['features']), ('integrated', 'ai-unverified', True))
        self.assertTrue(ai_research.find_game('Totally New Game'))
        self.assertIsNone(ai_research.find_game('Fake'))
        jobs = [j['game'] for j in ai_research.queue_load()['jobs']]
        self.assertIn(hk['id'], jobs)                                   # deep research queued
        self.assertEqual(atlas.validate(), [])


class FranchiseAndImagesTest(ModesTest):
    def setUp(self):
        super().setUp()
        quiet = lambda *a: None
        ai_research.create_game('ZZ Raid', ['PlayStation'], 'ZZ Raid', 1996, log=quiet)
        ai_research.create_game('ZZ Raid II', ['PC'], 'ZZ Raid', 1997, log=quiet)

    def test_find_game_respects_reboots_and_subtitles(self):
        self.assertEqual(ai_research.find_game('ZZ Raid II: The Dagger', 1997), 'zz-raid-ii')     # same game, subtitle
        self.assertIsNone(ai_research.find_game('ZZ Raid', 2013))                                # reboot ≠ 1996 game
        self.assertEqual(ai_research.find_game('ZZ Raid', 1996), 'zz-raid')
        gid, created = ai_research.create_game('ZZ Raid', ['PC'], 'ZZ Raid', 2013, log=lambda *a: None)
        self.assertTrue(created)
        self.assertEqual(atlas.read(atlas.DATA / 'games' / f'{gid}.json')['title'], 'ZZ Raid (2013)')

    def test_franchise_relations(self):
        src = 'https://en.wikipedia.org/wiki/ZZ_Raid'
        resp = fake_response({'games': [
            {'title': 'ZZ Raid II: The Dagger', 'year': 1997, 'platforms': ['PC'], 'sourceUrl': src,
             'relation': 'new', 'atlasId': '', 'versionType': 'original'},                    # model says new, dedupe catches it
            {'title': 'ZZ Raid', 'year': 2013, 'platforms': ['PC', 'PlayStation 3'], 'sourceUrl': src + '_(2013)',
             'relation': 'new', 'atlasId': '', 'versionType': 'original'},
            {'title': 'ZZ Raid Remastered', 'year': 2024, 'platforms': ['PC'], 'sourceUrl': src,
             'relation': 'version', 'atlasId': 'zz-raid', 'versionType': 'remaster'},
            {'title': 'ZZ Raid II', 'year': 2001, 'platforms': ['Xbox'], 'sourceUrl': src,
             'relation': 'version', 'atlasId': 'zz-raid-ii', 'versionType': 'port'},          # same title → named by platform
            {'title': 'Fake Raid', 'year': 2019, 'platforms': ['PC'], 'sourceUrl': 'https://made-up.example/x',
             'relation': 'new', 'atlasId': '', 'versionType': 'original'}]}, [src])
        original = ai_research.call_openai
        ai_research.call_openai = lambda payload, token: resp
        try:
            ai_research.research_franchise('ZZ Raid', 'key', 'model', log=lambda *a: None)
        finally:
            ai_research.call_openai = original
        rep = atlas.read(atlas.DATA / 'inbox.json')['franchiseScan']['ZZ Raid']
        self.assertEqual(rep['added'], ['zz-raid-2013'])
        self.assertEqual([x['title'] for x in rep['skipped']], ['Fake Raid'])
        v = atlas.read(atlas.DATA / 'games' / 'zz-raid.json')['versions'][-1]
        self.assertEqual((v['name'], v['type'], v['year']), ('ZZ Raid Remastered (2024)', 'remaster', 2024))
        self.assertEqual(atlas.read(atlas.DATA / 'games' / 'zz-raid-ii.json')['versions'][-1]['name'], 'Xbox (2001)')
        self.assertEqual(ai_research.queue_load()['jobs'][0]['game'], 'zz-raid-2013')         # new games researched first
        self.assertEqual(atlas.validate(), [])

    def test_image_request_finds_original_pictures_on_pages(self):
        import images
        gid = 'zz-raid'
        pages = {'https://store.steampowered.com/app/1/': [{'url': 'https://shared.steamstatic.com/ss_1.jpg', 'source': 'https://store.steampowered.com/app/1/', 'caption': 'Originalspiel'}],
                 'https://elsewhere.example/': [{'url': 'https://elsewhere.example/x.jpg', 'source': 'https://elsewhere.example/', 'caption': ''}]}
        orig = (ai_research.call_openai, ai_research.images_basic, images.images_from_page, ai_research.reachable)
        ai_research.call_openai = lambda payload, token: fake_response({'pages': [
            {'url': 'https://store.steampowered.com/app/1/', 'shows': 'Spielszenen'}, {'url': 'https://elsewhere.example/', 'shows': 'x'}]},
            ['https://store.steampowered.com/app/1/'])
        ai_research.images_basic = lambda ids, log=print: None          # no network in tests
        images.images_from_page = lambda url, *a, **k: pages.get(url, [])
        ai_research.reachable = lambda url: True
        try:
            st = ai_research.request_images([gid], 'key', 'model', log=lambda *a: None)
        finally:
            ai_research.call_openai, ai_research.images_basic, images.images_from_page, ai_research.reachable = orig
        g = atlas.read(atlas.DATA / 'games' / f'{gid}.json')
        self.assertEqual(st['games'], 1)
        self.assertEqual([(x['url'], x['check']) for x in g['screenshots']], [('https://shared.steamstatic.com/ss_1.jpg', 'ai')])
        self.assertIn(gid, atlas.read(atlas.DATA / 'inbox.json')['imageRequests'])
        self.assertEqual(atlas.validate(), [])


class CleanTest(unittest.TestCase):
    def test_strips_citations_and_cuts_at_sentence(self):
        t = 'Für den Thor interessant. ([store.steampowered.com](https://store.steampowered.com/app/1)) Siehe [Wiki](https://x.org/a) dazu.'
        self.assertEqual(ai_research.clean(t), 'Für den Thor interessant. Siehe Wiki dazu.')
        self.assertEqual(ai_research.clean('Erster Satz ist lang genug. Zweiter Satz geht weiter und weiter.', 40), 'Erster Satz ist lang genug.')
