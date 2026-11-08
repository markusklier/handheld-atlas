"""Integration guardrails for new repo and media discovery and CC0 index import."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from discover_repositories import QUERIES, candidates_from_search, update_state
from discover_media import candidates_from_readme
from import_wikidata import extract, update_catalog
ROOT=Path(__file__).resolve().parents[1]

class DiscoveryTests(unittest.TestCase):
    def test_repo_search_is_pending_not_published(self):
        sample=[{'full_name':'sample/Thor-DualScreen','description':'Dual-screen emulator companion','pushed_at':'2026-11-06T00:00:00Z','topics':['ayn-thor']},
                {'full_name':'spam/foo','description':'unrelated'}]
        urls=candidates_from_search(sample,'2026-11-08')
        self.assertEqual(len(urls),1)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir()
            (root/'data/catalog.json').write_text(json.dumps({'sources':[]}))
            (root/'data/candidates.json').write_text(json.dumps({'candidates':[]}))
            n=update_state({QUERIES[0]:sample},root=root)
            self.assertEqual(n,1)
            candidate=json.loads((root/'data/candidates.json').read_text())['candidates'][0]
            self.assertEqual(candidate['status'],'pending')
            self.assertIsNone(candidate['gameId'])
            self.assertEqual(update_state({QUERIES[0]:sample},root=root),0)

    def test_project_media_parses_exact_game_headings_and_screenshots(self):
        readme='''## Supported Games\n| (table) |\n## Metroid Dread\n| <img src="screenshots/metroid-dread/map.png" width="300" alt="Metroid Dread: Map"> |\n| <img src="screenshots/metroid-dread/emmi.png" alt="EMMI" width="300"> |\n## Unrelated Title\n<img src="screenshots/misc/example.png" alt="wrong game">\n'''
        catalog={'games':[{'id':'metroid-dread','title':'Metroid Dread'}]}
        shots=candidates_from_readme(readme,catalog)
        self.assertEqual(len(shots),2)
        self.assertTrue(all(s['gameId']=='metroid-dread' and s['reviewStatus']=='needs-media-review' for s in shots))

    def test_wikidata_import_keeps_route_catalog_untouched_and_dedupes_qid(self):
        payload={'results':{'bindings':[{'item':{'value':'https://www.wikidata.org/entity/Q987654321'},
                'itemLabel':{'value':'Test Game 64'},'seriesLabel':{'value':'Test Franchise'}},
                {'item':{'value':'https://www.wikidata.org/entity/Q99999'},'itemLabel':{'value':'Q99999'}}]}}
        items=extract(payload,'Nintendo 64')
        self.assertEqual(len(items),1)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'data').mkdir()
            old={'games':[{'id':'other','title':'Other','routes':[{'id':'route-1'}]}],'gameIndex':[]}
            (root/'data/catalog.json').write_text(json.dumps(old))
            self.assertEqual(update_catalog(root,items),1)
            self.assertEqual(update_catalog(root,items),0)
            new=json.loads((root/'data/catalog.json').read_text())
            self.assertEqual(new['games'],old['games'])
            self.assertTrue(new['gameIndex'][0]['unverified'])
            self.assertEqual(new['gameIndex'][0]['platforms'],['Nintendo 64'])

if __name__=='__main__':unittest.main()
