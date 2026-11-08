"""Data contracts and safety for game-specific multi-provider research."""
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from deep_research import (run,canonical_url,safe_project_image,image_candidates,
                           from_github,from_modrinth,merge, research_queries,from_lead)
from quality_audit import report
from triage_media import triage
from validate_agent_findings import validate_findings
ROOT=Path(__file__).resolve().parents[1]
catalog=json.loads((ROOT/'data/catalog.json').read_text(encoding='utf-8'))
mc=next(x for x in catalog['games'] if x['id']=='minecraft')
targets=json.loads((ROOT/'data/research_targets.json').read_text())['targets']
fixture=json.loads((ROOT/'fixtures/minecraft_research.json').read_text())
leads=json.loads((ROOT/'fixtures/minecraft_leads.json').read_text())

class DeepResearchTest(unittest.TestCase):
    def test_search_has_game_specific_providers(self):
        qs=research_queries(mc,targets['minecraft'])
        self.assertTrue(any('DroidBridge' in x for x in qs['github']))
        self.assertTrue(qs['modrinth'] and qs['curseforge'])

    def test_research_fixture_deduplicates_across_sources(self):
        q,added=run([mc],targets,fixture,False,leads,{'schemaVersion':1,'candidates':[],'runs':[]},budget=8)
        self.assertEqual(added,5)  # Duplicate CurseForge lead collapses to one project URL
        self.assertEqual(len(q['candidates']),5)
        self.assertEqual(q['runs'][0]['mode'],'fixture')
        self.assertEqual(q['runs'][0]['result'],'fixture-only')
        self.assertTrue(all(c['status']=='pending-review' and c['notTested'] for c in q['candidates']))
        self.assertTrue(any('1.21.11' in c['versionsMentioned'] for c in q['candidates']))
        self.assertTrue(any('1.21.1' in c['versionsMentioned'] for c in q['candidates']))
        self.assertEqual(len(mc['routes']),7)
        q2,n=run([mc],targets,fixture,False,leads,q,budget=8)
        self.assertEqual(n,0)
        self.assertEqual(len(q2['candidates']),5)

    def test_project_names_not_random_claims(self):
        irrelevant={'full_name':'example/AndroidWeatherApp','name':'Weather App','description':'Android weather HUD and charts'}
        self.assertIsNone(from_github(mc,targets['minecraft'],irrelevant,'q'))
        hit={'full_name':'example/minecraft-ds','name':'minecraft-ds','description':'Minecraft dual-screen companion'}
        item=from_github(mc,targets['minecraft'],hit,'q', '# Setup\nNeeds Minecraft 1.21.11 and Fabric API for a second screen.\n')
        self.assertIsNotNone(item)
        self.assertIn('fabric',item['loadersMentioned'])
        self.assertIn('1.21.11',item['versionsMentioned'])

    def test_modrinth_candidate_never_promotes_installation(self):
        hit={'title':'Dual Screen Hud','description':'Client Minecraft dual-screen mod','slug':'dual-screen-hud','versions':['1.21.11'], 'categories':['fabric']}
        c=from_modrinth(mc,targets['minecraft'],hit,'dual screen')
        self.assertEqual(c['provider'],'modrinth')
        self.assertEqual(c['status'],'pending-review')
        self.assertTrue(c['notTested'])

    def test_modrinth_search_gallery_provides_source_linked_candidates(self):
        hit={'title':'Dual Screen HUD', 'description':'Second display on Android handheld',
             'slug':'dual-screen-hud', 'versions':['1.21.11'], 'categories':['fabric'],
             'gallery':['https://cdn.modrinth.com/data/abc/images/dual.png',
                        'https://evil.example/tracker.png']}
        item=from_modrinth(mc,targets['minecraft'],hit,'dual screen')
        self.assertEqual(len(item['mediaCandidates']),1)
        self.assertEqual(item['mediaCandidates'][0]['sourceUrl'],item['url'])
        self.assertEqual(item['mediaCandidates'][0]['reviewStatus'],'needs-context-and-rights-review')

    def test_urls_images_and_markdown_are_safely_limited(self):
        self.assertEqual(canonical_url('https://www.curseforge.com/minecraft/mc-mods/dual-screen?utm_source=foo'),
                         'https://www.curseforge.com/minecraft/mc-mods/dual-screen')
        self.assertIsNone(canonical_url('http://127.0.0.1/private'))
        self.assertIsNone(safe_project_image('https://evil.example/download.png','example/project'))
        self.assertIsNone(safe_project_image('../private.png','example/project'))
        images=image_candidates('# Demo\n![Image](screenshots/example.png)\n![bad](../../secret.jpg)\n![external](https://evil.example/file.png)',
             'example/project','https://github.com/example/project')
        self.assertEqual(len(images),1)
        self.assertEqual(images[0]['reviewStatus'],'needs-context-and-rights-review')

    def test_reviewer_status_survives_repeat_discovery(self):
        sample={'id':'a','gameId':'minecraft','project':'Demo','status':'accepted','score':1,
                'matchedQueries':['old'],'versionsMentioned':[],'loadersMentioned':[],
                'evidence':[],'mediaCandidates':[]}
        rec={**sample,'status':'pending-review','matchedQueries':['new'],'score':2}
        out,n=merge([sample],[rec],'2026-11-08T01:00:00Z')
        self.assertEqual(n,0)
        self.assertEqual(out[0]['status'],'accepted')
        self.assertEqual(out[0]['matchedQueries'],['new','old'])

    def test_leads_must_have_known_game_and_approved_host(self):
        self.assertIsNone(from_lead(mc,{'gameId':'super-metroid','url':'https://github.com/abc/def'}))
        self.assertIsNone(from_lead(mc,{'gameId':'minecraft','url':'https://private.example/a'}))

    def test_ai_findings_require_exact_evidence_and_review(self):
        valid=json.loads((ROOT/'fixtures/example_agent_findings.json').read_text())
        clean=validate_findings(valid,{'minecraft'})
        self.assertTrue(clean['allRequireHumanReview'])
        bad=json.loads(json.dumps(valid))
        bad['findings'][0]['reviewRequired']=False
        with self.assertRaises(ValueError):validate_findings(bad,{'minecraft'})
        bad=json.loads(json.dumps(valid))
        bad['findings'][0]['sourceUrl']='http://127.0.0.1/secrets'
        with self.assertRaises(ValueError):validate_findings(bad,{'minecraft'})

    def test_media_triage_never_auto_assigns_variant(self):
        q={'candidates':[{'gameId':'minecraft','project':'demo','provider':'github','url':'https://github.com/demo/demo',
              'mediaCandidates':[{'url':'https://raw.githubusercontent.com/demo/demo/main/screenshots/demo.png','caption':'dual','sourceUrl':'https://github.com/demo/demo'}]}]}
        result=triage(q,{'candidates':[]},catalog)
        self.assertEqual(len(result['items']),1)
        self.assertIsNone(result['items'][0]['routeId'])
        self.assertIn('rights',result['items'][0]['reviewStatus'])

    def test_coverage_is_unknown_not_percent(self):
        q,_=run([mc],targets,fixture,False,leads,{'schemaVersion':1,'candidates':[],'runs':[]},budget=8)
        r=report(catalog,q)
        self.assertIn('unknown',r['games'][0]['coverageAssertion'])
        self.assertEqual(r['watchlistOnlyGames'],333)
        self.assertTrue(any(x['researchMode']=='fixture' for x in r['games']))

if __name__=='__main__':unittest.main()

# Additional tests can import this contract without a remote language model.
