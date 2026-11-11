import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import atlas  # noqa: E402


class RemakeTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        shutil.copytree(atlas.DATA, self.tmp / 'data')
        self.orig = atlas.DATA
        atlas.DATA = self.tmp / 'data'

    def tearDown(self):
        atlas.DATA = self.orig
        shutil.rmtree(self.tmp)

    def test_no_remake_versions_left_and_links_valid(self):
        db = atlas.load_db()
        for g in db['games']:
            if not g.get('remakeOf'):
                self.assertFalse(len(g.get('versions', [])) > 1 and any(v.get('type') == 'remake' for v in g['versions']), g['id'])
        self.assertTrue(any(g.get('remakeOf') == 'the-legend-of-zelda-ocarina-of-time' for g in db['games']))

    def test_repair_splits_a_new_remake_version_with_its_way(self):
        path = atlas.DATA / 'games' / 'super-metroid.json'
        g = atlas.read(path)
        g['versions'].append({'id': 'zz-remake', 'name': 'Super Metroid Neo (2030)', 'type': 'remake', 'year': 2030, 'platforms': ['Nintendo Switch']})
        g['routes'].append({'id': 'zz-way', 'name': 'ZZ Weg', 'release': 'zz-remake', 'kind': 'emulation', 'targets': ['android'],
                            'verification': 'ai-unverified', 'links': [{'label': 'x', 'url': 'https://example.org/zz'}]})
        atlas.write(path, g)
        made = atlas.split_remakes(log=lambda *a: None)
        self.assertEqual(len(made), 1)
        new = atlas.read(atlas.DATA / 'games' / f'{made[0]}.json')
        self.assertEqual(new['remakeOf'], 'super-metroid')
        self.assertEqual(new['title'], 'Super Metroid Neo')
        self.assertEqual([r['id'] for r in new['routes']], ['zz-way'])
        self.assertEqual(new['routes'][0]['release'], new['versions'][0]['id'])
        old = atlas.read(path)
        self.assertNotIn('zz-remake', [v['id'] for v in old['versions']])
        self.assertNotIn('zz-way', [r['id'] for r in old['routes']])
        self.assertFalse(atlas.validate())

    def test_title_of_a_generic_remake_name(self):
        orig = {'title': "The Legend of Zelda: Link's Awakening"}
        self.assertEqual(atlas.remake_title(orig, {'name': 'Remake für Nintendo Switch (2019)', 'year': 2019, 'platforms': ['Nintendo Switch']}),
                         "The Legend of Zelda: Link's Awakening (2019)")
        self.assertEqual(atlas.remake_title({'title': 'The Legend of Zelda: Ocarina of Time'}, {'name': 'Ocarina of Time 3D (2011)', 'year': 2011}),
                         'The Legend of Zelda: Ocarina of Time 3D')


if __name__ == '__main__':
    unittest.main()
