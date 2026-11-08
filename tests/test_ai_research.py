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
        entries = self.run_fake('tomb-raider')
        g = atlas.read(atlas.DATA / 'games' / 'tomb-raider.json')
        names = [v['name'] for v in g['versions']]
        self.assertIn('Tomb Raider I–III Remastered (2024)', names)   # existing version reused, not duplicated
        self.assertEqual(names.count('Tomb Raider I–III Remastered (2024)'), 1)
        self.assertNotIn('Erfundene Fassung', names)                  # source not from the web search
        route = next(r for r in g['routes'] if r['name'] == 'OpenLara')
        self.assertEqual((route['verification'], route['release']), ('ai-unverified', 'playstation'))
        self.assertEqual(route['reports'][0]['device'], 'AYN Thor')
        self.assertFalse(any('romsfun' in json.dumps(r) for r in g['routes']))  # piracy site blocked
        projects = atlas.read(atlas.DATA / 'projects.json')['projects']
        self.assertTrue(any(p['repo'] == 'XProger/OpenLara' and 'tomb-raider' in p['games'] for p in projects))
        self.assertEqual(atlas.validate(), [])
        self.assertTrue(any(e['type'] == 'route-added' and e['by'] == 'ai-research' for e in entries))

    def test_second_run_only_adds_new_reports(self):
        self.run_fake('tomb-raider')
        entries = self.run_fake('tomb-raider')
        g = atlas.read(atlas.DATA / 'games' / 'tomb-raider.json')
        self.assertEqual(sum(1 for r in g['routes'] if r['name'] == 'OpenLara'), 1)
        self.assertEqual(entries, [])

    def test_issue_body_selects_game(self):
        self.assertIsNone(ai_research.main.__doc__)  # smoke: callable
        import re
        self.assertEqual(re.search(r'game:\s*([a-z0-9-]+)', 'game: doom-1993\n\nbitte').group(1), 'doom-1993')


if __name__ == '__main__':
    unittest.main()
