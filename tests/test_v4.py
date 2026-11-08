"""Atlas 0.4 validation: no false compatibility claims, fixture leakage or unsafe image URLs."""
import hashlib
import json
import sys
import unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from atlas_v4 import make_index, media_url, project_url
from ai_agents import choose_game, run_research, validate_vision, vision_queue

CAT = json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))

class AtlasV4Tests(unittest.TestCase):
    def test_project_nodes_connect_routes_but_are_not_device_tests(self):
        out=make_index(CAT,{'candidates':[]},{'candidates':[]},{'findings':[]},{'results':{}},stamp='2026-11-08T00:00:00Z')
        self.assertGreater(out['totalProjects'], 0)
        known=[p for p in out['projects'] if p['curated']]
        self.assertTrue(any('minecraft' in p['gameIds'] for p in known))
        self.assertTrue(all(p['deviceTest']=='not-tested' for p in out['projects']))
        self.assertEqual(out['discoveredCount'],0)

    def test_live_candidate_image_surfaces_as_unverified_and_deduplicates_project(self):
        image='https://raw.githubusercontent.com/example/demo/main/shots/screen.png'
        hit={'gameId':'minecraft','provider':'github','project':'Demo Dual Screen','url':'https://github.com/example/demo',
             'status':'pending-review','discoveryMode':'live','firstSeenAt':'2026-11-08T01:00:00Z',
             'evidence':[{'sourceUrl':'https://github.com/example/demo/blob/main/README.md','excerpt':'A second screen companion for Minecraft'}],
             'mediaCandidates':[{'url':image,'sourceUrl':'https://github.com/example/demo','caption':'Dual screen'}]}
        key=hashlib.sha256(image.encode()).hexdigest()[:20]
        out=make_index(CAT,{'candidates':[hit,hit]}, {'candidates':[]},{'findings':[]},
                       {'results':{key:{'verdict':'plausible'}}},stamp='2026-11-08T02:00:00Z')
        lead=next(p for p in out['projects'] if p['url']=='https://github.com/example/demo')
        self.assertEqual(lead['gameIds'],['minecraft'])
        self.assertEqual(len(lead['media']),1)
        self.assertEqual(lead['media'][0]['rights'],'not-cleared')
        self.assertEqual(lead['media'][0]['vision'],'plausible')
        self.assertEqual(lead['deviceTest'],'not-tested')

    def test_fixture_results_do_not_become_news(self):
        fixture={'gameId':'minecraft','provider':'github','project':'Made up','url':'https://github.com/foo/bar',
                 'discoveryMode':'fixture','evidence':[{'sourceUrl':'https://github.com/foo/bar','excerpt':'demo'}]}
        out=make_index(CAT,{'candidates':[fixture]},{'candidates':[]},{'findings':[]},{'results':{}},stamp='2026-11-08T00:00:00Z')
        self.assertFalse(any(p['url']=='https://github.com/foo/bar' for p in out['projects']))

    def test_unsafe_image_and_urls_rejected(self):
        self.assertIsNone(project_url('https://evil.example/projects/example'))
        self.assertIsNone(media_url('https://127.0.0.1:8000/hacked.png'))
        self.assertIsNone(media_url('https://raw.githubusercontent.com/owner/repo/image.svg'))
        self.assertIsNone(media_url('http://raw.githubusercontent.com/owner/repo/img.png'))

    def test_web_leads_require_real_websearch_citation(self):
        game={'id':'minecraft','title':'Minecraft'}
        answer={'output':[{'type':'message','content':[{'type':'output_text','text':json.dumps({'findings':[
            {'name':'A','url':'https://github.com/foo/a','sourceUrl':'https://github.com/foo/a','excerpt':'some claim'},
            {'name':'B','url':'https://github.com/foo/b','sourceUrl':'https://github.com/foo/b','excerpt':'unsupported claim'}]})}]}],
            'type':'responses'}
        output,count=run_research(game,answer,{'findings':[],'scanTimes':{}},'2026-11-08T00:00:00Z')
        self.assertEqual(count,0)
        answer['output'].append({'type':'web_search_call','action':{'sources':[{'url':'https://github.com/foo/a'}]}})
        output,count=run_research(game,answer,{'findings':[],'scanTimes':{}},'2026-11-08T00:00:00Z')
        self.assertEqual(count,1)
        self.assertTrue(output['findings'][0]['notTested'])

    def test_dynamic_rotation_reaches_watchlist_index(self):
        game=choose_game(CAT, {'scanTimes':{g['id']:'2026-11-08' for g in CAT['games']}})
        self.assertIn(game['id'], {g['id'] for g in CAT['gameIndex']})

    def test_vision_is_only_plausibility_not_rights(self):
        self.assertEqual(validate_vision({'gameMatch':'yes','imageType':'gameplay'}),'plausible')
        self.assertEqual(validate_vision({'gameMatch':'no','imageType':'gameplay'}),'mismatch')
        self.assertEqual(validate_vision({'gameMatch':'yes','imageType':'mockup'}),'mismatch')
        self.assertEqual(validate_vision({}),'unclear')
        fixture={'candidates':[{'discoveryMode':'fixture','mediaCandidates':[{'url':'https://raw.githubusercontent.com/foo/a/main/img.png'}]}]}
        self.assertEqual(vision_queue(fixture,{'results':{}},2),[])

    def test_built_html_embeds_project_data(self):
        source=(ROOT/'src/template.html').read_text(encoding='utf-8')
        self.assertIn('/*__PROJECTS__*/',source)
        self.assertIn('data/projects.json',(ROOT/'scripts/build.py').read_text(encoding='utf-8'))

if __name__=='__main__': unittest.main()
