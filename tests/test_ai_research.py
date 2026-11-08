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
