"""Index expansion must stay title-only, deduplicated and non-compatible by design."""
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from expand_index import merge

class IndexExpansionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalog=json.loads((ROOT/'data/catalog.json').read_text())
        cls.seeds=json.loads((ROOT/'data/index_seeds_v051.json').read_text())

    def test_index_expansion_is_idempotent(self):
        data,stats=merge(self.catalog,self.seeds)
        self.assertEqual(stats['added'],0)
        self.assertEqual(len(data['gameIndex']),len(self.catalog['gameIndex']))

    def test_index_has_multiple_handheld_platforms_and_no_false_routes(self):
        self.assertGreaterEqual(len(self.catalog['games'])+len(self.catalog['gameIndex']),650)
        platforms={p for g in self.catalog['gameIndex'] for p in g['platforms']}
        for p in ('PSP','Wii','Nintendo GameCube','Dreamcast','PlayStation Vita','Sega Mega Drive'):
            self.assertIn(p,platforms)
        self.assertTrue(all('routes' not in g for g in self.catalog['gameIndex']))
        self.assertEqual(len(self.catalog['games']),41)

    def test_known_edition_and_id_are_never_overwritten(self):
        seed={'platforms':{'PSP':['An Existing Game','A New Game'],'Dreamcast':['A New Game']}}
        c={'games':[{'id':'existing-game','title':'An Existing Game','routes':[{'id':'test'}]}],
           'gameIndex':[]}
        out,result=merge(c,seed)
        self.assertEqual(result['added'],1)
        self.assertEqual(out['gameIndex'][0]['platforms'],['PSP','Dreamcast'])
        self.assertNotIn('routes',out['gameIndex'][0])

    def test_known_morrowind_mods_have_project_and_evidence(self):
        data=json.loads((ROOT/'data/game_addons.json').read_text())['games']['morrowind']
        self.assertGreaterEqual(len(data),4)
        self.assertTrue(all(x['projectUrl'].startswith('https://') and x['evidence'].startswith('https://') for x in data))
        self.assertTrue(all(x['thorStatus']=='unknown' for x in data))

if __name__=='__main__':unittest.main()
